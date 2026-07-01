"""
YOLOX-s training script — executa dentro da instância Vast.ai (Apache 2.0).

Env vars esperadas (injetadas por provision_and_train.sh):
  ROBOFLOW_API_KEY, ROBOFLOW_WORKSPACE, ROBOFLOW_PROJECT, ROBOFLOW_VERSION
  EPOCHS (default 50), BATCH (default 16), IMGSZ (default 640)

Saída:
  /root/runs/yolox_s_epi.onnx
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
BATCH  = int(os.environ.get("BATCH",  "16"))
IMGSZ  = int(os.environ.get("IMGSZ",  "640"))

WORKSPACE = os.environ["ROBOFLOW_WORKSPACE"]
PROJECT   = os.environ["ROBOFLOW_PROJECT"]
VERSION   = int(os.environ["ROBOFLOW_VERSION"])
RF_KEY    = os.environ["ROBOFLOW_API_KEY"]
RF_FORMAT = os.environ.get("ROBOFLOW_FORMAT", "yolov8")

RUNS_DIR = Path("/root/runs")
RUNS_DIR.mkdir(parents=True, exist_ok=True)
METRICS_PATH = Path("/root/metrics.json")

# EPI class names — mapeados via VIOLATION_CLASSES no serviço
EPI_CLASSES = [
    "helmet", "no_helmet", "vest", "no_vest",
    "gloves", "no_gloves", "glasses", "no_glasses",
]


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    logger.info("CMD: %s", " ".join(str(c) for c in cmd))
    result = subprocess.run(cmd, check=True, text=True, **kwargs)
    return result


def download_dataset() -> Path:
    """Baixa dataset via Roboflow API (CC BY 4.0) e retorna o diretório."""
    logger.info("Baixando dataset %s/%s v%d ...", WORKSPACE, PROJECT, VERSION)
    try:
        from roboflow import Roboflow  # noqa: PLC0415
    except ImportError:
        _run([sys.executable, "-m", "pip", "install", "-q", "roboflow"])
        from roboflow import Roboflow  # noqa: PLC0415

    rf = Roboflow(api_key=RF_KEY)
    project = rf.workspace(WORKSPACE).project(PROJECT)
    dataset = project.version(VERSION).download(RF_FORMAT, location="/root/dataset")
    return Path(dataset.location)


def install_yolox() -> None:
    """Instala YOLOX do repositório oficial (Apache 2.0)."""
    yolox_dir = Path("/root/YOLOX")
    if yolox_dir.exists():
        logger.info("YOLOX já instalado.")
        return
    logger.info("Instalando YOLOX (Apache 2.0)...")
    _run(["git", "clone", "https://github.com/Megvii-BaseDetection/YOLOX.git", str(yolox_dir)])
    _run([sys.executable, "-m", "pip", "install", "-q", "-r", str(yolox_dir / "requirements.txt")])
    _run([sys.executable, "-m", "pip", "install", "-q", "-e", str(yolox_dir)])


def build_exp_file(dataset_dir: Path, num_classes: int) -> Path:
    """Gera arquivo de experimento YOLOX-s com parâmetros do dataset."""
    exp_path = Path("/root/yolox_s_epi.py")
    data_yaml = dataset_dir / "data.yaml"

    exp_content = f"""
# YOLOX-s experiment — EPI classes — gerado por train_yolox.py
from yolox.exp import Exp as MyExp

class Exp(MyExp):
    def __init__(self):
        super().__init__()
        self.exp_name = "yolox_s_epi"
        self.depth = 0.33
        self.width = 0.50
        self.num_classes = {num_classes}
        self.max_epoch = {EPOCHS}
        self.data_num_workers = 4
        self.input_size = ({IMGSZ}, {IMGSZ})
        self.random_size = (14, 26)
        self.test_size = ({IMGSZ}, {IMGSZ})
        self.eval_interval = 5
        # Dataset paths (formato COCO JSON)
        self.train_ann = "instances_train.json"
        self.val_ann   = "instances_val.json"
        self.data_dir  = "{dataset_dir}"
