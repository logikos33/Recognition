#!/usr/bin/env python3
"""
Recognition — search_content.py (runner SELF-CONTAINED da instância RunPod).

Roda NA GPU remota — ZERO imports do repositório (embutido no onstart via
heredoc por `app/infrastructure/queue/tasks/search.py::
_read_search_executor_source`, mesmo padrão de `training/propagate_
seeded.py`/`training/vast/remote_train.py`). Só stdlib no import-time;
torch/Pillow/transformers são instalados via pip EM RUNTIME no pod — NUNCA
ultralytics (AGPL, fora do caminho servido e fora do caminho de treino,
ADR-0043/task "treino não pode mentir"; `scripts/check_license_gate.py`
varre este diretório por import).

Busca por conteúdo — open-vocabulary, sem sementes humanas (ao contrário da
propagação semeada): cada termo de busca (`{label, query}` — `query` é o
texto em INGLÊS passado ao modelo, `label` é o rótulo exibido/promovido) é
rodado contra CADA frame selecionado via **OWLv2 zero-shot object
detection** (checkpoint `google/owlv2-base-patch16-ensemble`, Apache 2.0 —
ver `docs/WEIGHTS_LICENSES.md`). O resultado é um ACHADO (inventário de
"onde este termo aparece"), não uma proposta de anotação — só vira
`pre_annotations` pendente via promoção manual no backend
(`search_handlers.py::promote_search_findings_handler`).

Pipeline:
  1. baixa o manifesto (MANIFEST_URL, presigned GET) — termos e frames
     (frame_id + imagem presigned), sem sementes/pool;
  2. instala deps (torch, Pillow, transformers) e carrega OWLv2 —
     `revision` PINADA (commit HF imutável, ver `_OWLV2_REVISION`) em vez
     de `sha256` de um arquivo único: `from_pretrained(..., revision=...)`
     resolve VÁRIOS arquivos do repositório HF, então a integridade vem do
     commit pinado (imutável), não de um hash de arquivo isolado — mesmo
     espírito de fail-closed do `download_and_verify_weight` da
     propagação, adaptado ao mecanismo de download do `transformers`;
  3. por frame: roda TODAS as queries de uma vez (batch de texto OWLv2),
     limiar de confiança via env (CONFIDENCE_THRESHOLD, default 0.15 —
     scores do OWLv2 são tipicamente mais baixos que detectores supervisionados),
     mantém as top-N detecções por termo (`_MAX_DETECTIONS_PER_TERM`, evita
     inundar o resultado com dezenas de caixas quase-duplicadas — OWLv2 não
     aplica NMS por padrão no post-processing);
  4. progresso via callback a cada PROGRESS_EVERY_N frames; resultado final
     (achados — JSON pequeno) via callback, sem upload pro R2 (mesmo desenho
     da propagação: o payload do callback final É o resultado, validado
     pelo backend em `search_handlers.py::search_callback_handler` antes de
     gravar em `search_jobs.results`).

Contrato (tudo via env, injetado pelo dispatch —
`app/infrastructure/queue/tasks/search.py::dispatch_search`):
  MANIFEST_URL           presigned GET do manifesto JSON (termos+frames)
  CALLBACK_URL            POST .../search/jobs/<id>/callback
  CALLBACK_TOKEN           header X-Callback-Token (token por-job, revogável)
  CONFIDENCE_THRESHOLD      float, default 0.15
  PROGRESS_EVERY_N           int, default 20

Em erro (manifesto ausente/vazio, sem termos, sem frames, etc.): POST
{status:'failed', error_message} e exit 1 — nunca 'completed' sem achados
verificáveis pelo backend.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from io import BytesIO
from typing import Any

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("search_content")

MANIFEST_URL = os.environ.get("MANIFEST_URL", "")
CALLBACK_URL = os.environ.get("CALLBACK_URL", "")
CALLBACK_TOKEN = os.environ.get("CALLBACK_TOKEN", "")
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.15"))
PROGRESS_EVERY_N = int(os.environ.get("PROGRESS_EVERY_N", "20"))

# HF Apache 2.0, commit IMUTÁVEL pinado (não "main" — main pode mudar sob
# nós). Confirmado Apache-2.0 + sha do commit via
# https://huggingface.co/api/models/google/owlv2-base-patch16-ensemble em
# 2026-08-11 — ver docs/WEIGHTS_LICENSES.md.
OWLV2_MODEL_ID = "google/owlv2-base-patch16-ensemble"
OWLV2_REVISION = "cfd3195ba4ea9592eec887ded089f4c08eff231d"

_MAX_DETECTIONS_PER_TERM = 5  # top-N por termo/frame — evita inundar de caixas quase-duplicadas


# --------------------------------------------------------------------- http

def post_callback(payload: dict) -> None:
    """POSTa progresso/resultado no backend. Best-effort — o job não morre
    por causa de rede (mesmo padrão de propagate_seeded.py)."""
    if not CALLBACK_URL:
        return
    try:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(  # noqa: S310
            CALLBACK_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Callback-Token": CALLBACK_TOKEN,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            resp.read()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.warning("callback_failed: %s", exc)


def download_json(url: str, timeout: int = 60) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read())


def download_bytes(url: str, timeout: int = 60) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def pip_install(*packages: str) -> None:
    logger.info("pip install %s", " ".join(packages))
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pip", "install", "-q", *packages],
        check=True,
        text=True,
    )


# ------------------------------------------------------------- pure matching
#
# Tudo abaixo desta seção (até "GPU pipeline") é PURO — só stdlib — de
# propósito: testável em CI sem instalar nenhuma dependência de ML (ver
# training/test_search_content.py). O caminho GPU real (load_owlv2,
# run_owlv2_on_frame) importa torch/PIL/transformers só dentro das próprias
# funções (lazy import — mesmo padrão de propagate_seeded.py), nunca no
# top-level do módulo.

def xyxy_to_normalized_cxcywh(
    box_xyxy: tuple[float, float, float, float], img_w: int, img_h: int
) -> tuple[float, float, float, float]:
    """Converte bbox absoluto (x0, y0, x1, y1 — saída do post-processing do
    OWLv2/HF) pra (cx, cy, w, h) normalizado [0,1] — formato consumido por
    `pre_annotations`/`search_jobs.results` (mesmo shape de
    `propagate_seeded.py::mask_bbox_to_normalized`, adaptado de xywh pra
    xyxy de entrada)."""
    x0, y0, x1, y1 = box_xyxy
    if img_w <= 0 or img_h <= 0:
        raise ValueError("dimensões de imagem inválidas (img_w/img_h <= 0)")
    w = max(0.0, x1 - x0)
    h = max(0.0, y1 - y0)
    cx = (x0 + w / 2.0) / img_w
    cy = (y0 + h / 2.0) / img_h
    nw = w / img_w
    nh = h / img_h
    return (
        max(0.0, min(1.0, cx)),
        max(0.0, min(1.0, cy)),
        max(0.01, min(1.0, nw)),
        max(0.01, min(1.0, nh)),
    )


def top_k_by_score(
    detections: list[dict[str, Any]], k: int
) -> list[dict[str, Any]]:
    """Mantém só as top-k detecções (por `score`, desc) — cada item precisa
    ter uma chave `score`. `k<=0` ou lista menor que `k`: retorna ordenado
    sem cortar. Desempate determinístico não é necessário aqui (score de
    modelo raramente empata exatamente; se empatar, `sorted` é estável —
    preserva a ordem original de geração)."""
    ordered = sorted(detections, key=lambda d: -float(d["score"]))
    if k <= 0:
        return ordered
    return ordered[:k]


def build_finding(
    frame_id: str, term: dict[str, str], score: float,
    bbox_cxcywh: tuple[float, float, float, float],
) -> dict[str, Any]:
    """Shape EXATO validado por
    `search_handlers.py::_validate_completed_findings`:
    `{frame_id, term, label, bbox: [cx,cy,w,h], confidence}` — `term` é o
    `query` literal do termo (o texto em inglês que produziu o achado,
    conferido contra `search_jobs.terms` no backend), `label` é o rótulo
    exibido/promovido."""
    cx, cy, w, h = bbox_cxcywh
    return {
        "frame_id": frame_id,
        "term": term["query"],
        "label": term["label"],
        "bbox": [round(cx, 6), round(cy, 6), round(w, 6), round(h, 6)],
        "confidence": round(float(score), 4),
    }


# --------------------------------------------------------------- GPU pipeline

def load_owlv2():
    """Processor + modelo OWLv2 — `revision` PINADA (commit imutável, ver
    docstring do módulo). `from_pretrained` baixa e cacheia os arquivos do
    repositório HF; sem verificação manual de sha256 (não há um arquivo
    único pra hashear como no fluxo de propagação) — a integridade vem do
    commit pinado, nunca resolvido a partir de `main`."""
    import torch  # noqa: PLC0415
    from transformers import Owlv2ForObjectDetection, Owlv2Processor  # noqa: PLC0415

    processor = Owlv2Processor.from_pretrained(OWLV2_MODEL_ID, revision=OWLV2_REVISION)
    model = Owlv2ForObjectDetection.from_pretrained(OWLV2_MODEL_ID, revision=OWLV2_REVISION)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()
    return processor, model, device


def run_owlv2_on_frame(
    processor, model, device, image, terms: list[dict[str, str]], threshold: float,
) -> list[dict[str, Any]]:
    """Roda TODAS as queries de `terms` de uma vez contra `image` (PIL) —
    batch de texto OWLv2, uma imagem. Retorna detecções cruas (antes do
    top-k): `[{term_index, score, box_xyxy}]`. `results[0]["labels"]` são
    índices em `texts[0]` (a MESMA ordem de `terms`) — mapeamento direto,
    sem heurística de texto (mesmo espírito de "class_name literal, nunca
    inventado" da propagação semeada)."""
    import torch  # noqa: PLC0415

    texts = [[term["query"] for term in terms]]
    inputs = processor(text=texts, images=image, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)

    target_sizes = torch.tensor([image.size[::-1]], device=device)
    processed = processor.post_process_object_detection(
        outputs=outputs, threshold=threshold, target_sizes=target_sizes,
    )[0]

    detections: list[dict[str, Any]] = []
    boxes = processed["boxes"].tolist()
    scores = processed["scores"].tolist()
    labels = processed["labels"].tolist()
    for box, score, term_index in zip(boxes, scores, labels, strict=True):
        detections.append({
            "term_index": int(term_index),
            "score": float(score),
            "box_xyxy": tuple(box),
        })
    return detections


def download_image(url: str):
    """Baixa e decodifica uma imagem (PIL) — lazy import."""
    from PIL import Image  # noqa: PLC0415

    data = download_bytes(url)
    return Image.open(BytesIO(data)).convert("RGB")


def build_frame_findings(
    processor, model, device, frame_id: str, image, terms: list[dict[str, str]],
    threshold: float,
) -> list[dict[str, Any]]:
    """Detecções cruas de `run_owlv2_on_frame` → achados normalizados,
    agrupados por termo e cortados nas top-`_MAX_DETECTIONS_PER_TERM`."""
    img_w, img_h = image.size
    raw = run_owlv2_on_frame(processor, model, device, image, terms, threshold)

    by_term: dict[int, list[dict[str, Any]]] = {}
    for det in raw:
        by_term.setdefault(det["term_index"], []).append(det)

    findings: list[dict[str, Any]] = []
    for term_index, dets in by_term.items():
        if not (0 <= term_index < len(terms)):
            continue  # defensivo — nunca deveria acontecer (post-processing do HF)
        term = terms[term_index]
        for det in top_k_by_score(dets, _MAX_DETECTIONS_PER_TERM):
            bbox_norm = xyxy_to_normalized_cxcywh(det["box_xyxy"], img_w, img_h)
            findings.append(build_finding(frame_id, term, det["score"], bbox_norm))
    return findings


# --------------------------------------------------------------------- main

def main() -> int:
    post_callback({"status": "running", "progress": 1, "metrics": {"stage": "manifest"}})
    if not MANIFEST_URL:
        raise RuntimeError("MANIFEST_URL não definido")
    manifest = download_json(MANIFEST_URL)
    terms = manifest.get("terms") or []
    frames = manifest.get("frames") or []
    if not terms:
        raise RuntimeError("manifesto sem termos — nada pra buscar")
    if not frames:
        raise RuntimeError("manifesto sem frames — nada pra processar")

    post_callback({"status": "running", "progress": 3, "metrics": {"stage": "deps"}})
    pip_install("torch", "pillow", "transformers>=4.44.0", "accelerate")

    post_callback({"status": "running", "progress": 8, "metrics": {"stage": "model"}})
    processor, model, device = load_owlv2()

    all_findings: list[dict[str, Any]] = []
    total = len(frames)
    for i, item in enumerate(frames, start=1):
        frame_id = str(item["frame_id"])
        try:
            image = download_image(item["image_url"])
            findings = build_frame_findings(
                processor, model, device, frame_id, image, terms, CONFIDENCE_THRESHOLD,
            )
        except Exception as exc:  # noqa: BLE001 — um frame ruim não derruba o job inteiro
            logger.warning("frame_failed: frame=%s err=%s", frame_id, exc)
            findings = []
        all_findings.extend(findings)

        if i % PROGRESS_EVERY_N == 0 or i == total:
            progress = min(95, 10 + int(85 * i / max(total, 1)))
            post_callback({
                "status": "running",
                "progress": progress,
                "metrics": {
                    "stage": "searching",
                    "frames_processed": i,
                    "frames_total": total,
                    "findings_so_far": len(all_findings),
                },
            })

    post_callback({
        "status": "completed",
        "progress": 100,
        "findings": all_findings,
        "metrics": {
            "stage": "done",
            "frames_total": total,
            "frames_processed": total,
            "findings_count": len(all_findings),
            "terms_searched": [t["label"] for t in terms],
        },
    })
    logger.info(
        "search_content_completed: frames=%d findings=%d", total, len(all_findings),
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — reporta QUALQUER falha ao backend
        logger.exception("search_content_failed")
        post_callback({"status": "failed", "error_message": str(exc)[:500]})
        sys.exit(1)
