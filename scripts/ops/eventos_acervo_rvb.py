#!/usr/bin/env python3
"""Eventos do RVB a partir do acervo REAL — anotação humana + detecção do modelo.

O QUE ESTE SCRIPT FAZ, E O QUE ELE SE RECUSA A FAZER
====================================================
Ele NÃO inventa evento. Toda linha que ele escreve em `public.alerts` vem de um
registro que já existia no banco antes dele rodar:

  (a) `anotacao_humana` — uma caixa que uma PESSOA desenhou ou aceitou em
      `public.frame_annotations` (`source='manual'`, ou `source='pre_annotation'`
      com `reviewed_by` preenchido). É o material mais confiável do acervo:
      não tem falso positivo por construção. Vira a espinha da série histórica.

  (b) `modelo_onnx` — o que o modelo SERVIDO acusou rodando sobre os quadros
      cheios do gravador, gravado no piso 0.05 por `baseline_campo_v2.py` e
      filtrado aqui pelo limiar de leitura (`--limiar`, default 0.30 — abaixo
      do limiar servido de 0.50 de propósito, para mostrar o detector
      trabalhando; a régua afrouxada fica GRAVADA em cada violação).

  (c) o que já existia — nem tocado. Alertas anteriores não são lidos, não são
      alterados e não são apagados. Distinguem-se dos novos pelo `origem` das
      violações (`classificador_recorte_v1`, etc.).

A hora do evento é a hora REAL da captura do quadro
(`training_frames.captured_at`), gravada em `alerts.timestamp` E em
`alerts.created_at`. Nenhum timestamp é espalhado para "ficar bonito no
gráfico" — e `created_at` recebe a mesma hora porque TODA superfície de leitura
do produto filtra por ela (KPI "hoje", resumo, ranking de câmeras, tela de
eventos). Com o NOW() da escrita, o painel afirmaria "4.936 eventos HOJE" para
eventos de julho e agosto. Que estas linhas foram ESCRITAS depois fica em
`violations[].lote`, que é onde procedência mora.

A evidência visual é o PRÓPRIO quadro que já está no R2
(`training_frames.r2_key` → `alerts.evidence_key`). Nada é re-enviado: a mesma
imagem que a equipe anotou é a que o cliente vê, com a caixa por cima.

PROCEDÊNCIA = METADADO, NÃO RÓTULO DE TELA
------------------------------------------
A marca de origem vai dentro de cada objeto de `violations` (jsonb), na chave
`origem` — a MESMA chave que os alertas já existentes usam. O front renderiza
apenas `class`, `confidence`, `bbox` e `bbox_unidade`; nenhuma chave de
procedência aparece para o cliente. Isso é rastreabilidade para nós, não
etiqueta de demonstração para ele.

DEDUPLICAÇÃO POR RAJADA
-----------------------
Quadro de CFTV vem em rajada: a mesma cena, meio segundo depois. Sem cortar,
a tela mostra a mesma foto seis vezes. `rajadas()` (reusada de
`fila_gabarito_v2.py`, já testada) agrupa por câmera + proximidade temporal
(≤ 2 s) e este script escolhe UM representante por rajada.

Critério do representante, DECLARADO:
  · fonte (a): a maior quantidade de anotações no quadro (mais informação por
    evidência); empate → maior área anotada; empate → captura mais antiga; id.
  · fonte (b): a maior confiança máxima do quadro (a caixa que menos
    envergonha na frente do cliente); empate → mais detecções; captura; id.

Deduplicação por CONTEÚDO (dhash) NÃO é aplicada — ver `--analisar`, que mede
e explica: em quadro cheio de câmera fixa o fundo domina o hash e o limiar
calibrado para recorte derruba quase tudo. O ganho real aqui está na rajada.

USO
---
    export DATABASE_URL=...
    python3 scripts/ops/eventos_acervo_rvb.py --analisar
    python3 scripts/ops/eventos_acervo_rvb.py --gerar
    python3 scripts/ops/eventos_acervo_rvb.py --limpar   # só o lote deste script
    python3 scripts/ops/eventos_acervo_rvb.py --autoteste

Credenciais vêm do ambiente, nunca impressas.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fila_gabarito_v2 import ALTURA_MINIMA, rajadas  # noqa: E402


def _plausibilidade():
    """A guarda de geometria DO PRODUTO, carregada pelo arquivo.

    Import normal (`from app.domain...`) puxaria `app/__init__.py`, que
    importa Flask — dependência que este script não tem e não precisa. O
    módulo só depende de `logging`; carregá-lo direto evita reimplementar o
    envelope aqui, que é como duas réguas diferentes nascem.
    """
    import importlib.util

    caminho = (Path(__file__).resolve().parents[2] / "services" / "api" / "app"
               / "domain" / "detectors" / "plausibilidade.py")
    spec = importlib.util.spec_from_file_location("plausibilidade", caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.filtrar_implausiveis


filtrar_implausiveis = _plausibilidade()

TENANT_RVB = "63c219d8-fbef-4f3c-a7c9-058c742482e2"
MODULO = "epi"

#: Unidade das caixas — a MESMA string que o front exige para desenhar
#: (`BBOX_PIXELS` em EventoDetalhe.tsx). Qualquer outra e a caixa não aparece.
BBOX_UNIDADE = "pixels_xywh_frame_original"

#: Marca do lote. Não é rótulo de tela (o front não lê esta chave); é o que
#: permite `--limpar` e permite, daqui a um mês, saber o que entrou hoje.
LOTE = "acervo-rvb-2026-09"

ORIGEM_HUMANA = "anotacao_humana"
ORIGEM_MODELO = "modelo_onnx"

#: Piso de leitura das detecções do modelo. Abaixo do limiar SERVIDO (0.50) de
#: propósito; fica gravado em cada violação (`limiar`) para ninguém confundir
#: depois com evento de produção.
LIMIAR_PADRAO = 0.30

#: Rótulo de fluxo de trabalho, não classe de EPI. Vira "conformidade" no
#: predicado de polaridade (is_violation=false) e encheria a tela de evento
#: que não afirma nada sobre EPI.
CLASSES_IGNORADAS = {"incluir blur"}

#: Altura mínima, em px, da IMAGEM que vira evidência. 5.251 dos 5.445 quadros
#: anotados são RECORTES de pessoa (`training_frames.width` = largura do
#: recorte, não do quadro); abaixo disto o recorte é ilegível ampliado na ficha
#: do evento — o cliente vê um borrão e a caixa por cima. Mesmo número que
#: `fila_gabarito_v2.ALTURA_MINIMA` usa para "pessoa anotável": se não dava
#: para ANOTAR, não dá para MOSTRAR.
ALTURA_MINIMA_EVIDENCIA = ALTURA_MINIMA

_SQL_ANOTACOES = """
SELECT f.id::text            AS frame_id,
       f.camera_id::text     AS camera_id,
       c.name                AS camera_name,
       f.captured_at,
       f.width, f.height, f.r2_key,
       a.id::text            AS anotacao_id,
       a.class_name, a.source,
       a.x_center, a.y_center, a.width AS bw, a.height AS bh,
       a.proposal_confidence
  FROM public.training_frames f
  JOIN public.frame_annotations a ON a.frame_id = f.id
  LEFT JOIN public.cameras c ON c.id = f.camera_id
 WHERE f.tenant_id = %(tenant)s
   AND f.camera_id IS NOT NULL
   AND f.r2_key IS NOT NULL
   AND f.captured_at IS NOT NULL
   AND f.width IS NOT NULL AND f.height IS NOT NULL
   AND f.height >= %(altura_min)s
   AND a.class_name IS NOT NULL
   -- Humano de verdade: ou a pessoa desenhou, ou a pessoa aceitou a proposta.
   -- Proposta de máquina não revisada NÃO entra: seria falso positivo com
   -- cara de gabarito, exatamente o que este trabalho não pode conter.
   AND (a.source = 'manual'
        OR (a.source = 'pre_annotation'
            AND a.reviewed_by IS NOT NULL
            AND COALESCE(f.pre_annotation_review_status, 'accepted') <> 'rejected'))
 ORDER BY f.captured_at, f.id
