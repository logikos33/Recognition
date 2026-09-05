#!/usr/bin/env python3
"""Fila de anotação do GABARITO v2 — quais 150 quadros o dono anota, e em que ordem.

O problema. O A/B das três variantes saiu não conclusivo porque o holdout tem ZERO
caixa de `Sem Luvas` e ZERO de `Sem mascara` (docs/quality/AB-HOLDOUT-V2.md). O que
desbloqueia não é treino, é GABARITO. Foram colhidos 440 quadros cheios 1920×1080 do
gravador do RVB (7 câmeras, 01/09 07h → 02/09 16h20, fábrica em operação). ~150 viram
gabarito. A hora do dono anotando é o recurso mais caro do projeto: 30-60 minutos.
Este script decide QUAIS e EM QUE ORDEM, para render o máximo por minuto.

⛔ RESTRIÇÃO INEGOCIÁVEL: nenhum CONTENDOR do A/B propõe caixa aqui. Nem para
pré-preencher, nem para ordenar. Contendores: variantes A (6ca25ee9), B (1deadfb0),
C (b9243540), baseline v10-ft (b3ae42b6) e o servido (46a30ed9). Gabarito
pré-preenchido pelo réu vira concordância medida, não verdade medida — o anotador
confirma a caixa que já está na tela. A saída deste script é LIMPA: só a ordem.

O detector de PESSOA (`yolox_nano`, COCO, classe `person`) NÃO é contendor: ele não
conhece nenhuma classe de EPI e não pode propor uma. Ele é usado só para SELECIONAR
e ORDENAR. É o mesmo objeto do caminho servido no edge (`PersonDetector` do
edge-sync-agent), com o ladrilhamento que o box usa.

O CRITÉRIO, declarado (ver `pontuar`):

  GATE (a) — anotável. Quadro sem pessoa enquadrada NÃO PODE conter ausência de EPI;
  é minuto perdido. Exige ≥1 pessoa com altura ≥ ALTURA_MINIMA px no quadro original.

  ORDEM (b) — probabilidade de conter ausência REAL, de sinais que não vêm de
  contendor:
    · VISIBILIDADE (peso 0,55) — altura em px da pessoa mais bem enquadrada. A mão
      é ~1/10 da altura da pessoa: com 420 px de pessoa a mão dá ~42 px, tamanho em
      que um humano separa luva de mão nua na tela. Caixa colada na borda SUPERIOR
      paga metade — cabeça cortada é rosto que não se julga (máscara, óculos).
    · DENSIDADE (peso 0,25) — mais gente no quadro, mais chances de alguém estar sem;
      e o minuto do dono rende mais caixas por quadro aberto. Retorno decrescente.
    · CONTEXTO (peso 0,20) — PRIOR DECLARADO, não medida: refeitório/convivência é
      onde máscara e luva SAEM (para comer, beber, fumar); porta de entrada é onde a
      pessoa ainda não colocou. Janelas de troca de turno e refeição idem. É palpite
      de domínio com peso pequeno de propósito, e as cotas por câmera (`--cota`)
      impedem que um prior errado sequestre o holdout.

  DEDUP POR RAJADA. Medido: a mediana do intervalo entre quadros consecutivos da
  mesma câmera é 0,5 s. Os 440 quadros são ~140 momentos distintos, não 440. Dois
  quadros da mesma rajada são quase o mesmo pixel: o segundo custa um minuto inteiro
  do dono e não acrescenta quase nada. Por isso a fila entrega PRIMEIRO um
  representante de cada rajada; só depois de esgotados os momentos distintos é que
  entra um segundo quadro de rajada (marcado `dup_rajada` na saída, para o dono poder
  parar antes deles sem perder nada).

Modos, na ordem em que se usa:

    --calibrar   mede a grade de ladrilhamento numa amostra (a grade errada
                 sub-detecta em silêncio e envenena toda a seleção)
    --pessoas    roda o detector de pessoa nos 440 e grava o JSONL
    --fila       pontua, ordena e grava o CSV + o relatório
    --autoteste  checa a lógica de pontuação/rajada/cota sem rede

    export DATABASE_URL=...
    eval "$(railway variables -s API-V3 -e Desenvolvimento --kv | grep ^R2_ | sed 's/^/export /')"
    python3 scripts/ops/fila_gabarito_v2.py --pessoas --modelo-pessoa <onnx> \\
        --jsonl docs/quality/evidence/gabarito-v2/pessoas-yolox-nano.jsonl
    python3 scripts/ops/fila_gabarito_v2.py --fila --jsonl <acima> \\
        --csv docs/quality/evidence/gabarito-v2/fila-gabarito-150.csv

Credenciais vêm do ambiente, nunca impressas, nunca escritas em arquivo.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

TENANT_RVB = "63c219d8-fbef-4f3c-a7c9-058c742482e2"

#: Gate (a). Altura em px, no quadro ORIGINAL, da menor pessoa que ainda vale abrir.
#: A mão é ~1/10 da altura: 200 px de pessoa → ~20 px de mão, o piso em que o humano
#: ainda separa luva de mão nua num JPEG de CFTV. Abaixo disso o dono não anota
#: `Sem Luvas` — ele ADIVINHA, e adivinhação no gabarito é pior que quadro nenhum.
ALTURA_MINIMA = 200

#: Altura em que a visibilidade satura (mão ≈ 42 px — leitura confortável).
ALTURA_PLENA = 420.0

#: Retorno decrescente da densidade: 1 pessoa → 0,45; 2 → 0,70; 3 → 0,83; 4 → 0,91.
BASE_DENSIDADE = 0.55

PESO_VISIBILIDADE = 0.55
PESO_DENSIDADE = 0.25
PESO_CONTEXTO = 0.20

#: Borda superior: caixa que começa a ≤ este y teve a cabeça cortada pelo quadro.
MARGEM_TOPO = 4

#: Fração da caixa MENOR que, se estiver dentro da maior, a torna a mesma pessoa.
#: Não é IoU: um FRAGMENTO (perna vista num ladrilho) tem IoU baixo com a pessoa
#: inteira e sobreviveria ao NMS, inflando a densidade. Contenção resolve.
CONTENCAO_MESMA_PESSOA = 0.70

#: Rajada: quadros da mesma câmera a menos disto um do outro são o mesmo momento.
#: 2 s é conservador — a mediana medida do acervo é 0,5 s e o segundo modo (5 s) já
#: agrupa quase igual (140 × 120 rajadas). Ver `--fila` no relatório.
SEGUNDOS_RAJADA = 2.0

#: PRIOR de contexto por câmera. Casado por substring no nome, minúsculo. É palpite
#: de domínio DECLARADO, com peso 0,20 — não é medida e não deve virar uma.
PRIOR_CAMERA = (
    ("convivência", 1.00),  # refeitório/descanso: máscara e luva saem aqui
    ("convivencia", 1.00),
    ("entrada", 0.60),      # porta: quem chega ainda não colocou
    ("expedição", 0.60),
    ("expedicao", 0.60),
)
PRIOR_CAMERA_PADRAO = 0.30

#: Janelas (hora local do frame, UTC-3) de troca de turno e refeição — momentos em
#: que o EPI sai ou ainda não entrou. Fora delas o prior de contexto paga 0,7.
JANELAS_TRANSICAO = ((7, 9), (11, 14), (16, 18))
FATOR_FORA_DA_JANELA = 0.70

#: ⚠️ `captured_at` vem com tzinfo=UTC mas o VALOR é o relógio de parede da
#: fábrica — o gravador grava a hora local e o campo é rotulado UTC. Conferido
#: contra o relógio QUEIMADO NA IMAGEM: o frame cujo captured_at é
#: 2026-09-01T07:00:00+00:00 tem "01/09/2026 07:00:00" impresso no canto. Deslocar
#: por -3 h (o palpite óbvio) jogaria a janela do almoço nas 15 h e a colheita
#: inteira (07:00→16:20) viraria uma madrugada de 04:00→13:20 numa fábrica que
#: comprovadamente está operando. Zero, então — e medido, não suposto.
FUSO_FABRICA = timedelta(0)

_SQL_FRAMES = """
SELECT f.id::text AS frame_id, f.r2_key, f.camera_id::text AS camera_id,
       c.name AS camera_name, f.captured_at, f.created_at, f.width, f.height
  FROM public.training_frames f
  LEFT JOIN public.cameras c ON c.id = f.camera_id
 WHERE f.tenant_id = %(tenant)s
   AND f.created_at > now() - (%(horas)s || ' hours')::interval
   AND f.width >= %(largura_min)s
   AND f.is_annotated = false
 ORDER BY f.captured_at, f.id
