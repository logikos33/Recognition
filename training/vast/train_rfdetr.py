"""
RF-DETR training script — executa dentro da instância Vast.ai (Apache 2.0).

Roboflow RF-DETR: https://github.com/roboflow/rf-detr (Apache 2.0)

Env vars esperadas (injetadas por provision_and_train.sh):
  ROBOFLOW_API_KEY, ROBOFLOW_WORKSPACE, ROBOFLOW_PROJECT, ROBOFLOW_VERSION
  EPOCHS (default 50), BATCH (default 4), IMGSZ (default 560)

Saída:
  /root/runs/rfdetr_base_epi.onnx
  /root/metrics.json  (mAP50, mAP50-95, recall_no_helmet)
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

EPOCHS = int(os.environ.get("EPOCHS", "50"))
BATCH  = int(os.environ.get("BATCH",  "4"))    # RF-DETR usa batch menor
IMGSZ  = int(os.environ.get("IMGSZ",  "560"))  # múltiplo de 56 (RF-DETR padrão)

WORKSPACE = os.environ["ROBOFLOW_WORKSPACE"]
PROJECT   = os.environ["ROBOFLOW_PROJECT"]
VERSION   = int(os.environ["ROBOFLOW_VERSION"])
RF_KEY    = os.environ["ROBOFLOW_API_KEY"]

RUNS_DIR = Path("/root/runs")
RUNS_DIR.mkdir(parents=True, exist_ok=True)
METRICS_PATH = Path("/root/metrics.json")


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    logger.info("CMD: %s", " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, check=True, text=True, **kwargs)


def install_rfdetr() -> None:
    """Instala RF-DETR (Apache 2.0)."""
    try:
        import rfdetr  # noqa: F401
        logger.info("RF-DETR já instalado.")
    except ImportError:
        logger.info("Instalando RF-DETR (Apache 2.0)...")
        _run([sys.executable, "-m", "pip", "install", "-q",
              "rfdetr", "roboflow", "supervision"])


def download_dataset() -> Path:
    """Baixa dataset via Roboflow (CC BY 4.0), formato COCO."""
    logger.info("Baixando dataset %s/%s v%d (COCO)...", WORKSPACE, PROJECT, VERSION)
    from roboflow import Roboflow  # noqa: PLC0415
    rf = Roboflow(api_key=RF_KEY)
    project = rf.workspace(WORKSPACE).project(PROJECT)
    dataset = project.version(VERSION).download("coco", location="/root/dataset_coco")
    return Path(dataset.location)


def train(dataset_dir: Path) -> Path:
    """Treina RF-DETR-base via API Python."""
    from rfdetr import RFDETRBase  # noqa: PLC0415

    train_dir = dataset_dir / "train"
    val_dir   = dataset_dir / "valid"

    model = RFDETRBase()

    logger.info("Iniciando treinamento RF-DETR-base...")
    model.train(
        dataset_dir=str(dataset_dir),
        epochs=EPOCHS,
        batch_size=BATCH,
        grad_accum_steps=max(1, 16 // BATCH),
        lr=1e-4,
        resolution=IMGSZ,
        output_dir="/root/rfdetr_output",
    )

    best_ckpt = Path("/root/rfdetr_output/checkpoint_best_total.pth")
    if not best_ckpt.exists():
        candidates = sorted(Path("/root/rfdetr_output").glob("checkpoint_*.pth"))
        if candidates:
            best_ckpt = candidates[-1]
    return best_ckpt


def export_onnx(model: object) -> Path:
    """Exporta RF-DETR para ONNX via torch.onnx."""
    import torch  # noqa: PLC0415

    onnx_path = RUNS_DIR / "rfdetr_base_epi.onnx"
    logger.info("Exportando RF-DETR para ONNX → %s", onnx_path)

    dummy = torch.randn(1, 3, IMGSZ, IMGSZ)
    torch.onnx.export(
        model,
        dummy,
        str(onnx_path),
        opset_version=17,
        input_names=["images"],
        output_names=["pred_logits", "pred_boxes"],
        dynamic_axes={"images": {0: "batch"}},
    )
    return onnx_path


def parse_metrics() -> dict:
    """Extrai mAP do log de treinamento."""
    import re  # noqa: PLC0415
    metrics: dict = {"source": "rfdetr_base", "epochs": EPOCHS}

    log_candidates = [
        Path("/root/rfdetr_train.log"),
        Path("/root/rfdetr_output/log.txt"),
    ]
    for log_path in log_candidates:
        if not log_path.exists():
            continue
        text = log_path.read_text()
        for pat, key in [
            (r"mAP50[:\s]+([\d.]+)", "map50"),
            (r"mAP50-95[:\s]+([\d.]+)", "map50_95"),
            (r"AP@\[IoU=0\.50\][:\s]+([\d.]+)", "map50"),
        ]:
            m = re.search(pat, text)
            if m:
                metrics[key] = float(m.group(1))
        for line in text.splitlines():
            if "no_helmet" in line.lower():
                m = re.search(r"(\d+\.\d+)", line)
                if m:
                    metrics["recall_no_helmet"] = float(m.group(1))
                    break
        break

    return metrics


def main() -> None:
    install_rfdetr()
    dataset_dir = download_dataset()

    from rfdetr import RFDETRBase  # noqa: PLC0415
    trained_model = RFDETRBase()
    trained_model.train(
        dataset_dir=str(dataset_dir),
        epochs=EPOCHS,
        batch_size=BATCH,
        grad_accum_steps=max(1, 16 // BATCH),
        lr=1e-4,
        resolution=IMGSZ,
        output_dir="/root/rfdetr_output",
    )

    onnx_path = export_onnx(trained_model)
    metrics = parse_metrics()
    metrics["onnx_path"] = str(onnx_path)
    metrics["dataset"] = f"{WORKSPACE}/{PROJECT}@v{VERSION}"
    metrics["license"] = "CC BY 4.0"
    metrics["resolution"] = IMGSZ

    # Merge com metrics.json do yolox se existir
    if METRICS_PATH.exists():
        existing = json.loads(METRICS_PATH.read_text())
        combined = {"yolox": existing, "rfdetr": metrics}
        METRICS_PATH.write_text(json.dumps(combined, indent=2))
    else:
        METRICS_PATH.write_text(json.dumps({"rfdetr": metrics}, indent=2))

    logger.info("Métricas RF-DETR: %s", json.dumps(metrics, indent=2))
    logger.info("ONNX exportado: %s (%d bytes)", onnx_path, onnx_path.stat().st_size)


if __name__ == "__main__":
    main()
