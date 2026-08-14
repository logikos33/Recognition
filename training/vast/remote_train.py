#!/usr/bin/env python3
"""
Recognition — remote_train.py (runner SELF-CONTAINED da instância Vast.ai).

Roda NA GPU remota — ZERO imports do repositório (é embutido no onstart via
heredoc por tasks/training.py::_build_vast_onstart). Só stdlib + frameworks
instalados via pip em runtime (RF-DETR/YOLOX — Apache 2.0; onnxruntime — MIT).

Contrato (tudo via env, injetado pelo dispatch):
  DATASET_URL          presigned GET do zip COCO da dataset_version
  FRAMEWORK            rfdetr | yolox (default rfdetr)
  EPOCHS               int (default 50)
  BATCH                int (default 4)
  IMGSZ                int (default 560 — múltiplo de 56, padrão RF-DETR)
  CALLBACK_URL         POST /api/v1/training/jobs/<id>/progress-callback
  CALLBACK_TOKEN       header X-Callback-Token (token por-job, revogável)
  UPLOAD_URL_ONNX      presigned PUT do model.onnx
  UPLOAD_URL_WEIGHTS   presigned PUT dos pesos (.pth)
  UPLOAD_URL_METRICS   presigned PUT do metrics.json
  R2_ONNX_KEY          chave R2 final do ONNX (ecoada no callback final)

Fluxo:
  1. baixa e extrai o dataset COCO (train/valid[/test] + _annotations.coco.json)
  2. pip install do framework (runbook TRAINING_PIPELINE_WEEKEND_MVP.md)
  3. treina; POSTa progresso {progress, epoch, metrics} a cada época
  4. exporta ONNX e valida com onnxruntime (session + dummy input)
  5. sobe artefatos via PUT presigned
  6. POST final {status, progress, metrics, r2_onnx_key}
Em erro: POST {status: 'failed', error_message} e exit 1.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("remote_train")

DATASET_URL = os.environ.get("DATASET_URL", "")
FRAMEWORK = os.environ.get("FRAMEWORK", "rfdetr").strip().lower()
EPOCHS = int(os.environ.get("EPOCHS", "50"))
BATCH = int(os.environ.get("BATCH", "4"))
IMGSZ = int(os.environ.get("IMGSZ", "560"))
CALLBACK_URL = os.environ.get("CALLBACK_URL", "")
CALLBACK_TOKEN = os.environ.get("CALLBACK_TOKEN", "")
UPLOAD_URL_ONNX = os.environ.get("UPLOAD_URL_ONNX", "")
UPLOAD_URL_WEIGHTS = os.environ.get("UPLOAD_URL_WEIGHTS", "")
UPLOAD_URL_METRICS = os.environ.get("UPLOAD_URL_METRICS", "")
R2_ONNX_KEY = os.environ.get("R2_ONNX_KEY", "")

WORK_DIR = Path("/root")
DATASET_DIR = WORK_DIR / "dataset_coco"
OUTPUT_DIR = WORK_DIR / "train_output"

_METRIC_KEYS = (
    "map", "map50", "mAP50", "mAP50-95", "loss", "precision", "recall",
    "test_map", "val_map", "class_map",
)


# --------------------------------------------------------------------- http

def post_callback(payload: dict) -> None:
    """POSTa progresso no backend. Best-effort — treino não morre por rede."""
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
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            resp.read()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.warning("callback_failed: %s", exc)


def http_put(url: str, path: Path, content_type: str) -> None:
    """Sobe artefato via presigned PUT (streaming em memória — arquivos <1GB)."""
    data = path.read_bytes()
    req = urllib.request.Request(  # noqa: S310
        url, data=data, headers={"Content-Type": content_type}, method="PUT"
    )
    with urllib.request.urlopen(req, timeout=600) as resp:  # noqa: S310
        resp.read()
    logger.info("uploaded: %s (%d bytes)", path.name, len(data))


def download(url: str, dest: Path) -> None:
    logger.info("download: %s → %s", url.split("?")[0], dest)
    with urllib.request.urlopen(url, timeout=600) as resp:  # noqa: S310
        dest.write_bytes(resp.read())


def pip_install(*packages: str) -> None:
    logger.info("pip install %s", " ".join(packages))
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pip", "install", "-q", *packages],
        check=True,
        text=True,
    )


# ------------------------------------------------------------------ dataset

def prepare_dataset() -> Path:
    """Baixa o zip COCO presigned e extrai para /root/dataset_coco."""
    if not DATASET_URL:
        raise RuntimeError("DATASET_URL não definido")
    archive = WORK_DIR / "dataset.zip"
    download(DATASET_URL, archive)
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(DATASET_DIR)  # noqa: S202 — zip gerado pelo próprio backend

    # Se o zip tem um único diretório raiz, usar ele como dataset_dir
    entries = [p for p in DATASET_DIR.iterdir() if not p.name.startswith(".")]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return DATASET_DIR


def _collect_metrics(source: dict) -> dict:
    """Filtra chaves numéricas de métricas conhecidas de um log dict."""
    metrics: dict = {}
    for key, value in source.items():
        if key in _METRIC_KEYS or key.startswith(("map", "mAP", "loss")):
            try:
                metrics[key] = float(value)
            except (TypeError, ValueError):
                continue
    return metrics


# ------------------------------------------------------- métricas por classe
# Volta 0: com 5 classes desbalanceadas de poucas câmeras, o mAP agregado
# mistura tudo — uma classe pode estar em 0 enquanto outra puxa a média pra
# cima. As funções abaixo produzem P/R/F1 POR CLASSE + suporte por split
# (contagem de exemplos), o mínimo pra o resultado do treino ser legível.
# São stdlib-puras (testáveis sem GPU — ver test_remote_train_metrics.py);
# a avaliação do modelo (evaluate_rfdetr_per_class) só as alimenta.
_EVAL_IOU = 0.5
_EVAL_CONF = 0.5
_COCO_ANN = "_annotations.coco.json"


def _xywh_to_xyxy(b: list[float]) -> tuple[float, float, float, float]:
    x, y, w, h = b
    return (x, y, x + w, y + h)


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn}


def _match_and_score(gt_by_img: dict, pred_by_img: dict, iou_thr: float = _EVAL_IOU):
    """Greedy match por imagem (IoU>=thr, MESMA categoria) -> tp/fp/fn por
    categoria + confusão leve (categoria da GT que um FP mais sobrepôs).

    gt_by_img/pred_by_img: {img_id: [(cat_id, (x1,y1,x2,y2)), ...]}. Predições
    ordenadas por confiança DESC pelo caller (greedy consome a melhor GT primeiro).
    Retorna (per_cat: {cat_id: {tp,fp,fn}}, confusion: {(gt_cat,pred_cat): n}).
    """
    per_cat: dict = {}
    confusion: dict = {}

    def bump(cat, key):
        per_cat.setdefault(cat, {"tp": 0, "fp": 0, "fn": 0})[key] += 1

    for img_id, gts in gt_by_img.items():
        for cat, _ in gts:
            per_cat.setdefault(cat, {"tp": 0, "fp": 0, "fn": 0})

    all_imgs = set(gt_by_img) | set(pred_by_img)
    for img_id in all_imgs:
        gts = list(gt_by_img.get(img_id, []))
        used = [False] * len(gts)
        for pcat, pbox in pred_by_img.get(img_id, []):
            best_i, best_iou = -1, iou_thr
            best_any_i, best_any_iou = -1, 0.0  # p/ confusão (qualquer categoria)
            for i, (gcat, gbox) in enumerate(gts):
                if used[i]:
                    continue
                v = _iou(pbox, gbox)
                if v > best_any_iou:
                    best_any_iou, best_any_i = v, i
                if gcat == pcat and v >= best_iou:
                    best_iou, best_i = v, i
            if best_i >= 0:
                used[best_i] = True
                bump(pcat, "tp")
            else:
                bump(pcat, "fp")
                if best_any_i >= 0 and best_any_iou >= iou_thr:
                    gcat = gts[best_any_i][0]
                    confusion[(gcat, pcat)] = confusion.get((gcat, pcat), 0) + 1
        for i, (gcat, _) in enumerate(gts):
            if not used[i]:
                bump(gcat, "fn")
    return per_cat, confusion


def count_coco_support(dataset_dir: Path) -> dict:
    """Suporte por classe (caixas + imagens) em cada split, lido dos COCO
    exportados. Determinístico, sem modelo — sempre popula, mesmo se a
    avaliação do modelo falhar. {name: {train_boxes, val_boxes, train_imgs, val_imgs}}."""
    out: dict = {}
    split_dirs = {"train": ["train"], "val": ["valid", "val"], "test": ["test"]}
    zero = {f"{s}_{k}": 0 for s in split_dirs for k in ("boxes", "imgs")}
    for split, folders in split_dirs.items():
        coco = None
        for folder in folders:
            p = dataset_dir / folder / _COCO_ANN
            if p.exists():
                coco = json.loads(p.read_text()); break
        if not coco:
            continue
        names = {c["id"]: c["name"] for c in coco.get("categories", [])}
        imgs_per_cat: dict = {}
        for ann in coco.get("annotations", []):
            name = names.get(ann.get("category_id"), str(ann.get("category_id")))
            row = out.setdefault(name, dict(zero))
            row[f"{split}_boxes"] += 1
            imgs_per_cat.setdefault(name, set()).add(ann.get("image_id"))
        for name, ids in imgs_per_cat.items():
            out[name][f"{split}_imgs"] = len(ids)
    return out


def evaluate_rfdetr_per_class(model, dataset_dir: Path) -> tuple[dict, dict, str]:
    """P/R/F1 por classe no maior split held-out (best-effort — NUNCA derruba o
    job; o caller embrulha em try/except, o artefato ONNX já está salvo).

    Roda model.predict em cada imagem held-out, casa com a GT (greedy IoU) e
    resume por nome de classe. Retorna (per_class_by_name, confusion_by_name,
    split_avaliado).
    """
    from PIL import Image  # noqa: PLC0415

    # Avalia no maior conjunto held-out disponível: 'test' de preferência
    # (nunca visto no treino), senão 'valid'/'val'. Com poucas câmeras o split
    # por grupo (cam+dia) desbalanceia MUITO os tamanhos — o val pode ficar
    # com pouquíssimas imagens; o test held-out costuma dar mais sinal.
    val_dir = next((dataset_dir / f for f in ("test", "valid", "val")
                    if (dataset_dir / f / _COCO_ANN).exists()), None)
    if val_dir is None:
        return {}, {}, ""
    coco = json.loads((val_dir / _COCO_ANN).read_text())
    names = {c["id"]: c["name"] for c in coco.get("categories", [])}
    # mapa 0-based -> category_id (rfdetr prediz índice 0-based da ordem das categorias)
    ordered = [c["id"] for c in sorted(coco.get("categories", []), key=lambda c: c["id"])]
    idx_to_cat = {i: cid for i, cid in enumerate(ordered)}
    files = {im["id"]: im["file_name"] for im in coco.get("images", [])}

    gt_by_img: dict = {}
    for ann in coco.get("annotations", []):
        gt_by_img.setdefault(ann["image_id"], []).append(
            (ann["category_id"], _xywh_to_xyxy(ann["bbox"])))

    pred_by_img: dict = {}
    for img_id, fname in files.items():
        path = val_dir / fname
        if not path.exists():
            continue
        with Image.open(path) as im:
            det = model.predict(im.convert("RGB"), threshold=_EVAL_CONF)
        preds = []
        xyxy = getattr(det, "xyxy", [])
        cls = getattr(det, "class_id", None)
        conf = getattr(det, "confidence", None)
        for i in range(len(xyxy)):
            raw = int(cls[i]) if cls is not None else 0
            cat = raw if raw in names else idx_to_cat.get(raw, raw)
            box = tuple(float(v) for v in xyxy[i])
            c = float(conf[i]) if conf is not None else 1.0
            preds.append((c, cat, box))
        preds.sort(key=lambda t: t[0], reverse=True)  # greedy: maior confiança 1º
        pred_by_img[img_id] = [(cat, box) for _, cat, box in preds]

    per_cat, confusion = _match_and_score(gt_by_img, pred_by_img)
    per_class = {names.get(cat, str(cat)): _prf(v["tp"], v["fp"], v["fn"])
                 for cat, v in per_cat.items()}
    conf_named = {f"{names.get(g, g)}->{names.get(p, p)}": n
                  for (g, p), n in confusion.items()}
    return per_class, conf_named, val_dir.name


# ------------------------------------------------------------------- rfdetr

def train_rfdetr(dataset_dir: Path) -> tuple[Path, Path | None, dict]:
    """Treina RF-DETR (Apache 2.0) e exporta ONNX.

    Passos do runbook TRAINING_PIPELINE_WEEKEND_MVP.md:
      pip install rfdetr → model.train(dataset_dir=..., epochs=N)
      pip install "rfdetr[onnx]" → model.export() → um .onnx
    """
    pip_install("rfdetr", "rfdetr[onnx]", "supervision")
    from rfdetr import RFDETRBase  # noqa: PLC0415

    model = RFDETRBase()
    last_metrics: dict = {}
    state = {"epoch": 0}

    def _on_epoch_end(log: dict) -> None:
        state["epoch"] += 1
        epoch = int(log.get("epoch", state["epoch"]))
        metrics = _collect_metrics(log if isinstance(log, dict) else {})
        last_metrics.update(metrics)
        progress = min(90, 5 + int(epoch / max(EPOCHS, 1) * 85))
        # Envia o ACUMULADO (last_metrics), não só o log desta época: o
        # backend faz UPDATE ... SET metrics = %s (overwrite, não merge —
        # ver TrainingRepository.update_job_status), e frameworks de treino
        # nem sempre logam a mesma chave em toda época (ex.: mAP só a cada
        # N épocas) — mandar só `metrics` fazia chaves já reportadas
        # desaparecerem do progresso ao vivo (achado da revisão adversarial).
        post_callback({
            "status": "running",
            "progress": progress,
            "epoch": epoch,
            "metrics": dict(last_metrics),
        })

    try:
        model.callbacks["on_fit_epoch_end"].append(_on_epoch_end)
    except (AttributeError, KeyError, TypeError):
        logger.warning("rfdetr sem hook on_fit_epoch_end — progresso só no final")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model.train(
        dataset_dir=str(dataset_dir),
        epochs=EPOCHS,
        batch_size=BATCH,
        grad_accum_steps=max(1, 16 // max(BATCH, 1)),
        lr=1e-4,
        resolution=IMGSZ,
        output_dir=str(OUTPUT_DIR),
    )

    # Export ONNX (rfdetr[onnx])
    onnx_path: Path | None = None
    try:
        model.export(output_dir=str(OUTPUT_DIR))
    except TypeError:
        model.export()
    candidates = sorted(OUTPUT_DIR.rglob("*.onnx")) or sorted(
        WORK_DIR.glob("**/inference_model*.onnx")
    )
    if candidates:
        onnx_path = candidates[-1]
    if onnx_path is None:
        raise RuntimeError("RF-DETR export não produziu .onnx")

    weights = OUTPUT_DIR / "checkpoint_best_total.pth"
    if not weights.exists():
        ckpts = sorted(OUTPUT_DIR.glob("checkpoint_*.pth"))
        weights = ckpts[-1] if ckpts else None  # type: ignore[assignment]

    # Métricas por classe (best-effort — o ONNX já foi exportado acima; um erro
    # aqui NUNCA pode derrubar o job/artefato pago). Ver docstring do bloco.
    metrics = dict(last_metrics)
    try:
        per_class, confusion, eval_split = evaluate_rfdetr_per_class(model, dataset_dir)
        if per_class:
            metrics["per_class"] = per_class
            metrics["per_class_eval_split"] = eval_split
        if confusion:
            metrics["confusion"] = confusion
    except Exception as exc:  # noqa: BLE001
        logger.warning("per_class_eval_failed: %s", exc)

    return onnx_path, weights, metrics


# -------------------------------------------------------------------- yolox

def train_yolox(dataset_dir: Path) -> tuple[Path, Path | None, dict]:
    """Treina YOLOX-s (Apache 2.0) via CLI oficial e exporta ONNX."""
    pip_install("yolox", "onnx")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # YOLOX espera datasets/COCO com annotations/ + train2017/ + val2017/;
    # o layout COCO exportado (train/valid/_annotations.coco.json) é adaptado
    # via -d/-b e exp custom simplificado. MVP: treino padrão yolox_s.
    subprocess.run(  # noqa: S603
        [
            sys.executable, "-m", "yolox.tools.train",
            "-n", "yolox-s",
            "-b", str(BATCH),
            "--fp16",
            "-o",
            "max_epoch", str(EPOCHS),
            "data_dir", str(dataset_dir),
            "output_dir", str(OUTPUT_DIR),
        ],
        check=True,
        text=True,
        cwd=str(WORK_DIR),
    )

    ckpts = sorted(OUTPUT_DIR.rglob("best_ckpt.pth"))
    if not ckpts:
        raise RuntimeError("YOLOX não produziu best_ckpt.pth")
    weights = ckpts[-1]

    onnx_path = OUTPUT_DIR / "yolox_s_recognition.onnx"
    subprocess.run(  # noqa: S603
        [
            sys.executable, "-m", "yolox.tools.export_onnx",
            "-n", "yolox-s",
            "-c", str(weights),
            "--output-name", str(onnx_path),
        ],
        check=True,
        text=True,
        cwd=str(WORK_DIR),
    )
    return onnx_path, weights, {}


# ----------------------------------------------------------------- validate

def validate_onnx(onnx_path: Path) -> None:
    """Valida o ONNX com onnxruntime: cria session e roda dummy input."""
    pip_install("onnxruntime", "numpy")
    import numpy as np  # noqa: PLC0415
    import onnxruntime as ort  # noqa: PLC0415

    session = ort.InferenceSession(
        str(onnx_path), providers=["CPUExecutionProvider"]
    )
    feeds = {}
    for inp in session.get_inputs():
        shape = [
            dim if isinstance(dim, int) and dim > 0 else (IMGSZ if i >= 2 else 1)
            for i, dim in enumerate(inp.shape)
        ]
        dtype = np.float16 if "float16" in inp.type else np.float32
        feeds[inp.name] = np.zeros(shape, dtype=dtype)
    outputs = session.run(None, feeds)
    logger.info(
        "onnx_validated: %s outputs=%d shapes=%s",
        onnx_path.name, len(outputs), [getattr(o, "shape", None) for o in outputs],
    )


# --------------------------------------------------------------------- main

def main() -> int:
    post_callback({"status": "running", "progress": 1,
                   "metrics": {"stage": 1.0}})
    dataset_dir = prepare_dataset()
    post_callback({"status": "running", "progress": 5,
                   "metrics": {"stage": 2.0}})

    if FRAMEWORK == "yolox":
        onnx_path, weights_path, metrics = train_yolox(dataset_dir)
    else:
        onnx_path, weights_path, metrics = train_rfdetr(dataset_dir)

    # Suporte por classe/split (determinístico, sem modelo — sempre popula
    # mesmo que a avaliação P/R/F1 acima tenha falhado).
    try:
        metrics["support"] = count_coco_support(dataset_dir)
    except Exception as exc:  # noqa: BLE001
        logger.warning("support_count_failed: %s", exc)

    post_callback({"status": "running", "progress": 92, "metrics": metrics})
    validate_onnx(onnx_path)

    if UPLOAD_URL_ONNX:
        http_put(UPLOAD_URL_ONNX, onnx_path, "application/octet-stream")
    if UPLOAD_URL_WEIGHTS and weights_path and weights_path.exists():
        http_put(UPLOAD_URL_WEIGHTS, weights_path, "application/octet-stream")

    metrics_path = WORK_DIR / "metrics.json"
    metrics_doc = {
        "framework": FRAMEWORK,
        "epochs": EPOCHS,
        "r2_key": R2_ONNX_KEY,
        **metrics,
    }
    metrics_path.write_text(json.dumps(metrics_doc, indent=2))
    if UPLOAD_URL_METRICS:
        http_put(UPLOAD_URL_METRICS, metrics_path, "application/json")

    post_callback({
        "status": "completed",
        "progress": 100,
        "epoch": EPOCHS,
        "metrics": metrics,
        "r2_onnx_key": R2_ONNX_KEY,
    })
    logger.info("remote_train_completed: onnx=%s", onnx_path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — reporta QUALQUER falha ao backend
        logger.exception("remote_train_failed")
        post_callback({"status": "failed", "error_message": str(exc)[:500]})
        sys.exit(1)