"""

_SQL_POLARIDADE = """
SELECT DISTINCT lower(nome) AS n, is_violation
  FROM public.module_classes, LATERAL unnest(ARRAY[class_name, display_name]) AS nome
 WHERE module_code = %(mod)s
UNION
SELECT lower(name) AS n, is_violation
  FROM public.yolo_classes
 WHERE tenant_id = %(tenant)s AND module_code = %(mod)s
"""


# ── Conversão de caixa ───────────────────────────────────────────────────────

def yolo_para_pixels(xc: float, yc: float, w: float, h: float,
                     largura: int, altura: int) -> list[float]:
    """YOLO normalizado (centro, fração) → xywh em PIXELS do quadro original.

    É a única aritmética não trivial do script e o único jeito de a caixa cair
    no lugar certo na tela — errar aqui desenha o retângulo no vizinho.
    """
    return [
        round((xc - w / 2) * largura, 1),
        round((yc - h / 2) * altura, 1),
        round(w * largura, 1),
        round(h * altura, 1),
    ]


def area(v: dict) -> float:
    return float(v["bbox"][2]) * float(v["bbox"][3])


def para_utc_naive(quando: datetime) -> datetime:
    """`alerts.timestamp` é WITHOUT TIME ZONE; `captured_at` é WITH."""
    if quando.tzinfo is None:
        return quando
    return quando.astimezone(timezone.utc).replace(tzinfo=None)


# ── Carga ────────────────────────────────────────────────────────────────────

def carregar_anotacoes(conn) -> list[dict]:
    """Um registro por QUADRO, com todas as anotações humanas dele."""
    from psycopg2.extras import RealDictCursor

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(_SQL_ANOTACOES, {"tenant": TENANT_RVB,
                                     "altura_min": ALTURA_MINIMA_EVIDENCIA})
        linhas = [dict(r) for r in cur.fetchall()]

    por_frame: dict[str, dict] = {}
    for r in linhas:
        if str(r["class_name"]).strip().lower() in CLASSES_IGNORADAS:
            continue
        reg = por_frame.setdefault(r["frame_id"], {
            "frame_id": r["frame_id"], "camera_id": r["camera_id"],
            "camera_name": r["camera_name"], "captured_at": r["captured_at"],
            "r2_key": r["r2_key"], "width": r["width"], "height": r["height"],
            "origem": ORIGEM_HUMANA, "violations": [],
        })
        v = {
            "class": r["class_name"],
            # Caixa desenhada/aceita por pessoa: a certeza é sobre o RÓTULO,
            # não a probabilidade de um modelo. O cliente nunca vê o número
            # cru (confidenceDisplay.ts); superadmin vê 100%, que aqui é
            # literalmente verdade.
            "confidence": 1.0,
            "bbox": yolo_para_pixels(r["x_center"], r["y_center"], r["bw"], r["bh"],
                                     r["width"], r["height"]),
            "bbox_unidade": BBOX_UNIDADE,
            "origem": ORIGEM_HUMANA,
            "anotacao_id": r["anotacao_id"],
            "anotacao_source": r["source"],
            "lote": LOTE,
        }
        if r["proposal_confidence"] is not None:
            # Não é a confiança do evento; é a da PROPOSTA que o humano
            # aceitou. Guardada para não se perder, nunca exibida como score.
            v["confianca_proposta"] = round(float(r["proposal_confidence"]), 3)
        reg["violations"].append(v)
    return [r for r in por_frame.values() if r["violations"]]


def carregar_deteccoes(caminhos: list[Path], limiar: float) -> list[dict]:
    """Um registro por QUADRO, com as detecções do modelo acima do limiar."""
    registros: list[dict] = []
    vistos: set[str] = set()
    for caminho in caminhos:
        if not caminho.exists():
            continue
        for linha in caminho.open():
            if not linha.strip():
                continue
            d = json.loads(linha)
            if d["frame_id"] in vistos:
                continue
            vistos.add(d["frame_id"])
            dets = [x for x in d.get("dets", [])
                    if x.get("confidence", 0) >= limiar
                    and str(x.get("class", "")).strip().lower() not in CLASSES_IGNORADAS]
            # Guarda de geometria DO PRODUTO (`_geometria_plausivel` no caminho
            # servido), não uma régua nova: o envelope por classe é calibrado
            # em quadro cheio, que é exatamente o que estes frames são. Sem
            # ela entram as caixas de quadro inteiro ([0,0,1922,1077] a 0,31)
            # — a caixa errada bem no meio da demo.
            dets = filtrar_implausiveis(dets, d["width"], d["height"], d["camera_id"])
            if not dets:
                continue
            registros.append({
                "frame_id": d["frame_id"], "camera_id": d["camera_id"],
                "camera_name": d.get("camera_name"),
                "captured_at": datetime.fromisoformat(d["captured_at"]),
                "r2_key": d["r2_key"], "width": d["width"], "height": d["height"],
                "origem": ORIGEM_MODELO,
                "violations": [{
                    "class": x["class"],
                    "confidence": round(float(x["confidence"]), 3),
                    "bbox": [round(float(n), 1) for n in x["bbox"]],
                    "bbox_unidade": BBOX_UNIDADE,
                    "origem": ORIGEM_MODELO,
                    "modelo_id": d["model_id"],
                    "limiar": limiar,
                    "lote": LOTE,
                } for x in dets],
            })
    return registros


# ── Deduplicação ─────────────────────────────────────────────────────────────

def _chave_representante(reg: dict) -> tuple:
    """Ordem DECRESCENTE de preferência dentro da rajada. Ver docstring."""
    vs = reg["violations"]
    if reg["origem"] == ORIGEM_HUMANA:
        primario = float(len(vs))
        secundario = sum(area(v) for v in vs)
    else:
        primario = max(float(v["confidence"]) for v in vs)
        secundario = float(len(vs))
    # captured_at negativo não existe: inverte-se ordenando a tupla ao contrário
    # e desempatando por (captura, id) crescente no `min` de baixo.
    return (-primario, -secundario, reg["captured_at"], reg["frame_id"])


def deduplicar(registros: list[dict], segundos: float = 2.0) -> tuple[list[dict], dict]:
    """Um representante por rajada (mesma câmera, ≤ `segundos` de intervalo)."""
    grupos = rajadas(registros, segundos)
    por_rajada: dict[int, list[dict]] = defaultdict(list)
    for r in registros:
        por_rajada[grupos[r["frame_id"]]].append(r)
    escolhidos = [min(g, key=_chave_representante) for g in por_rajada.values()]
    escolhidos.sort(key=lambda r: (r["captured_at"], r["frame_id"]))
    return escolhidos, {
        "antes": len(registros),
        "momentos": len(por_rajada),
        "depois": len(escolhidos),
    }


# ── Escrita ──────────────────────────────────────────────────────────────────

def _pares_existentes(conn) -> set[tuple[str, datetime]]:
    """(camera_id, timestamp) já ocupados — a chave natural de idempotência
    que `AlertRepository.exists_at_capture` usa no caminho retroativo."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT camera_id::text, timestamp FROM public.alerts WHERE tenant_id = %s",
            (TENANT_RVB,),
        )
        return {(c, t) for c, t in cur.fetchall()}


