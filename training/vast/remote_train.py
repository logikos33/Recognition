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
import atexit
import threading
import time
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
UPLOAD_URL_LOG = os.environ.get("UPLOAD_URL_LOG", "")

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


def download(url: str, dest: Path, *, expect_zip: bool = False) -> None:
    """Baixa e CONFERE o que veio.

    Sem conferência, um 404 do R2 (que responde XML) era gravado como se fosse
    o dataset, e o erro só aparecia páginas depois como "Could not find class
    names" — mensagem que aponta para o lugar errado. Quatro pods morreram na
    época 0 antes de alguém olhar os bytes.
    """
    logger.info("download: %s → %s", url.split("?")[0], dest)
    with urllib.request.urlopen(url, timeout=600) as resp:  # noqa: S310
        status = getattr(resp, "status", 200)
        if status >= 400:
            raise RuntimeError(f"download falhou: HTTP {status} em {url.split('?')[0]}")
        body = resp.read()

    if not body:
        raise RuntimeError(f"download vazio (0 bytes): {url.split('?')[0]}")

    if expect_zip and body[:2] != b"PK":
        # Diz O QUE veio, não só que deu errado.
        amostra = body[:200].decode("utf-8", "replace")
        raise RuntimeError(
            f"esperava um zip e vieram {len(body)} bytes começando com "
            f"{body[:8]!r} — provável resposta de erro do storage. "
            f"Início: {amostra}"
        )

    dest.write_bytes(body)


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
    download(DATASET_URL, archive, expect_zip=True)
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        nomes = zf.namelist()
        if not nomes:
            raise RuntimeError(
                f"dataset.zip sem nenhuma entrada ({archive.stat().st_size} bytes) "
                "— o backend empacotou de um prefixo vazio"
            )
        if not any(n.endswith("train/_annotations.coco.json") for n in nomes):
            pastas = sorted({n.split("/")[0] for n in nomes if "/" in n})
            raise RuntimeError(
                "dataset.zip sem train/_annotations.coco.json — o treino não "
                f"tem como achar as classes. Pastas no zip: {pastas}"
            )
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


# ------------------------------------------------------------------- rfdetr

def train_rfdetr(dataset_dir: Path) -> tuple[Path, Path | None, dict]:
    """Treina RF-DETR (Apache 2.0) e exporta ONNX.

    Passos do runbook TRAINING_PIPELINE_WEEKEND_MVP.md:
      pip install rfdetr → model.train(dataset_dir=..., epochs=N)
      pip install "rfdetr[onnx]" → model.export() → um .onnx
    """
    # transformers<5: o rfdetr importa BackboneConfigMixin, API da série 4.x
    # removida na 5.x — sem o pin, o pod resolve a 5.x e morre no import
    # (visto em produção DEV: job 9504a3a2, pods m0amcgnl4/1849fpuq).
    # `onnx` e `onnxruntime` EXPLÍCITOS: listar "rfdetr" antes de
    # "rfdetr[onnx]" na mesma chamada faz o pip considerar o requisito já
    # satisfeito pelo primeiro e PULAR o extra. O treino roda até o fim e só
    # então morre no export com "Module onnx is not installed!" — depois de
    # pagar a GPU inteira. Ambos são licenças permissivas (onnx Apache 2.0,
    # onnxruntime MIT), dentro do ADR-0043.
    pip_install(
        "rfdetr", "rfdetr[onnx]", "onnx", "onnxruntime",
        "supervision", "transformers<5",
    )
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
    # RF-DETR (backbone DINOv2) exige resolution múltipla de 56 — o IMGSZ=640
    # herdado do fluxo YOLO derruba o treino no primeiro forward ("Backbone
    # requires input shape to be divisible by 56", visto no DEV: job 90946c17).
    # Ajusta para o múltiplo de 56 mais próximo (default do RFDETRBase é 560).
    resolution = max(56, round(IMGSZ / 56) * 56)
    if resolution != IMGSZ:
        logger.info("rfdetr_resolution_ajustada: %d → %d (múltiplo de 56)", IMGSZ, resolution)
    # RF-DETR base @616 com batch 16 estoura os 24GB da RTX 3090 (OOM real
    # no DEV, job 90946c17: 23,38 GiB em uso). Cap em 4; grad_accum preserva
    # o batch EFETIVO 16 (4 × 4) — mesma matemática, memória 1/4.
    batch_size = min(max(BATCH, 1), 4)
    model.train(
        dataset_dir=str(dataset_dir),
        epochs=EPOCHS,
        batch_size=batch_size,
        grad_accum_steps=max(1, 16 // batch_size),
        lr=1e-4,
        resolution=resolution,
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

    return onnx_path, weights, last_metrics


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


# --------------------------------------------------------------- auto-log
#
# O pod sobe o PRÓPRIO stdout/stderr ao R2. A API REST do RunPod não expõe
# logs (`/v1/pods/{id}/logs` → HTTP 400), então toda falha de pod era cega:
# o log morria com o pod e o diagnóstico virava adivinhação. Nove pods e duas
# paradas do loop custaram isso.
#
# Estratégia: `tee` em memória + flush periódico ao R2 + upload final no
# encerramento. O upload final NÃO cobre SIGKILL/OOM (o processo morre sem
# rodar nada), e é justamente por isso que existe o flush periódico: se o
# kernel matar, o último flush é o que sobra — muito melhor que nada.
_LOG_BUFFER: list[str] = []
_LOG_FLUSH_SECONDS = 120


class _Tee:
    """Escreve no destino original E guarda para o R2."""

    def __init__(self, original):
        self._original = original

    def write(self, texto):
        self._original.write(texto)
        _LOG_BUFFER.append(texto)
        return len(texto)

    def flush(self):
        self._original.flush()

    def __getattr__(self, nome):
        return getattr(self._original, nome)


def _subir_log(motivo: str) -> None:
    if not UPLOAD_URL_LOG or not _LOG_BUFFER:
        return
    try:
        corpo = "".join(_LOG_BUFFER).encode("utf-8", "replace")
        req = urllib.request.Request(
            UPLOAD_URL_LOG, data=corpo, method="PUT",
            headers={"Content-Type": "text/plain"},
        )
        urllib.request.urlopen(req, timeout=120)  # noqa: S310
        logger.info("log_uploaded: %s (%d bytes)", motivo, len(corpo))
    except Exception as exc:  # noqa: BLE001 — log nunca derruba o treino
        logger.warning("log_upload_failed (%s): %s", motivo, exc)


def _flush_periodico() -> None:
    while True:
        time.sleep(_LOG_FLUSH_SECONDS)
        _subir_log("flush periodico")


def _instalar_autolog() -> None:
    if not UPLOAD_URL_LOG:
        return
    sys.stdout = _Tee(sys.stdout)
    sys.stderr = _Tee(sys.stderr)
    for h in logging.getLogger().handlers:
        if isinstance(h, logging.StreamHandler):
            h.stream = sys.stderr
    threading.Thread(target=_flush_periodico, daemon=True).start()
    atexit.register(lambda: _subir_log("encerramento"))


if __name__ == "__main__":
    _instalar_autolog()
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 — reporta QUALQUER falha ao backend
        logger.exception("remote_train_failed")
        _subir_log("falha")
        post_callback({"status": "failed", "error_message": str(exc)[:500]})
        sys.exit(1)
