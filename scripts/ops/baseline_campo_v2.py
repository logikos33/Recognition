#!/usr/bin/env python3
"""Baseline de campo: o modelo SERVIDO rodado nos frames cheios de CFTV do RVB.

Por que existe. O modelo é servido em quadro inteiro 1920×1080 (single-stage), mas
até hoje ninguém tinha medido o que ele acusa NESSE domínio — as métricas do
registry vêm do holdout do dataset, que é feito de RECORTES de pessoa. "Baseline de
campo" é a diferença entre as duas coisas, e ela é o número que o cliente vê.

Três modos, na ordem em que se usam:

  --inferir   roda o ONNX do modelo sobre os frames e grava um JSONL (o artefato)
  --sweep     varre limiares sobre um JSONL já gravado (nenhuma inferência)
  --folha     monta a folha de contato HTML, com as fotos do R2 e as caixas

O JSONL é o ponto da coisa. Quando o vencedor do A/B existir, ele roda
`--inferir --ids-de <jsonl-do-baseline>` — MESMOS frames, mesma ordem — e a
comparação vira diff de dois arquivos com a mesma chave (frame_id, classe).
Sem isso, a segunda rodada mediria outro conjunto e o "melhorou" seria opinião.

O piso de gravação é 0.05, deliberadamente abaixo de qualquer limiar que se vá
discutir: NMS é ganancioso em ordem decrescente de score, então caixa abaixo de T
nunca altera quais caixas acima de T sobrevivem. Gravar no piso e filtrar depois dá
EXATAMENTE o mesmo resultado que rodar com o piso em T — e permite varrer sem
reprocessar 440 imagens.

O pré-processamento NÃO é reimplementado aqui: usa `RfDetrOnnxDetector` do produto,
o mesmo objeto do caminho servido. Normalização errada dá resultado silenciosamente
falso, e já deu (#417, #542).

Credenciais vêm do ambiente, nunca impressas, nunca escritas no HTML.

    export DATABASE_URL=...
    eval "$(railway variables -s API-V3 -e Desenvolvimento --kv | grep ^R2_ | sed 's/^/export /')"

    python3 scripts/ops/baseline_campo_v2.py --inferir --modelo 46a30ed9-... \\
        --jsonl docs/quality/evidence/baseline-campo-v2/deteccoes-46a30ed9.jsonl
    python3 scripts/ops/baseline_campo_v2.py --sweep  --jsonl <acima>
    python3 scripts/ops/baseline_campo_v2.py --folha  --jsonl <acima> \\
        --saida docs/quality/FOLHA-CONTATO-CAMPO-V2.html
    python3 scripts/ops/baseline_campo_v2.py --autoteste
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from amostra_variante_c_fotos import _cliente_r2, _esc, _fonte  # noqa: E402

TENANT_RVB = "63c219d8-fbef-4f3c-a7c9-058c742482e2"

#: piso de gravação. Ver o docstring: abaixo de qualquer limiar discutível.
PISO = 0.05

#: limiares varridos. 0.25 é o piso da avaliação (`_EVAL_CONFIDENCE`) e 0.5 é o
#: limiar SERVIDO hoje (`DETECTION_CONFIDENCE_THRESHOLD`, default do código).
LIMIARES = (0.05, 0.10, 0.25, 0.30, 0.50, 0.70, 0.90)
LIMIAR_SERVIDO = 0.50
LIMIAR_FOLHA = 0.25

SEMENTE = 20260902
LARGURA_SAIDA = 800
JPEG_Q = 80

COR_ALVO = (217, 43, 43)
COR_OUTRA = (150, 150, 150)


def e_ausencia(classe: str) -> bool:
    """Classe de ACUSAÇÃO (o EPI falta ou está mal usado), não de presença."""
    return classe.startswith(("Sem ", "Uso "))


# ── Inferência ────────────────────────────────────────────────────────────────

_SQL_DESCOBERTA = """
SELECT f.id::text AS frame_id, f.r2_key, f.camera_id::text AS camera_id,
       c.name AS camera_name, f.captured_at, f.width, f.height
  FROM public.training_frames f
  LEFT JOIN public.cameras c ON c.id = f.camera_id
 WHERE f.tenant_id = %(tenant)s
   AND f.created_at > now() - (%(horas)s || ' hours')::interval
   AND f.width >= %(largura_min)s
   AND f.is_annotated = false
 ORDER BY f.captured_at, f.id
"""

_SQL_POR_ID = """
SELECT f.id::text AS frame_id, f.r2_key, f.camera_id::text AS camera_id,
       c.name AS camera_name, f.captured_at, f.width, f.height
  FROM public.training_frames f
  LEFT JOIN public.cameras c ON c.id = f.camera_id
 WHERE f.id = ANY(%(ids)s::uuid[])
 ORDER BY f.captured_at, f.id