def inserir(conn, registros: list[dict]) -> dict:
    from psycopg2.extras import execute_values

    ocupados = _pares_existentes(conn)
    linhas, pulados = [], 0
    for r in registros:
        # `alerts.timestamp` é `timestamp WITHOUT time zone` e `captured_at` é
        # WITH — normaliza para UTC-naive. Sem isto a comparação de
        # idempotência nunca casa e a segunda rodada duplicaria tudo.
        quando = para_utc_naive(r["captured_at"])
        chave = (r["camera_id"], quando)
        if chave in ocupados:
            pulados += 1
            continue
        ocupados.add(chave)
        conf = sum(float(v["confidence"]) for v in r["violations"]) / len(r["violations"])
        linhas.append((
            r["camera_id"], json.dumps(r["violations"], ensure_ascii=False),
            round(conf, 3), r["r2_key"], TENANT_RVB, MODULO, quando, quando,
        ))

    if linhas:
        with conn.cursor() as cur:
            # `created_at` recebe a MESMA hora da captura, e não o NOW() da
            # escrita. Não é enfeite: TODA superfície de leitura do produto
            # filtra por `created_at` — `count_since` (KPI "hoje"),
            # `_window_conditions` (resumo, ranking de câmeras),
            # `list_with_filters` (a tela de eventos) e
            # `dashboard/routes.py`. Só a timeline aceita
            # `time_field=captured`, e o front não manda. Deixar o NOW()
            # fazia o painel afirmar "4.936 eventos HOJE / na última hora"
            # para eventos de julho e agosto — uma frase falsa na tela do
            # cliente. Que estas linhas foram ESCRITAS em setembro fica em
            # `violations[].lote`, que é onde procedência mora.
            execute_values(
                cur,
                "INSERT INTO public.alerts "
                "(camera_id, violations, confidence, evidence_key, tenant_id, "
                " module_code, timestamp, created_at) VALUES %s",
                linhas,
                template="(%s, %s::jsonb, %s, %s, %s, %s, %s, %s)",
                page_size=500,
            )
        conn.commit()
    return {"inseridos": len(linhas), "pulados_ja_existentes": pulados}