"""
    exp_path.write_text(exp_content)
    logger.info("Arquivo de experimento escrito em %s", exp_path)
    return exp_path


def convert_dataset_to_coco(dataset_dir: Path) -> tuple[Path, int]:
    """Converte dataset YOLOv8 (txt+yaml) para formato COCO JSON."""
    import re  # noqa: PLC0415
    import yaml  # noqa: PLC0415 (included with ultralytics env)

    yaml_files = list(dataset_dir.glob("*.yaml"))
    if not yaml_files:
        raise FileNotFoundError(f"Nenhum arquivo .yaml encontrado em {dataset_dir}")

    with yaml_files[0].open() as f:
        cfg = yaml.safe_load(f)

    names: list[str] = cfg.get("names", EPI_CLASSES)
    num_classes = len(names)
    logger.info("Classes (%d): %s", num_classes, names)

    coco_base = {
        "info": {"description": f"EPI dataset v{VERSION}", "version": "1.0"},
        "licenses": [{"id": 1, "name": "CC BY 4.0"}],
        "categories": [{"id": i, "name": n, "supercategory": "epi"} for i, n in enumerate(names)],
    }

    for split in ("train", "valid", "test"):
        split_dir = dataset_dir / split
        if not split_dir.exists():
            continue
        images_dir = split_dir / "images"
        labels_dir = split_dir / "labels"
        if not images_dir.exists():
            continue

        images_meta, annotations = [], []
        ann_id = 1

        for img_path in sorted(images_dir.iterdir()):
            if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            img_id = len(images_meta) + 1
            images_meta.append({"id": img_id, "file_name": str(img_path), "width": IMGSZ, "height": IMGSZ})

            lbl_path = labels_dir / (img_path.stem + ".txt")
            if not lbl_path.exists():
                continue
            for line in lbl_path.read_text().splitlines():
                parts = line.split()
                if len(parts) != 5:
                    continue
                cls, cx, cy, w, h = int(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                abs_w, abs_h = w * IMGSZ, h * IMGSZ
                abs_x, abs_y = cx * IMGSZ - abs_w / 2, cy * IMGSZ - abs_h / 2
                annotations.append({
                    "id": ann_id, "image_id": img_id, "category_id": cls,
                    "bbox": [abs_x, abs_y, abs_w, abs_h],
                    "area": abs_w * abs_h, "iscrowd": 0,
                })
                ann_id += 1

        out = {**coco_base, "images": images_meta, "annotations": annotations}
        out_file = dataset_dir / split / f"instances_{split if split != 'valid' else 'val'}.json"
        out_file.write_text(json.dumps(out))
        logger.info("COCO JSON escrito: %s (%d imgs, %d anns)", out_file, len(images_meta), len(annotations))

    return dataset_dir, num_classes


def train(exp_file: Path, dataset_dir: Path) -> Path:
    """Executa treinamento YOLOX via CLI."""
    yolox_dir = Path("/root/YOLOX")
    pretrained = "/root/yolox_s.pth"

    # Baixar pesos pré-treinados COCO (Apache 2.0)
    if not Path(pretrained).exists():
        logger.info("Baixando pesos YOLOX-s COCO...")
        _run([
            "wget", "-q",
            "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.pth",
            "-O", pretrained,
        ])

    _run([
        sys.executable, str(yolox_dir / "tools" / "train.py"),
        "-f", str(exp_file),
        "-c", pretrained,
        "-d", "1",       # 1 GPU
        "-b", str(BATCH),
        "--fp16",
        "--occupy",
    ])

    # Localizar melhor checkpoint
    best_ckpt = Path("/root/YOLOX_outputs/yolox_s_epi/best_ckpt.pth")
    if not best_ckpt.exists():
        candidates = list(Path("/root/YOLOX_outputs").glob("**/best_ckpt.pth"))
        if candidates:
            best_ckpt = candidates[0]
    return best_ckpt


def export_onnx(exp_file: Path, checkpoint: Path) -> Path:
    """Exporta modelo para ONNX."""
    yolox_dir = Path("/root/YOLOX")
    onnx_out = RUNS_DIR / "yolox_s_epi.onnx"
    logger.info("Exportando ONNX → %s", onnx_out)

    _run([
        sys.executable, str(yolox_dir / "tools" / "export_onnx.py"),
        "--output-name", str(onnx_out),
        "-f", str(exp_file),
        "-c", str(checkpoint),
    ])
    return onnx_out


def parse_metrics(log_path: Path = Path("/root/yolox_train.log")) -> dict:
    """Extrai mAP do log de treinamento."""
    import re  # noqa: PLC0415
    metrics: dict = {"source": "yolox_s", "epochs": EPOCHS}

    if not log_path.exists():
        return metrics

    text = log_path.read_text()
    # Padrão: "AP50: 0.xxx", "mAP: 0.xxx"
    for pat, key in [
        (r"AP50[:\s]+([\d.]+)", "map50"),
        (r"mAP50-95[:\s]+([\d.]+)", "map50_95"),
    ]:
        m = re.search(pat, text)
        if m:
            metrics[key] = float(m.group(1))

    # Recall específico de no_helmet
    for line in text.splitlines():
        if "no_helmet" in line.lower():
            m = re.search(r"(\d+\.\d+)", line)
            if m:
                metrics["recall_no_helmet"] = float(m.group(1))
                break

    return metrics


def main() -> None:
    dataset_dir = download_dataset()
    install_yolox()
    dataset_dir, num_classes = convert_dataset_to_coco(dataset_dir)
    exp_file = build_exp_file(dataset_dir, num_classes)
    checkpoint = train(exp_file, dataset_dir)
    onnx_path = export_onnx(exp_file, checkpoint)
    metrics = parse_metrics()
    metrics["onnx_path"] = str(onnx_path)
    metrics["dataset"] = f"{WORKSPACE}/{PROJECT}@v{VERSION}"
    metrics["license"] = "CC BY 4.0"

    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    logger.info("Métricas: %s", json.dumps(metrics, indent=2))
    logger.info("ONNX exportado: %s (%d bytes)", onnx_path, onnx_path.stat().st_size)


if __name__ == "__main__":
    main()