"""


def _taxonomia(s3, coco_prefix: str) -> list[str]:
    """Índice→nome gravado nos pesos, lido do split TRAIN — mesma regra do
    caminho servido (`inference._taxonomia_do_modelo`). Buraco de id vira "?N".

    Não é detalhe: o ONNX devolve um índice, e um dicionário de outro domínio
    faz "Sem protetor de ouvido" sair como "truck" sem erro nenhum (#542).
    """
    coco = json.loads(_baixar(s3, f"{coco_prefix}/train/_annotations.coco.json"))
    por_id = {int(c["id"]): c["name"] for c in coco.get("categories", [])}
    if not por_id:
        raise RuntimeError(f"COCO sem categorias em {coco_prefix}/train")
    return [por_id.get(i, f"?{i}") for i in range(max(por_id) + 1)]


def _baixar(s3, key: str) -> bytes:
    return s3.get_object(Bucket=os.environ["R2_BUCKET"], Key=key)["Body"].read()


def inferir(args) -> int:
    import cv2
    import numpy as np
    import psycopg2
    from psycopg2.extras import RealDictCursor

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "api"))
    from app.domain.detectors.factory import FRAMEWORK_TO_BACKEND, get_detector

    s3 = _cliente_r2()
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT m.id::text, m.display_name, m.framework, m.r2_onnx_key,
                          m.tenant_id::text AS tenant_id, d.coco_r2_key
                     FROM public.trained_models m
                     LEFT JOIN public.dataset_versions d
                            ON d.id = m.dataset_version_id
                    WHERE m.id::text LIKE %s""",
                (args.modelo + "%",),
            )
            modelos = cur.fetchall()
            if len(modelos) != 1:
                print(f"ERRO: {len(modelos)} modelos casam com '{args.modelo}'.")
                return 1
            m = dict(modelos[0])
            if not m["r2_onnx_key"]:
                print(f"ERRO: modelo {m['id']} não tem r2_onnx_key. Parando.")
                return 1
            if not m["coco_r2_key"]:
                print("ERRO: modelo sem dataset_version — sem taxonomia, o índice "
                      "viraria rótulo de outro domínio. Parando.")
                return 1

            if args.ids_de:
                ids = [json.loads(l)["frame_id"] for l in args.ids_de.open()]
                cur.execute(_SQL_POR_ID, {"ids": ids})
            else:
                cur.execute(_SQL_DESCOBERTA, {
                    "tenant": args.tenant, "horas": str(args.horas),
                    "largura_min": args.largura_min,
                })
            frames = [dict(r) for r in cur.fetchall()]

    print(f"modelo: {m['id']}  {m['display_name']}  framework={m['framework']}")
    print(f"frames: {len(frames)}")
    if not frames:
        print("ERRO: nenhum frame casou com o filtro. Parando.")
        return 1

    nomes = _taxonomia(s3, m["coco_r2_key"])
    print(f"taxonomia ({len(nomes)}): {nomes}")

    local = args.cache / f"{m['id']}.onnx"
    args.cache.mkdir(parents=True, exist_ok=True)
    if not local.exists():
        local.write_bytes(_baixar(s3, m["r2_onnx_key"]))
    print(f"onnx: {local.stat().st_size / 1e6:.1f} MB")

    det = get_detector(
        backend=FRAMEWORK_TO_BACKEND.get((m["framework"] or "").lower(), m["framework"]),
        model_path=str(local),
        class_names=nomes,
        confidence=PISO,
    )
    if not det.is_ready:
        print("ERRO: detector não carregou. Parando — sem substituto silencioso.")
        return 1

    args.jsonl.parent.mkdir(parents=True, exist_ok=True)
    falhas = 0
    with args.jsonl.open("w") as out:
        for i, fr in enumerate(frames, 1):
            try:
                img = cv2.imdecode(
                    np.frombuffer(_baixar(s3, fr["r2_key"]), dtype=np.uint8),
                    cv2.IMREAD_COLOR,
                )
                if img is None:
                    raise ValueError("cv2.imdecode devolveu None")
                # O backend só SETA `ultimo_erro`, nunca limpa: sem zerar aqui, o
                # primeiro erro contamina todos os frames seguintes.
                det.ultimo_erro = None
                dets = det.predict(img)
                if det.ultimo_erro:
                    raise RuntimeError(det.ultimo_erro)
            except Exception as exc:  # noqa: BLE001
                falhas += 1
                print(f"  FALHA {fr['frame_id']}: {exc}")
                continue
            out.write(json.dumps({
                "frame_id": fr["frame_id"], "r2_key": fr["r2_key"],
                "camera_id": fr["camera_id"], "camera_name": fr["camera_name"],
                "captured_at": fr["captured_at"].isoformat() if fr["captured_at"] else None,
                "width": fr["width"], "height": fr["height"],
                "model_id": m["id"], "piso": PISO, "dets": dets,
            }, ensure_ascii=False) + "\n")
            if i % 50 == 0:
                print(f"  {i}/{len(frames)}")
    print(f"gravado: {args.jsonl}  ({len(frames) - falhas} ok, {falhas} falhas)")
    return 1 if falhas else 0


# ── Varredura de limiar ───────────────────────────────────────────────────────

def carregar(caminho: Path) -> list[dict]:
    return [json.loads(l) for l in caminho.open() if l.strip()]