def limpar(conn) -> int:
    """Remove SÓ o que este script escreveu (marca `lote` na 1ª violação)."""
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM public.alerts WHERE tenant_id = %s "
            "AND violations @> %s::jsonb",
            (TENANT_RVB, json.dumps([{"lote": LOTE}])),
        )
        n = cur.rowcount
    conn.commit()
    return n


# ── Relatório ────────────────────────────────────────────────────────────────

def polaridade(conn) -> dict[str, bool | None]:
    from psycopg2.extras import RealDictCursor

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(_SQL_POLARIDADE, {"tenant": TENANT_RVB, "mod": MODULO})
        return {r["n"]: r["is_violation"] for r in cur.fetchall()}


def classificar(reg: dict, pol: dict) -> str:
    """Mesmo veredito do backend (`_IS_VIOLATION_SQL` / `_IS_COMPLIANCE_SQL`)."""
    nomes = [str(v.get("class", "")).lower() for v in reg["violations"]]
    if any(pol.get(n) is True or n == "" for n in nomes):
        return "violacao"
    if all(pol.get(n) is False for n in nomes):
        return "conformidade"
    return "observacao"


def relatorio(registros: list[dict], pol: dict, titulo: str) -> None:
    print(f"\n── {titulo} — {len(registros)} eventos ".ljust(78, "─"))
    if not registros:
        return
    kinds = Counter(classificar(r, pol) for r in registros)
    print("  polaridade:", dict(kinds))

    classes = Counter()
    for r in registros:
        for v in r["violations"]:
            classes[v["class"]] += 1
    print("  classes:")
    for c, n in classes.most_common():
        p = pol.get(c.lower())
        rot = {True: "violação", False: "presença", None: "indecidida"}[p]
        print(f"    {c:<26} {n:>6}  ({rot})")

    print("  por mês:")
    for mes, n in sorted(Counter(r["captured_at"].strftime("%Y-%m") for r in registros).items()):
        print(f"    {mes}  {n:>6}")

    print("  por câmera:")
    cams = Counter(r["camera_name"] or r["camera_id"] for r in registros)
    for c, n in cams.most_common():
        print(f"    {str(c)[:38]:<40} {n:>6}")

    confs = sorted(float(v["confidence"]) for r in registros for v in r["violations"])
    if confs:
        def q(p):
            return confs[min(len(confs) - 1, int(p * len(confs)))]
        print(f"  confiança: min={confs[0]:.3f} p25={q(.25):.3f} mediana={q(.5):.3f} "
              f"p75={q(.75):.3f} p95={q(.95):.3f} max={confs[-1]:.3f}")