"""


# ── Pontuação (sem rede, sem banco — é o que o autoteste exercita) ────────────

def fundir(caixas: list[dict]) -> list[dict]:
    """União de grades: fica a MAIOR caixa de cada pessoa.

    Por que duas grades (medido em 40 quadros, `--calibrar`): o quadro inteiro em
    416×416 encolhe a pessoa distante até o YOLOX perdê-la (26/40 quadros com
    pessoa contra 33/40); mas o ladrilho RECORTA quem é alto — a maior caixa da
    grade 3×3 mede exatamente 432 px, que é a altura do ladrilho, não da pessoa.
    Uma grade só erra de um dos dois lados. A altura é justamente o sinal que
    ordena a fila, então medir errado ordenaria errado.

    (A grade 2×2 do edge foi descartada aqui: acusa pessoa em 40/40 quadros,
    inclusive no pátio comprovadamente vazio — foi calibrada para 704×480.)
    """
    ordenadas = sorted(caixas, key=lambda c: -(c["w"] * c["h"]))
    mantidas: list[dict] = []
    for c in ordenadas:
        area = max(1, c["w"] * c["h"])
        engolida = False
        for m in mantidas:
            ix = max(0, min(c["x"] + c["w"], m["x"] + m["w"]) - max(c["x"], m["x"]))
            iy = max(0, min(c["y"] + c["h"], m["y"] + m["h"]) - max(c["y"], m["y"]))
            if (ix * iy) / area >= CONTENCAO_MESMA_PESSOA:
                engolida = True
                break
        if not engolida:
            mantidas.append(c)
    return mantidas


def pessoa_anotavel(caixa: dict) -> bool:
    """A pessoa é grande o bastante para o dono julgar mão e rosto?"""
    return caixa["h"] >= ALTURA_MINIMA


def visibilidade(caixas: list[dict]) -> float:
    """0..1 da MELHOR pessoa do quadro. Cabeça cortada pela borda paga metade."""
    melhor = 0.0
    for c in caixas:
        if not pessoa_anotavel(c):
            continue
        v = min(1.0, c["h"] / ALTURA_PLENA)
        if c["y"] <= MARGEM_TOPO:
            v *= 0.5
        melhor = max(melhor, v)
    return melhor


def densidade(caixas: list[dict]) -> float:
    n = sum(1 for c in caixas if pessoa_anotavel(c))
    return 0.0 if n == 0 else 1.0 - BASE_DENSIDADE**n


def contexto(camera_nome: str | None, captured_at: datetime | None) -> float:
    """PRIOR declarado. Não é medida — ver o docstring do módulo."""
    nome = (camera_nome or "").lower()
    base = PRIOR_CAMERA_PADRAO
    for chave, valor in PRIOR_CAMERA:
        if chave in nome:
            base = max(base, valor)
    if captured_at is None:
        return base * FATOR_FORA_DA_JANELA
    hora = (captured_at + FUSO_FABRICA).hour
    dentro = any(ini <= hora < fim for ini, fim in JANELAS_TRANSICAO)
    return base if dentro else base * FATOR_FORA_DA_JANELA


def pontuar(registro: dict) -> dict:
    """Score do quadro + as três parcelas, para o relatório poder ser auditado."""
    caixas = registro.get("pessoas") or []
    v = visibilidade(caixas)
    d = densidade(caixas)
    c = contexto(registro.get("camera_name"), _quando(registro))
    return {
        "visibilidade": round(v, 4),
        "densidade": round(d, 4),
        "contexto": round(c, 4),
        "score": round(
            PESO_VISIBILIDADE * v + PESO_DENSIDADE * d + PESO_CONTEXTO * c, 4
        ),
        "n_pessoas": len(caixas),
        "n_anotaveis": sum(1 for x in caixas if pessoa_anotavel(x)),
        "altura_max": max((x["h"] for x in caixas), default=0),
    }


def _quando(registro: dict) -> datetime | None:
    bruto = registro.get("captured_at")
    if isinstance(bruto, datetime):
        return bruto
    if not bruto:
        return None
    return datetime.fromisoformat(bruto)


def rajadas(registros: list[dict], segundos: float = SEGUNDOS_RAJADA) -> dict[str, int]:
    """frame_id → id da rajada. Mesma câmera + intervalo ≤ `segundos` = mesmo momento."""
    por_camera: dict[str, list[dict]] = defaultdict(list)
    for r in registros:
        por_camera[r.get("camera_id") or "?"].append(r)
    saida: dict[str, int] = {}
    proxima = 0
    for camera in sorted(por_camera):
        anterior: datetime | None = None
        atual = -1
        for r in sorted(por_camera[camera], key=lambda x: (_quando(x) or datetime.min, x["frame_id"])):
            quando = _quando(r)
            novo = (
                anterior is None
                or quando is None
                or (quando - anterior).total_seconds() > segundos
            )
            if novo:
                proxima += 1
                atual = proxima
            saida[r["frame_id"]] = atual
            anterior = quando
    return saida


def montar_fila(registros: list[dict], alvo: int, cota: float) -> list[dict]:
    """A fila, na ordem em que o dono anota.

    Passe 1 — um representante por rajada (o de maior score), rajadas em ordem de
    score. É onde está TODO o ganho por minuto: 440 quadros são ~140 momentos.
    Passe 2 — só se faltar vaga, o segundo melhor quadro das melhores rajadas,
    marcado `dup_rajada=True` para o dono poder parar antes deles.

    `cota` é a fração máxima de UMA câmera na fila (diversidade: um prior de
    contexto errado não pode sequestrar o holdout). Excedente vai para o fim da
    fila, marcado `acima_da_cota=True` — nunca é descartado, só despriorizado.
    """
    aptos = [r for r in registros if r["_p"]["n_anotaveis"] > 0]
    grupo = rajadas(aptos)
    por_rajada: dict[int, list[dict]] = defaultdict(list)
    for r in aptos:
        por_rajada[grupo[r["frame_id"]]].append(r)
    for lista in por_rajada.values():
        lista.sort(key=lambda r: (-r["_p"]["score"], r["frame_id"]))

    ordem_rajadas = sorted(
        por_rajada, key=lambda g: (-por_rajada[g][0]["_p"]["score"], g)
    )

    teto = max(1, int(alvo * cota))
    fila: list[dict] = []
    excedente: list[dict] = []
    usados: Counter = Counter()

    def empurrar(r: dict, dup: bool, rodada: int) -> None:
        item = dict(r)
        item["dup_rajada"] = dup
        item["rajada"] = grupo[r["frame_id"]]
        item["acima_da_cota"] = False
        if usados[r["camera_id"]] >= teto:
            item["acima_da_cota"] = True
            excedente.append(item)
            return
        usados[r["camera_id"]] += 1
        item["passe"] = rodada
        fila.append(item)

    for g in ordem_rajadas:
        empurrar(por_rajada[g][0], dup=False, rodada=1)

    rodada = 2
    while len(fila) < alvo:
        restou = False
        for g in ordem_rajadas:
            if len(por_rajada[g]) >= rodada:
                restou = True
                empurrar(por_rajada[g][rodada - 1], dup=True, rodada=rodada)
                if len(fila) >= alvo:
                    break
        if not restou:
            break
        rodada += 1

    for item in excedente:
        item["passe"] = 99
    fila.extend(excedente)
    for i, item in enumerate(fila, 1):
        item["posicao"] = i
    return fila[:alvo] if alvo else fila


# ── Modo --pessoas ────────────────────────────────────────────────────────────

def _cliente_r2():
    from amostra_variante_c_fotos import _cliente_r2 as fabrica  # noqa: PLC0415

    return fabrica()


def _detector(caminho: str, grade: tuple[int, int], limiar: float):
    sys.path.insert(
        0, str(Path(__file__).resolve().parents[2] / "services" / "edge-sync-agent")
    )
    from app.collector.person_detector import PersonDetector  # noqa: PLC0415

    det = PersonDetector(
        model_path=caminho, confidence=limiar, tile_grid=grade
    )
    if not det.is_ready:
        raise RuntimeError(
            f"detector de pessoa não carregou de {caminho} — sem substituto silencioso"
        )
    return det


def _frames_do_banco(args) -> list[dict]:
    import psycopg2  # noqa: PLC0415
    from psycopg2.extras import RealDictCursor  # noqa: PLC0415

    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                _SQL_FRAMES,
                {
                    "tenant": args.tenant,
                    "horas": str(args.horas),
                    "largura_min": args.largura_min,
                },
            )
            return [dict(r) for r in cur.fetchall()]


def _bytes_do_frame(s3, cache: Path, fr: dict) -> bytes:
    local = cache / f"{fr['frame_id']}.jpg"
    if local.exists():
        return local.read_bytes()
    bruto = s3.get_object(Bucket=os.environ["R2_BUCKET"], Key=fr["r2_key"])["Body"].read()
    local.write_bytes(bruto)
    return bruto


def pessoas(args) -> int:
    frames = _frames_do_banco(args)
    print(f"frames: {len(frames)}")
    if not frames:
        print("ERRO: nenhum frame casou com o filtro. Parando.")
        return 1

    s3 = _cliente_r2()
    args.cache.mkdir(parents=True, exist_ok=True)
    dets = [(g, _detector(args.modelo_pessoa, g, args.limiar_pessoa)) for g in args.grades]
    grades_txt = "+".join(f"{nx}x{ny}" for nx, ny in args.grades)
    print(f"detector: {args.modelo_pessoa}  grades={grades_txt}  "
          f"limiar={args.limiar_pessoa}")

    args.jsonl.parent.mkdir(parents=True, exist_ok=True)
    falhas = 0
    with args.jsonl.open("w") as out:
        for i, fr in enumerate(frames, 1):
            try:
                bruto = _bytes_do_frame(s3, args.cache, fr)
                cruas: list[dict] = []
                for grade, det in dets:
                    res = det.detect(bruto)
                    if res.undetermined:
                        raise RuntimeError("detector indeterminado (erro de inferência)")
                    cruas.extend(
                        {"x": b.x, "y": b.y, "w": b.w, "h": b.h,
                         "conf": b.confidence, "grade": f"{grade[0]}x{grade[1]}"}
                        for b in res.boxes
                    )
                caixas = fundir(cruas)
            except Exception as exc:  # noqa: BLE001
                falhas += 1
                print(f"  FALHA {fr['frame_id']}: {exc}")
                continue
            out.write(
                json.dumps(
                    {
                        "frame_id": fr["frame_id"],
                        "r2_key": fr["r2_key"],
                        "camera_id": fr["camera_id"],
                        "camera_name": fr["camera_name"],
                        "captured_at": fr["captured_at"].isoformat()
                        if fr["captured_at"]
                        else None,
                        "created_at": fr["created_at"].isoformat()
                        if fr["created_at"]
                        else None,
                        "width": fr["width"],
                        "height": fr["height"],
                        "detector_pessoa": Path(args.modelo_pessoa).name,
                        "grades": grades_txt,
                        "limiar_pessoa": args.limiar_pessoa,
                        "pessoas": caixas,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            if i % 50 == 0:
                print(f"  {i}/{len(frames)}")
    print(f"gravado: {args.jsonl}  ({len(frames) - falhas} ok, {falhas} falhas)")
    return 1 if falhas else 0


def calibrar(args) -> int:
    """A grade de ladrilhamento é o joelho da medição — 2x2 foi calibrado para
    704×480 no edge, e aqui o quadro é 1920×1080. Grade errada sub-detecta em
    SILÊNCIO, e a seleção inteira sai envenenada. Então mede-se."""
    frames = _frames_do_banco(args)[: args.amostra]
    s3 = _cliente_r2()
    args.cache.mkdir(parents=True, exist_ok=True)
    brutos = [_bytes_do_frame(s3, args.cache, fr) for fr in frames]
    print(f"amostra: {len(brutos)} frames  limiar={args.limiar_pessoa}")
    print(f"{'grade':>7} {'frames c/ pessoa':>17} {'pessoas':>8} "
          f"{'pessoas ≥200px':>15} {'seg':>6}")
    import time  # noqa: PLC0415

    for grade in ((1, 1), (2, 2), (3, 3), (4, 3), (5, 3)):
        det = _detector(args.modelo_pessoa, grade, args.limiar_pessoa)
        t0 = time.time()
        com, total, grandes = 0, 0, 0
        for b in brutos:
            res = det.detect(b)
            if res.boxes:
                com += 1
            total += len(res.boxes)
            grandes += sum(1 for x in res.boxes if x.h >= ALTURA_MINIMA)
        print(f"{grade[0]}x{grade[1]:>5} {com:>17} {total:>8} {grandes:>15} "
              f"{time.time() - t0:>6.1f}")
    return 0


# ── Modo --fila ───────────────────────────────────────────────────────────────

def carregar(caminho: Path) -> list[dict]:
    return [json.loads(l) for l in caminho.open() if l.strip()]


def posicoes_na_galeria(registros: list[dict]) -> dict[str, int]:
    """frame_id → posição do card na galeria do Estúdio, contando de 1 por câmera.

    A galeria ordena por `created_at DESC, id DESC` (FrameRepository.
    list_frames_paginated, `ordem_sql`) e o Estúdio de anotação anda por essa
    MESMA lista, mostrando "N de M" no cabeçalho (AnnotationStudio.tsx:968). Com
    o filtro Origem=Câmera/NVR + Status=Não anotadas + a câmera, os 440 quadros
    desta colheita são os MAIS NOVOS do tenant — logo ocupam o PREFIXO da lista,
    e esta posição é literalmente o número que ele vê na tela.

    Conferido no banco: nas últimas 12 h existem exatamente 440 linhas, todas
    `source='nvr'`, todas `curation_status='active'`, todas `width>=1280` — nada
    se intercala no prefixo.
    """
    por_camera: dict[str, list[dict]] = defaultdict(list)
    for r in registros:
        por_camera[r.get("camera_id") or "?"].append(r)
    saida: dict[str, int] = {}
    for lista in por_camera.values():
        lista.sort(key=lambda r: (r.get("created_at") or "", r["frame_id"]), reverse=True)
        for i, r in enumerate(lista, 1):
            saida[r["frame_id"]] = i
    return saida


def fila(args) -> int:
    registros = carregar(args.jsonl)
    for r in registros:
        r["_p"] = pontuar(r)

    escolhidos = montar_fila(registros, args.alvo, args.cota)
    galeria = posicoes_na_galeria(registros)

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "frame_id", "posicao", "score", "camera_id", "camera_name",
                "posicao_na_galeria", "captured_at", "r2_key", "visibilidade",
                "densidade", "contexto", "n_pessoas", "n_anotaveis",
                "altura_max_px", "rajada", "dup_rajada", "acima_da_cota",
                "criterio",
            ]
        )
        for it in escolhidos:
            p = it["_p"]
            w.writerow([
                it["frame_id"], it["posicao"], f"{p['score']:.4f}", it["camera_id"],
                it["camera_name"], galeria[it["frame_id"]], it["captured_at"],
                it["r2_key"],
                f"{p['visibilidade']:.4f}", f"{p['densidade']:.4f}",
                f"{p['contexto']:.4f}", p["n_pessoas"], p["n_anotaveis"],
                p["altura_max"], it["rajada"],
                "sim" if it["dup_rajada"] else "nao",
                "sim" if it["acima_da_cota"] else "nao",
                f"vis{PESO_VISIBILIDADE}+den{PESO_DENSIDADE}+ctx{PESO_CONTEXTO}",
            ])
    print(f"gravado: {args.csv}  ({len(escolhidos)} quadros)")

    if args.roteiro:
        _roteiro(escolhidos, galeria, args.roteiro)
        print(f"gravado: {args.roteiro}")

    _medir(registros, escolhidos)
    return 0


_URL_ESTUDIO = "/novo/estudio/dados?camera={cid}&status=nao_anotado"

#: `PAGE_SIZE` da galeria (TrainingGallery.tsx). Clicar no card abre o Estúdio já
#: naquele índice — é o que evita 160 setas para chegar ao card 161.
TAMANHO_PAGINA = 60


def _roteiro(escolhidos: list[dict], galeria: dict[str, int], saida: Path) -> None:
    """A folha da sentada: por câmera, quais posições da galeria abrir.

    O Estúdio NÃO aceita ordem arbitrária nem lista de ids (conferido: a galeria
    monta o filtro em TrainingGallery.tsx:244-255 — page, page_size,
    curation_status, is_annotated, pending_review, camera_ids, source — e o
    Estúdio anda pelo array que ela entregou). Então o atalho não é uma feature
    nova: é o filtro que já existe + o número que o cabeçalho já mostra.
    """
    por_camera: dict[str, list[dict]] = defaultdict(list)
    for it in escolhidos:
        por_camera[it["camera_name"]].append(it)
    ordem = sorted(
        por_camera,
        key=lambda nome: -sum(
            1 for it in por_camera[nome] if not it["dup_rajada"]
        ),
    )
    linhas = [
        "# Roteiro da sentada — gabarito v2",
        "",
        "Gerado por `scripts/ops/fila_gabarito_v2.py --fila`. Não editar à mão.",
        "",
        "**Como usar.** Abra o link da câmera. Deixe **Status = Não anotadas** (o link",
        f"já manda). A galeria mostra **{TAMANHO_PAGINA} cards por página**, do mais",
        "novo para o mais velho — e os quadros desta colheita são os mais novos do",
        "acervo, então ocupam o começo da lista. Vá até a página indicada e **clique no",
        "card**: o Estúdio abre exatamente nele, e o contador do cabeçalho (`N de"
        f" {TAMANHO_PAGINA}`) confirma que é o card certo. `→` anda para o próximo.",
        "",
        "As câmeras estão na ordem em que rendem mais por minuto. Dentro de cada",
        "câmera, anote os cards da lista **instantes**; os de **repetições** são o",
        "mesmo momento meio segundo depois — só valem se sobrar tempo.",
        "",
        "⚠️ Anote uma câmera de uma vez só. Ao sair e voltar, o quadro já anotado sai",
        "do filtro *Não anotadas* e a numeração dos cards anda para trás.",
        "",
    ]
    for nome in ordem:
        itens = sorted(por_camera[nome], key=lambda it: galeria[it["frame_id"]])
        cid = itens[0]["camera_id"]
        momentos = [it for it in itens if not it["dup_rajada"]]
        linhas += [
            f"## {nome}",
            "",
            f"`{_URL_ESTUDIO.format(cid=cid)}`",
            "",
            f"{len(momentos)} instantes distintos + "
            f"{len(itens) - len(momentos)} repetições de rajada.",
            "",
        ]
        for rotulo, grupo in (("instantes", momentos),
                              ("repetições (opcional)", [i for i in itens if i["dup_rajada"]])):
            if not grupo:
                continue
            paginas: dict[int, list[int]] = defaultdict(list)
            for it in grupo:
                pos = galeria[it["frame_id"]]
                paginas[(pos - 1) // TAMANHO_PAGINA + 1].append(
                    (pos - 1) % TAMANHO_PAGINA + 1
                )
            linhas.append(f"**{rotulo}** — ")
            linhas.append(
                "; ".join(
                    f"pág {pg}: cards " + ", ".join(str(c) for c in sorted(cards))
                    for pg, cards in sorted(paginas.items())
                )
            )
            linhas.append("")
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text("\n".join(linhas))


def _medir(registros: list[dict], escolhidos: list[dict]) -> None:
    """Os números do item 5 do pedido. Tudo contado, nada estimado."""
    total = len(registros)
    com_pessoa = sum(1 for r in registros if r["_p"]["n_pessoas"] > 0)
    anotaveis = sum(1 for r in registros if r["_p"]["n_anotaveis"] > 0)
    print()
    print(f"quadros medidos            : {total}")
    print(f"com QUALQUER pessoa        : {com_pessoa} ({100*com_pessoa/total:.1f}%)")
    print(f"com pessoa ≥{ALTURA_MINIMA}px (gate) : {anotaveis} ({100*anotaveis/total:.1f}%)")
    print(f"rajadas distintas (aptos)  : {len(set(rajadas([r for r in registros if r['_p']['n_anotaveis']>0]).values()))}")
    print()
    print("distribuição do score (todos os aptos):")
    scores = sorted(r["_p"]["score"] for r in registros if r["_p"]["n_anotaveis"] > 0)
    if scores:
        for rot, idx in (("min", 0), ("p25", len(scores)//4), ("mediana", len(scores)//2),
                         ("p75", 3*len(scores)//4), ("max", len(scores)-1)):
            print(f"  {rot:>8}: {scores[idx]:.4f}")
    print()
    print("quadros por câmera na fila:")
    por_cam = Counter(it["camera_name"] for it in escolhidos)
    for nome, n in por_cam.most_common():
        print(f"  {n:>4}  {nome}")
    dups = sum(1 for it in escolhidos if it["dup_rajada"])
    print()
    print(f"na fila: {len(escolhidos)}  |  momentos distintos: {len(escolhidos)-dups}"
          f"  |  segundo-quadro-de-rajada: {dups}")


# ── Autoteste ─────────────────────────────────────────────────────────────────

def autoteste(_args) -> int:
    def caixa(h, y=100, x=10, w=50, conf=0.9):
        return {"x": x, "y": y, "w": w, "h": h, "conf": conf}

    # Fusão de grades: fragmento engolido pela pessoa inteira some; pessoa ao lado fica.
    inteira = {"x": 100, "y": 100, "w": 100, "h": 400}
    fragmento = {"x": 110, "y": 300, "w": 80, "h": 180}   # dentro da inteira
    vizinha = {"x": 400, "y": 100, "w": 100, "h": 400}    # sem sobreposição
    encostada = {"x": 180, "y": 100, "w": 100, "h": 400}  # 20% sobreposta
    assert fundir([inteira, fragmento]) == [inteira]
    assert fundir([fragmento, inteira]) == [inteira], "ordem de entrada não importa"
    assert len(fundir([inteira, vizinha])) == 2
    assert len(fundir([inteira, encostada])) == 2, "encostar não é ser a mesma pessoa"
    assert fundir([]) == []

    # Gate: pessoa pequena não é anotável.
    assert not pessoa_anotavel(caixa(ALTURA_MINIMA - 1))
    assert pessoa_anotavel(caixa(ALTURA_MINIMA))

    # Visibilidade satura e cabeça cortada paga metade.
    assert visibilidade([caixa(ALTURA_PLENA * 2)]) == 1.0
    assert visibilidade([caixa(int(ALTURA_PLENA), y=0)]) == 0.5
    assert visibilidade([caixa(ALTURA_MINIMA - 1)]) == 0.0, "pequena não pontua"
    assert visibilidade([caixa(300), caixa(500)]) == 1.0, "vale a MELHOR pessoa"

    # Densidade cresce e satura.
    assert densidade([]) == 0.0
    d1, d2 = densidade([caixa(300)]), densidade([caixa(300), caixa(300)])
    assert 0 < d1 < d2 < 1.0
    assert densidade([caixa(300), caixa(10)]) == d1, "pequena não conta densidade"

    # Contexto: prior declarado, refeitório > entrada > resto; fora da janela paga menos.
    # captured_at é relógio de parede da fábrica (ver FUSO_FABRICA).
    dentro = datetime.fromisoformat("2026-09-01T12:00:00+00:00")  # almoço
    fora = datetime.fromisoformat("2026-09-01T17:00:00+00:00")    # saída de turno
    madrugada = datetime.fromisoformat("2026-09-01T03:00:00+00:00")
    assert contexto("Espaço de convivência", dentro) > contexto("Entrada Expedição", dentro)
    assert contexto("Entrada Expedição", dentro) > contexto("Corredor", dentro)
    assert contexto("Espaço de convivência", madrugada) < contexto("Espaço de convivência", dentro)
    assert contexto("Espaço de convivência", fora) == contexto("Espaço de convivência", dentro)

    # Rajada: mesma câmera, 0,5 s de intervalo = um momento; 10 s = dois.
    def reg(fid, cam, seg, h=300):
        return {
            "frame_id": fid, "camera_id": cam, "camera_name": cam,
            "captured_at": (datetime.fromisoformat("2026-09-01T10:00:00+00:00")
                            + timedelta(seconds=seg)).isoformat(),
            "pessoas": [caixa(h)],
        }

    juntos = [reg("a", "c1", 0), reg("b", "c1", 0.5), reg("c", "c1", 1.0)]
    g = rajadas(juntos)
    assert len({g["a"], g["b"], g["c"]}) == 1, g
    separados = [reg("a", "c1", 0), reg("b", "c1", 30)]
    g = rajadas(separados)
    assert g["a"] != g["b"]
    # Câmeras diferentes no MESMO instante nunca são a mesma rajada.
    g = rajadas([reg("a", "c1", 0), reg("b", "c2", 0)])
    assert g["a"] != g["b"]

    # Fila: passe 1 é um por rajada; duplicata só depois, e marcada.
    regs = [reg("a", "c1", 0, 400), reg("b", "c1", 0.5, 300), reg("c", "c2", 0, 250)]
    for r in regs:
        r["_p"] = pontuar(r)
    f = montar_fila(regs, alvo=3, cota=1.0)
    assert [x["frame_id"] for x in f[:2]] == ["a", "c"], [x["frame_id"] for x in f]
    assert f[0]["dup_rajada"] is False and f[2]["dup_rajada"] is True
    assert f[2]["frame_id"] == "b"

    # Quadro sem pessoa anotável NUNCA entra na fila (gate (a)).
    vazio = reg("z", "c3", 0, h=10)
    vazio["_p"] = pontuar(vazio)
    f = montar_fila([vazio], alvo=10, cota=1.0)
    assert f == [], f

    # Cota: câmera dominante não sequestra a fila; excedente vai pro fim, não some.
    muitos = []
    for i in range(10):
        r = reg(f"m{i}", "c1", i * 60, 400)
        r["_p"] = pontuar(r)
        muitos.append(r)
    outro = reg("outro", "c2", 0, 210)
    outro["_p"] = pontuar(outro)
    f = montar_fila(muitos + [outro], alvo=11, cota=0.3)
    assert sum(1 for x in f[:3] if x["camera_id"] == "c1") == 3
    assert any(x["frame_id"] == "outro" and not x["acima_da_cota"] for x in f)
    assert len(f) == 11, "excedente é despriorizado, nunca descartado"
    assert all(x["acima_da_cota"] for x in f[4:]), [x["frame_id"] for x in f]

    print("autoteste OK")
    return 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def _grade(bruto: str) -> tuple[int, int]:
    nx, _, ny = bruto.lower().partition("x")
    return int(nx), int(ny)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    modo = ap.add_mutually_exclusive_group(required=True)
    modo.add_argument("--pessoas", action="store_true")
    modo.add_argument("--calibrar", action="store_true")
    modo.add_argument("--fila", action="store_true")
    modo.add_argument("--autoteste", action="store_true")

    ap.add_argument("--tenant", default=TENANT_RVB)
    ap.add_argument("--horas", type=int, default=12)
    ap.add_argument("--largura-min", type=int, default=1280)
    ap.add_argument("--modelo-pessoa",
                    default="/Users/vitoremanuel/Logikos-mutirao/modelos-servidos/"
                            "yolox_nano_SERVIDO.onnx")
    ap.add_argument("--grades", type=lambda s: [_grade(p) for p in s.split("+")],
                    default=[(1, 1), (3, 3)],
                    help="ladrilhamentos unidos por '+' (ver --calibrar e `fundir`). "
                         "1x1 mede quem está perto sem cortar; 3x3 acha quem está "
                         "longe. 2x2 (default do edge) foi calibrado p/ 704x480 e "
                         "aqui acusa pessoa em pátio vazio.")
    ap.add_argument("--limiar-pessoa", type=float, default=0.35,
                    help="o mesmo default do coletor do edge")
    ap.add_argument("--amostra", type=int, default=40, help="frames em --calibrar")
    ap.add_argument("--cache", type=Path,
                    default=Path("/tmp/gabarito-v2-frames"))  # noqa: S108
    ap.add_argument("--jsonl", type=Path,
                    default=Path("docs/quality/evidence/gabarito-v2/"
                                 "pessoas-yolox-nano.jsonl"))
    ap.add_argument("--csv", type=Path,
                    default=Path("docs/quality/evidence/gabarito-v2/"
                                 "fila-gabarito-150.csv"))
    ap.add_argument("--roteiro", type=Path,
                    default=Path("docs/quality/evidence/gabarito-v2/"
                                 "ROTEIRO-DA-SENTADA.md"))
    ap.add_argument("--alvo", type=int, default=150)
    ap.add_argument("--cota", type=float, default=0.30,
                    help="fração máxima de UMA câmera na fila")
    args = ap.parse_args()

    if args.autoteste:
        return autoteste(args)
    if args.calibrar:
        return calibrar(args)
    if args.pessoas:
        return pessoas(args)
    return fila(args)


if __name__ == "__main__":
    raise SystemExit(main())