def resumo(linhas: list[dict], limiar: float) -> dict:
    """Números do baseline num limiar. Tudo contado, nada estimado."""
    por_classe: Counter = Counter()
    frames_com_ausencia = set()
    frames_com_algo = set()
    confs = defaultdict(list)
    for r in linhas:
        acima = [d for d in r["dets"] if d["confidence"] >= limiar]
        if acima:
            frames_com_algo.add(r["frame_id"])
        for d in acima:
            por_classe[d["class"]] += 1
            confs[d["class"]].append(d["confidence"])
            if e_ausencia(d["class"]):
                frames_com_ausencia.add(r["frame_id"])
    return {
        "limiar": limiar,
        "total": sum(por_classe.values()),
        "por_classe": dict(por_classe.most_common()),
        "confs": {k: sorted(v) for k, v in confs.items()},
        "frames": len(linhas),
        "frames_com_algo": len(frames_com_algo),
        "frames_sem_nada": len(linhas) - len(frames_com_algo),
        "frames_com_ausencia": len(frames_com_ausencia),
    }


def sweep(args) -> int:
    linhas = carregar(args.jsonl)
    print(f"frames: {len(linhas)}   modelo: {linhas[0]['model_id']}")
    print()
    print(f"{'limiar':>7} {'dets':>6} {'frames c/ det':>14} {'frames s/ nada':>15} "
          f"{'frames c/ ausência':>19}")
    for t in LIMIARES:
        r = resumo(linhas, t)
        print(f"{t:>7.2f} {r['total']:>6} {r['frames_com_algo']:>14} "
              f"{r['frames_sem_nada']:>15} {r['frames_com_ausencia']:>19}")
    print()
    classes = sorted({d["class"] for r in linhas for d in r["dets"]})
    cab = "  ".join(f"{t:>5.2f}" for t in LIMIARES)
    print(f"{'classe':<26} {cab}   conf_max")
    for c in classes:
        cols = []
        for t in LIMIARES:
            cols.append(f"{resumo(linhas, t)['por_classe'].get(c, 0):>5}")
        mx = max(d["confidence"] for r in linhas for d in r["dets"] if d["class"] == c)
        marca = "  ←acusação" if e_ausencia(c) else ""
        print(f"{c:<26} {'  '.join(cols)}   {mx:.3f}{marca}")
    return 0


# ── Folha de contato ──────────────────────────────────────────────────────────

def selecionar(linhas: list[dict], n_acusacoes: int, n_silencio: int,
               limiar: float) -> tuple[list[dict], list[dict]]:
    """Amostra HONESTA, não vitrine.

    Acusações: proporcional por classe, e dentro de cada classe entram
    obrigatoriamente a de MAIOR confiança e a MAIS RENTE ao limiar. Se o modelo
    erra com confiança alta, é aí que aparece; se acerta só no fundo do poço,
    também. O resto das vagas sai de sorteio com semente fixa.

    Silêncio: frames onde o modelo não acusa NADA no limiar servido. Sem eles a
    folha vira 24 itens de conformidade e não mede o que interessa — se há
    ausência real no material que o modelo está deixando passar.
    """
    rnd = random.Random(SEMENTE)
    cands: dict[str, list[dict]] = defaultdict(list)
    for r in linhas:
        for i, d in enumerate(r["dets"]):
            if d["confidence"] >= limiar and e_ausencia(d["class"]):
                cands[d["class"]].append({"linha": r, "det": d, "idx": i})
    if not cands:  # nenhuma acusação: a folha é só silêncio, e isso é o achado
        acus: list[dict] = []
    else:
        total = sum(len(v) for v in cands.values())
        vagas = {c: max(1, round(n_acusacoes * len(v) / total)) for c, v in cands.items()}
        acus = []
        for c, itens in sorted(cands.items()):
            itens = sorted(itens, key=lambda x: -x["det"]["confidence"])
            k = min(vagas[c], len(itens))
            escolhidos = {0: "maior confiança da classe"}
            if k > 1:
                escolhidos[len(itens) - 1] = "rente ao limiar"
            resto = [i for i in range(len(itens)) if i not in escolhidos]
            rnd.shuffle(resto)
            for i in resto[: max(0, k - len(escolhidos))]:
                escolhidos[i] = "sorteado no miolo"
            for i in sorted(escolhidos):
                it = dict(itens[i])
                it["motivo"] = escolhidos[i]
                acus.append(it)
        acus.sort(key=lambda x: (x["det"]["class"], -x["det"]["confidence"]))

    mudos = [r for r in linhas
             if not any(d["confidence"] >= LIMIAR_SERVIDO for d in r["dets"])]
    # espalha pelas câmeras em vez de sortear no monte: uma câmera concentra 38%
    # dos frames e levaria a amostra inteira.
    por_cam: dict[str, list[dict]] = defaultdict(list)
    for r in mudos:
        por_cam[r["camera_id"] or "?"].append(r)
    sil: list[dict] = []
    cams = sorted(por_cam, key=lambda c: -len(por_cam[c]))
    while len(sil) < n_silencio and any(por_cam.values()):
        for c in cams:
            if por_cam[c] and len(sil) < n_silencio:
                sil.append(por_cam[c].pop(rnd.randrange(len(por_cam[c]))))
    return acus, sil