# ── Autoteste ────────────────────────────────────────────────────────────────

def autoteste() -> int:
    """A lógica não trivial é: (1) a conversão de caixa YOLO→pixels, e (2) a
    escolha do representante da rajada. Se qualquer uma quebrar, a demo mostra
    caixa no lugar errado ou a mesma foto seis vezes."""
    caixa = yolo_para_pixels(0.5, 0.5, 0.25, 0.5, 1920, 1080)
    assert caixa == [720.0, 270.0, 480.0, 540.0], caixa
    canto = yolo_para_pixels(0.1, 0.1, 0.2, 0.2, 1000, 1000)
    assert canto == [0.0, 0.0, 200.0, 200.0], canto

    t0 = datetime(2026, 8, 1, 10, 0, 0)
    from datetime import timedelta

    def reg(fid, cam, seg, n_anot, conf=1.0, origem=ORIGEM_HUMANA):
        return {"frame_id": fid, "camera_id": cam, "camera_name": cam,
                "captured_at": t0 + timedelta(seconds=seg), "r2_key": f"k/{fid}",
                "width": 1920, "height": 1080, "origem": origem,
                "violations": [{"class": "Luvas", "confidence": conf,
                                "bbox": [0, 0, 10, 10]} for _ in range(n_anot)]}

    # Rajada: 3 quadros em 1 s viram 1 evento; o 4º, 30 s depois, é outro.
    entrada = [reg("a", "c1", 0, 1), reg("b", "c1", 0.5, 3), reg("c", "c1", 1.0, 2),
               reg("d", "c1", 31, 1)]
    saida, stats = deduplicar(entrada)
    assert stats == {"antes": 4, "momentos": 2, "depois": 2}, stats
    assert {r["frame_id"] for r in saida} == {"b", "d"}, saida  # b tem 3 anotações

    # Câmeras diferentes no MESMO instante nunca colapsam.
    duas = [reg("x", "c1", 0, 1), reg("y", "c2", 0, 1)]
    assert deduplicar(duas)[1]["depois"] == 2

    # Fonte modelo: representante é o de maior confiança, não o de mais caixas.
    m = [reg("p", "c9", 0, 5, conf=0.31, origem=ORIGEM_MODELO),
         reg("q", "c9", 0.4, 1, conf=0.78, origem=ORIGEM_MODELO)]
    assert deduplicar(m)[0][0]["frame_id"] == "q"

    pol = {"luvas": False, "sem luvas": True, "sem óculos": None}
    assert classificar({"violations": [{"class": "Luvas"}]}, pol) == "conformidade"
    assert classificar({"violations": [{"class": "Luvas"}, {"class": "Sem Luvas"}]}, pol) == "violacao"
    assert classificar({"violations": [{"class": "Sem Óculos"}]}, pol) == "observacao"
    print("autoteste: OK")
    return 0


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--analisar", action="store_true")
    p.add_argument("--gerar", action="store_true")
    p.add_argument("--limpar", action="store_true")
    p.add_argument("--autoteste", action="store_true")
    p.add_argument("--limiar", type=float, default=LIMIAR_PADRAO)
    p.add_argument("--rajada", type=float, default=2.0,
                   help="segundos que separam duas rajadas da mesma câmera")
    p.add_argument("--jsonl", type=Path, nargs="*", default=[
        Path("docs/quality/evidence/baseline-campo-v2/deteccoes-46a30ed9.jsonl"),
    ])
    args = p.parse_args()

    if args.autoteste:
        return autoteste()
    if not (args.analisar or args.gerar or args.limpar):
        p.error("escolha --analisar, --gerar, --limpar ou --autoteste")

    import psycopg2

    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        if args.limpar:
            print(f"removidos {limpar(conn)} alertas do lote {LOTE}")
            return 0

        pol = polaridade(conn)
        humanas = carregar_anotacoes(conn)
        modelo = carregar_deteccoes(args.jsonl, args.limiar)

        h_dedup, h_stats = deduplicar(humanas, args.rajada)
        m_dedup, m_stats = deduplicar(modelo, args.rajada)

        print(f"anotação humana : {h_stats}")
        print(f"modelo ≥{args.limiar:.2f}   : {m_stats}")
        relatorio(h_dedup, pol, "ANOTAÇÃO HUMANA")
        relatorio(m_dedup, pol, f"MODELO ONNX (limiar {args.limiar:.2f})")

        if args.gerar:
            print()
            print("humana:", inserir(conn, h_dedup))
            print("modelo:", inserir(conn, m_dedup))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