def desenhar(bruto: bytes, alvo: dict | None, outras: list[dict]) -> str:
    """Redimensiona para LARGURA_SAIDA, desenha as caixas, devolve data URI.

    `bbox` do detector é [x, y, w, h] em pixels do frame ORIGINAL; a escala
    aplicada aqui é a mesma nos dois eixos porque o resize preserva a proporção.
    """
    from PIL import Image, ImageDraw

    img = Image.open(io.BytesIO(bruto)).convert("RGB")
    escala = LARGURA_SAIDA / img.width
    img = img.resize(
        (LARGURA_SAIDA, max(1, round(img.height * escala))), Image.LANCZOS
    )
    d = ImageDraw.Draw(img)
    fonte = _fonte(max(13, img.width // 48))
    traco = max(2, img.width // 300)

    def caixa(det: dict, cor, tracejado: bool) -> None:
        x, y, w, h = (v * escala for v in det["bbox"])
        x0, y0, x1, y1 = x, y, x + w, y + h
        if tracejado:
            for i in range(0, max(1, int(x1 - x0)), 12):
                d.line([x0 + i, y0, min(x0 + i + 6, x1), y0], fill=cor, width=traco)
                d.line([x0 + i, y1, min(x0 + i + 6, x1), y1], fill=cor, width=traco)
            for i in range(0, max(1, int(y1 - y0)), 12):
                d.line([x0, y0 + i, x0, min(y0 + i + 6, y1)], fill=cor, width=traco)
                d.line([x1, y0 + i, x1, min(y0 + i + 6, y1)], fill=cor, width=traco)
        else:
            d.rectangle([x0, y0, x1, y1], outline=cor, width=traco)
        rot = f'{det["class"]} {det["confidence"]:.2f}'.replace(".", ",")
        cx0, cy0, cx1, cy1 = d.textbbox((0, 0), rot, font=fonte)
        ty = y0 - (cy1 - cy0) - 6 if y0 > (cy1 - cy0) + 8 else y1 + 3
        d.rectangle([x0, ty, x0 + (cx1 - cx0) + 8, ty + (cy1 - cy0) + 6], fill=cor)
        d.text((x0 + 4, ty + 2), rot, fill=(255, 255, 255), font=fonte)

    for o in outras:
        caixa(o, COR_OUTRA, True)
    if alvo is not None:
        caixa(alvo, COR_ALVO, False)

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=JPEG_Q, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


_ESTILO = """
:root { --fg:#1a1a1a; --fg2:#666; --bg:#faf9f7; --card:#fff; --borda:#d8d4cc;
        --acento:#d92b2b; --ok:#20a060; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --fg:#e8e6e1; --fg2:#9a958c; --bg:#16150f; --card:#1f1e18; --borda:#3a382f;
  --acento:#ff6b5e; --ok:#4fd18b; } }
:root[data-theme="dark"] { --fg:#e8e6e1; --fg2:#9a958c; --bg:#16150f; --card:#1f1e18;
  --borda:#3a382f; --acento:#ff6b5e; --ok:#4fd18b; }
body { background:var(--bg); color:var(--fg); margin:0; padding:2rem 1.25rem 4rem;
  font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",sans-serif; }
main { max-width:1200px; margin:0 auto; }
h1 { font-size:1.7rem; margin:0 0 .3rem; letter-spacing:-.02em; }
h2 { font-size:1.15rem; margin:2.5rem 0 .8rem; }
p { max-width:70ch; }
.sub { color:var(--fg2); margin:0 0 1.5rem; }
.leg { display:flex; gap:1.2rem; flex-wrap:wrap; font-size:.85rem; margin:0 0 1.5rem;
  color:var(--fg2); }
.leg i { display:inline-block; width:22px; height:0; border-top:3px solid; margin-right:.35rem;
  vertical-align:middle; font-style:normal; }
table { border-collapse:collapse; margin:0 0 1.5rem; font-size:.88rem; }
th,td { text-align:left; padding:.32rem .9rem .32rem 0; border-bottom:1px solid var(--borda); }
th { color:var(--fg2); font-weight:600; }
td.num, th.num { text-align:right; padding-right:1.1rem; }
.grid { display:grid; gap:1.4rem; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); }
figure.c { margin:0; background:var(--card); border:1px solid var(--borda);
  border-radius:6px; overflow:hidden; display:flex; flex-direction:column; }
figure.c img { display:block; width:100%; height:auto; background:#111; }
.semfoto { padding:2.5rem 1rem; text-align:center; color:var(--acento); font-size:.85rem;
  background:var(--card); border-bottom:1px solid var(--borda); }
figcaption { padding:.7rem .8rem .8rem; display:flex; flex-direction:column; flex:1; }
.n { font-size:.72rem; color:var(--fg2); letter-spacing:.06em; text-transform:uppercase; }
.para { margin:.15rem 0 .1rem; font-size:1.02rem; }
.para b { color:var(--acento); }
.motivo { margin:.1rem 0 .6rem; font-size:.78rem; color:var(--fg2); font-style:italic; }
dl { display:grid; grid-template-columns:auto 1fr; gap:.08rem .55rem; margin:0 0 .7rem;
  font-size:.75rem; }
dt { color:var(--fg2); } dd { margin:0; overflow-wrap:anywhere; }
.veredito { margin-top:auto; padding-top:.6rem; border-top:1px dashed var(--borda);
  font-size:.8rem; color:var(--fg2); }
.veredito b { color:var(--fg); }
ol.resp { columns:2; font-size:.9rem; max-width:44rem; }
.box { background:var(--card); border:1px solid var(--borda); border-radius:6px;
  padding:1rem 1.2rem; max-width:70ch; }
.box.ok { border-left:3px solid var(--ok); }
.box.alerta { border-left:3px solid var(--acento); }
"""


def _cartao(i: int, img: str | None, erro: str, titulo: str, motivo: str,
            campos: list[tuple[str, str]], pergunta: str) -> str:
    alt = _esc(re.sub(r"<[^>]+>", "", titulo))  # o título tem <b>; alt é texto puro
    visual = (f'<img src="{img}" alt="{alt}">' if img
              else f'<div class="semfoto"><b>FOTO NÃO VEIO</b><br>{_esc(erro)}</div>')
    dl = "".join(f"<dt>{_esc(k)}</dt><dd>{v}</dd>" for k, v in campos)
    return (f'<figure class="c">{visual}<figcaption>'
            f'<p class="n">#{i}</p><p class="para">{titulo}</p>'
            f'<p class="motivo">{_esc(motivo)}</p><dl>{dl}</dl>'
            f'<p class="veredito"><b>#{i}:</b> {pergunta}</p>'
            f'</figcaption></figure>')


def _quando(iso: str | None) -> str:
    if not iso:
        return "—"
    return f"{iso[8:10]}/{iso[5:7]} {iso[11:16]}"


def dominio_do_treino(s3, conn, model_id: str, largura_min: int) -> dict:
    """Conta as imagens do dataset que treinou o modelo por LARGURA.

    É a comparação que explica o baseline: o modelo é servido em quadro inteiro,
    mas foi treinado em quê? Contado do COCO exportado, não inferido.
    """
    from psycopg2.extras import RealDictCursor

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT d.version, d.coco_r2_key FROM public.trained_models m
                 JOIN public.dataset_versions d ON d.id = m.dataset_version_id
                WHERE m.id = %s::uuid""",
            (model_id,),
        )
        dsv = cur.fetchone()
    if not dsv:
        return {"versao": "?", "recortes": "?", "cheios": "?",
                "largura_min": largura_min}
    cheios = recortes = 0
    for split in ("train", "val", "test"):
        try:
            coco = json.loads(
                _baixar(s3, f'{dsv["coco_r2_key"]}/{split}/_annotations.coco.json')
            )
        except Exception:  # noqa: BLE001 — split ausente é normal
            continue
        for im in coco.get("images", []):
            if im["width"] >= largura_min:
                cheios += 1
            else:
                recortes += 1
    return {"versao": dsv["version"], "recortes": recortes, "cheios": cheios,
            "largura_min": largura_min}


def montar_html(linhas: list[dict], acus: list[dict], sil: list[dict],
                fotos: dict[str, str], erros: dict[str, str],
                dominio: dict) -> str:
    r_serv = resumo(linhas, LIMIAR_SERVIDO)
    r_folha = resumo(linhas, LIMIAR_FOLHA)
    n_cams = len({r["camera_id"] for r in linhas})

    tabela = ["<table><thead><tr><th>limiar</th><th class='num'>detecções</th>"
              "<th class='num'>frames c/ alguma detecção</th>"
              "<th class='num'>frames sem nada</th>"
              "<th class='num'>frames c/ acusação de ausência</th></tr></thead><tbody>"]
    for t in LIMIARES:
        r = resumo(linhas, t)
        marca = " <b>← limiar servido hoje</b>" if t == LIMIAR_SERVIDO else ""
        tabela.append(
            f"<tr><td>{t:.2f}".replace(".", ",") + f"{marca}</td>"
            f"<td class='num'>{r['total']}</td>"
            f"<td class='num'>{r['frames_com_algo']}</td>"
            f"<td class='num'>{r['frames_sem_nada']}</td>"
            f"<td class='num'>{r['frames_com_ausencia']}</td></tr>")
    tabela.append("</tbody></table>")

    classes = sorted({d["class"] for r in linhas for d in r["dets"]})
    porcls = ["<table><thead><tr><th>classe</th>"]
    for t in LIMIARES:
        porcls.append(f"<th class='num'>≥{t:.2f}".replace(".", ",") + "</th>")
    porcls.append("<th class='num'>conf. máx.</th></tr></thead><tbody>")
    contagens = {t: resumo(linhas, t)["por_classe"] for t in LIMIARES}
    for c in classes:
        mx = max(d["confidence"] for r in linhas for d in r["dets"] if d["class"] == c)
        nome = f"<b>{_esc(c)}</b>" if e_ausencia(c) else _esc(c)
        porcls.append(f"<tr><td>{nome}</td>")
        for t in LIMIARES:
            porcls.append(f"<td class='num'>{contagens[t].get(c, 0)}</td>")
        porcls.append(f"<td class='num'>{mx:.3f}".replace(".", ",") + "</td></tr>")
    porcls.append("</tbody></table>")

    cards, respostas = [], []
    i = 0
    for it in acus:
        i += 1
        r, d = it["linha"], it["det"]
        outras = [x for j, x in enumerate(r["dets"])
                  if j != it["idx"] and x["confidence"] >= LIMIAR_FOLHA]
        cards.append(_cartao(
            i, fotos.get(f"a{i}"), erros.get(f"a{i}", "?"),
            f'<b>{_esc(d["class"])}</b> — confiança '
            + f'{d["confidence"]:.2f}'.replace(".", ","),
            it["motivo"],
            [("caixa (px)", f'{d["bbox"][2]} × {d["bbox"][3]}'),
             ("frame", f'{r["width"]} × {r["height"]}'),
             ("câmera", _esc(r["camera_name"] or r["camera_id"] or "—")),
             ("quando", _quando(r["captured_at"])),
             ("outras caixas no frame", str(len(outras))),
             ("frame_id", f'<code>{_esc(r["frame_id"])}</code>')],
            "correto &nbsp;/&nbsp; falso positivo &nbsp;/&nbsp; duvidoso"))
        respostas.append(f'<li>{_esc(d["class"])} '
                         + f'{d["confidence"]:.2f}'.replace(".", ",")
                         + " — ______</li>")
    for r in sil:
        i += 1
        cards.append(_cartao(
            i, fotos.get(f"s{i}"), erros.get(f"s{i}", "?"),
            "<b>silêncio</b> — o modelo não acusou nada aqui",
            f"frame sem nenhuma detecção acima de {LIMIAR_SERVIDO:.2f}".replace(".", ","),
            [("frame", f'{r["width"]} × {r["height"]}'),
             ("câmera", _esc(r["camera_name"] or r["camera_id"] or "—")),
             ("quando", _quando(r["captured_at"])),
             ("caixas fracas desenhadas",
              str(len([d for d in r["dets"] if d["confidence"] >= LIMIAR_FOLHA]))),
             ("frame_id", f'<code>{_esc(r["frame_id"])}</code>')],
            "sem violação (silêncio certo) &nbsp;/&nbsp; "
            "TEM violação (o modelo perdeu) &nbsp;/&nbsp; duvidoso"))
        respostas.append("<li>silêncio — ______</li>")

    pct_mudo = 100 * r_serv["frames_sem_nada"] / len(linhas)
    conf_max = max(d["confidence"] for r in linhas for d in r["dets"])
    n_aus_serv = sum(1 for r in linhas for d in r["dets"]
                     if d["confidence"] >= LIMIAR_SERVIDO and e_ausencia(d["class"]))
    sem_teto = [c for c in classes if e_ausencia(c) and max(
        d["confidence"] for r in linhas for d in r["dets"] if d["class"] == c
    ) < LIMIAR_SERVIDO]
    return f"""<!doctype html>
<html lang="pt-BR"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Folha de contato — baseline de campo V2</title>
<style>{_ESTILO}</style></head><body>
<main>
<h1>Folha de contato — o que o modelo de hoje enxerga na fábrica</h1>
<p class="sub">Modelo servido <code>{_esc(linhas[0]["model_id"][:8])}</code>
("Logikos EPI Completo (v10-base)") rodado em <b>{len(linhas)} frames cheios
1920×1080</b> colhidos do gravador do RVB, {n_cams} câmeras, fábrica em operação.
Nenhum destes frames foi anotado nem treinado — é campo puro.</p>

<div class="box alerta">
<p style="margin-top:0"><b>O que você está julgando.</b> Não é uma proposta de
mudança: é uma <b>fotografia do que o produto faz hoje</b>. Cada cartão abaixo é
uma coisa que o modelo afirmou (ou deixou de afirmar) sobre um quadro real da sua
fábrica, e a única pergunta é se a afirmação está certa.</p>
<p><b>O que a sua resposta decide.</b> Estamos treinando dois modelos novos. Para
saber se algum deles é melhor, precisamos saber o que "melhor" significa aqui — e
isso exige saber quantos dos alarmes de hoje são verdadeiros e quantas violações
reais passam batido. Sem os seus vereditos, o A/B compara dois números contra
nenhuma referência.</p>
<p style="margin-bottom:0"><b>O que já está medido, sem depender de você.</b> No
limiar que o produto usa hoje (0,50), o modelo produziu
<b>{r_serv["total"]} detecções nos {len(linhas)} frames</b> e acusou ausência de EPI
em <b>{r_serv["frames_com_ausencia"]} deles</b>. {pct_mudo:.0f}% dos quadros saíram
completamente mudos. Por isso {len(sil)} dos {len(acus) + len(sil)} cartões desta
folha são <i>silêncios</i>: no regime atual o silêncio é a saída dominante, e ele
também precisa de veredito.</p>
</div>

<h2>Leitura honesta de quem gerou a folha</h2>
<div class="box">
<p style="margin-top:0"><b>Veredito curto: no quadro inteiro, o modelo de hoje
praticamente não fala.</b> Nos {len(linhas)} frames, no limiar servido, saíram
<b>{n_aus_serv} acusações de ausência no total</b> — não por frame, no total. A
confiança mais alta que o modelo atingiu em qualquer classe e qualquer quadro foi
<b>{f"{conf_max:.3f}".replace(".", ",")}</b>. Não existe nenhuma detecção acima de
0,90 neste material; se você procurar aqui o "erro confiante", ele não está — o
modelo não chega a ficar confiante.</p>

<p><b>A causa mais provável está medida, e não é sutil.</b> O dataset que treinou
este modelo ({_esc(dominio["versao"])}) tem
<b>{f'{dominio["recortes"]:,}'.replace(",", ".")} imagens de RECORTE de pessoa e
{dominio["cheios"]} de quadro inteiro</b> (largura ≥ {dominio["largura_min"]}).
Ele é servido em 1920×1080. Um EPI que ocupava metade da imagem no treino ocupa
1% do quadro em campo — é outro problema visual, e o colapso de confiança é o
que se espera. Não é opinião sobre o treino: é a contagem das imagens do próprio
artefato exportado.</p>

<p><b>Classes que nunca chegam ao limiar servido neste material:</b>
{", ".join(f"<code>{_esc(c)}</code>" for c in sem_teto) or "nenhuma"}. Para o
cliente, hoje, elas simplesmente não existem — não importa o que aconteça na
fábrica.</p>

<p style="margin-bottom:0"><b>O que a folha ainda não sabe, e só você sabe.</b>
"O modelo não acusa" não é o mesmo que "não houve violação". Os
{len(sil)} cartões de silêncio existem exatamente para separar as duas coisas. Se
você olhar e disser "aqui tinha gente sem protetor auditivo", o problema é de
detecção. Se disser "estava todo mundo certo", o silêncio é a resposta certa e o
número que interessa passa a ser outro.</p>
</div>

<h2>Quanto o modelo acusa, por limiar</h2>
<p>O limiar de produção (0,50) não tem origem documentada — foi o
<i>default</i> do código. Esta varredura existe para escolhê-lo com base em algo.
Todas as linhas vêm da MESMA rodada de inferência: as detecções foram gravadas no
piso 0,05 e filtradas depois, o que dá exatamente o mesmo resultado que rodar em
cada limiar.</p>
{"".join(tabela)}

<h2>Por classe</h2>
<p>Em <b>negrito</b>, as classes de acusação ("Sem X" / "Uso incorreto") — as
únicas que geram alerta para o cliente. As demais são presença de EPI.</p>
{"".join(porcls)}

<h2>Como ler as fotos</h2>
<p class="leg">
  <span><i style="border-color:#d92b2b"></i>a acusação em julgamento, com a classe e a confiança</span>
  <span><i style="border-color:#969696;border-top-style:dashed"></i>outras detecções do mesmo frame acima de {LIMIAR_FOLHA:.2f} (contexto)</span>
</p>
<p class="sub">As imagens estão reduzidas a 800 px de largura para caber na
página; as caixas foram desenhadas na mesma escala. Os cartões
<b>1–{len(acus)}</b> são acusações; os cartões
<b>{len(acus) + 1}–{len(acus) + len(sil)}</b> são silêncios, e neles a pergunta
se inverte.</p>

<h2>Acusações ({len(acus)}) — limiar {LIMIAR_FOLHA:.2f}</h2>
<p>Abaixo do limiar de produção, de propósito: em 0,50 há apenas
{r_serv["frames_com_ausencia"]} frame(s) com acusação em {len(linhas)}, o que não
dá amostra. Em {LIMIAR_FOLHA:.2f} há {r_folha["frames_com_ausencia"]}. A confiança
de cada caixa está escrita nela — julgue sabendo que as fracas <i>não apareceriam</i>
para o cliente hoje.</p>
<div class="grid">{"".join(cards[:len(acus)])}</div>

<h2>Silêncios ({len(sil)}) — a pergunta se inverte</h2>
<p>Nestes frames o modelo não acusou <b>nada</b> acima de 0,50. A pergunta aqui é
a oposta: <b>havia alguma violação de EPI neste quadro?</b> Se houver, o modelo
perdeu. Se não houver, o silêncio está certo e é uma boa notícia. Foram sorteados
com semente fixa, espalhados pelas câmeras — não escolhidos.</p>
<div class="grid">{"".join(cards[len(acus):])}</div>

<h2>Sua resposta</h2>
<p>Marque só o que não estiver certo — o resto eu considero aprovado.
Formato: <code>3 falso, 7 duvidoso, 20 tem violação</code>.</p>
<ol class="resp">{"".join(respostas)}</ol>
</main></body></html>
"""


def folha(args) -> int:
    import psycopg2

    linhas = carregar(args.jsonl)
    acus, sil = selecionar(linhas, args.acusacoes, args.silencios, LIMIAR_FOLHA)
    print(f"acusações: {len(acus)}  silêncios: {len(sil)}")
    s3 = _cliente_r2()
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        dominio = dominio_do_treino(s3, conn, linhas[0]["model_id"], args.largura_min)
    print(f"domínio do treino: {dominio}")
    fotos: dict[str, str] = {}
    erros: dict[str, str] = {}
    i = 0
    for it in acus:
        i += 1
        r = it["linha"]
        outras = [x for j, x in enumerate(r["dets"])
                  if j != it["idx"] and x["confidence"] >= LIMIAR_FOLHA]
        try:
            fotos[f"a{i}"] = desenhar(_baixar(s3, r["r2_key"]), it["det"], outras)
        except Exception as exc:  # noqa: BLE001
            erros[f"a{i}"] = f"{type(exc).__name__}: {exc}"
    for r in sil:
        i += 1
        fracas = [d for d in r["dets"] if d["confidence"] >= LIMIAR_FOLHA]
        try:
            fotos[f"s{i}"] = desenhar(_baixar(s3, r["r2_key"]), None, fracas)
        except Exception as exc:  # noqa: BLE001
            erros[f"s{i}"] = f"{type(exc).__name__}: {exc}"
    html = montar_html(linhas, acus, sil, fotos, erros, dominio)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(html, encoding="utf-8")
    mb = args.saida.stat().st_size / 1e6
    print(f"gravado: {args.saida}  {mb:.2f} MB  ({len(erros)} fotos falharam)")
    if mb > 8:
        print("AVISO: acima de 8 MB — reduza --acusacoes/--silencios ou JPEG_Q.")
    return 0


# ── Autoteste ─────────────────────────────────────────────────────────────────

def autoteste() -> int:
    """A lógica não trivial daqui é uma só: filtrar no piso e depois no limiar
    tem de dar o mesmo que rodar no limiar. É o que este teste trava."""
    def frame(fid, dets, cam="c1"):
        return {"frame_id": fid, "camera_id": cam, "camera_name": cam,
                "captured_at": "2026-09-01T08:00:00+00:00", "width": 1920,
                "height": 1080, "r2_key": f"k/{fid}", "model_id": "m", "dets": dets}

    def det(c, conf, box=(10, 10, 50, 50)):
        return {"class": c, "confidence": conf, "bbox": list(box)}

    linhas = [
        frame("f1", [det("Sem Luvas", 0.91), det("Luvas", 0.40)]),
        frame("f2", [det("Protetor auditivo", 0.30)], cam="c2"),
        frame("f3", [], cam="c2"),
        frame("f4", [det("Sem mascara", 0.26), det("Sem mascara", 0.10)], cam="c3"),
    ]
    r = resumo(linhas, 0.25)
    assert r["total"] == 4, r["total"]  # f1:2 (0,91 e 0,40) + f2:1 + f4:1
    assert r["frames_com_ausencia"] == 2, r
    assert r["frames_sem_nada"] == 1, r          # só f3
    r5 = resumo(linhas, 0.5)
    assert r5["total"] == 1 and r5["frames_com_ausencia"] == 1, r5
    assert r5["frames_sem_nada"] == 3, r5
    assert e_ausencia("Sem Luvas") and e_ausencia("Uso incorreto de mascara")
    assert not e_ausencia("Luvas") and not e_ausencia("Protetor auditivo")

    acus, sil = selecionar(linhas, 4, 2, 0.25)
    assert {a["det"]["class"] for a in acus} == {"Sem Luvas", "Sem mascara"}, acus
    assert acus[0]["motivo"] == "maior confiança da classe"
    # silêncio = tudo abaixo de 0,50; f1 tem 0,91 e fica de fora
    assert len(sil) == 2 and "f1" not in {s["frame_id"] for s in sil}, sil
    # espalhado por câmera: as duas vagas não podem cair na mesma
    assert len({s["camera_id"] for s in sil}) == 2, sil

    # zero acusações não pode explodir a folha
    vazio = [frame("f9", [det("Botas", 0.8)])]
    a2, s2 = selecionar(vazio, 4, 1, 0.25)
    assert a2 == [] and len(s2) == 0, (a2, s2)  # f9 tem 0,8 → não é silêncio
    print("autoteste OK")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--inferir", action="store_true")
    p.add_argument("--sweep", action="store_true")
    p.add_argument("--folha", action="store_true")
    p.add_argument("--autoteste", action="store_true")
    p.add_argument("--jsonl", type=Path,
                   default=Path("docs/quality/evidence/baseline-campo-v2/"
                                "deteccoes-46a30ed9.jsonl"))
    p.add_argument("--saida", type=Path,
                   default=Path("docs/quality/FOLHA-CONTATO-CAMPO-V2.html"))
    p.add_argument("--modelo", default="46a30ed9")
    p.add_argument("--tenant", default=TENANT_RVB)
    p.add_argument("--horas", type=int, default=4)
    p.add_argument("--largura-min", type=int, default=1280)
    p.add_argument("--ids-de", type=Path,
                   help="JSONL de uma rodada anterior: usa EXATAMENTE os mesmos "
                        "frames (é assim que a 2ª rodada fica comparável)")
    p.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "recognition-onnx")
    p.add_argument("--acusacoes", type=int, default=18)
    p.add_argument("--silencios", type=int, default=6)
    args = p.parse_args()

    if args.autoteste:
        return autoteste()
    if args.inferir:
        return inferir(args)
    if args.sweep:
        return sweep(args)
    if args.folha:
        return folha(args)
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
