"""
Registra modelos COCO pré-treinados no registry — task-055a / PR A2.

Baixa YOLOX-s e RF-DETR-N ONNX (Apache 2.0, COCO 80 classes),
faz upload para R2 sob o prefixo do tenant de teste e insere linhas
na tabela `models` com linhagem completa.

Uso:
  SEED_ALLOWED=1 \\
  DATABASE_URL=postgresql://... \\
  R2_ENDPOINT=https://xxx.r2.cloudflarestorage.com \\
  R2_BUCKET=epi-monitor \\
  R2_KEY=... R2_SECRET=... \\
  python3 scripts/register_pretrained_models.py

  # Para recriar (deleta linhas existentes antes):
  SEED_ALLOWED=1 ... REGISTER_FORCE=1 python3 scripts/register_pretrained_models.py

Licenças:
  YOLOX   — Apache 2.0 (Megvii)   https://github.com/Megvii-BaseDetection/YOLOX
  RF-DETR — Apache 2.0 (Roboflow) https://github.com/roboflow/rf-detr
"""
import hashlib
import os
import sys
import tempfile
import uuid
from pathlib import Path

TEST_TENANT_ID = "00000000-0000-0000-0000-0000000000AA"

MODELS = [
    {
        "name": "yolox-s-coco-pretrained",
        "backend": "yolox_onnx",
        "url": (
            "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/"
            "0.1.1rc0/yolox_s.onnx"
        ),
        "r2_key": "models/test-tenant/pretrained/yolox_s_coco.onnx",
        "metrics": {
            "source": "pretrained-coco",
            "license": "Apache-2.0",
            "license_url": "https://github.com/Megvii-BaseDetection/YOLOX/blob/main/LICENSE",
            "dataset": "COCO 2017 val",
            "map50_95": 0.407,
            "classes": 80,
            "input_size": "640x640",
            "backend": "yolox_onnx",
            "notes": "COCO pretrained — para EPI substituir via console com modelo treinado",
        },
        "is_default": True,
    },
    {
        "name": "rfdetr-n-coco-pretrained",
        "backend": "rfdetr_onnx",
        "url": (
            "https://huggingface.co/roboflow/rf-detr-base/resolve/main/"
            "rf-detr-base.onnx"
        ),
        "r2_key": "models/test-tenant/pretrained/rfdetr_n_coco.onnx",
        "metrics": {
            "source": "pretrained-coco",
            "license": "Apache-2.0",
            "license_url": "https://github.com/roboflow/rf-detr/blob/main/LICENSE",
            "dataset": "COCO 2017 val",
            "map50_95": 0.481,
            "classes": 91,
            "backend": "rfdetr_onnx",
            "notes": "RF-DETR base pretrained — alternativo ao YOLOX para benchmarking",
        },
        "is_default": False,
    },
]


def _gate() -> None:
    if os.environ.get("SEED_ALLOWED") != "1":
        print("ERRO: defina SEED_ALLOWED=1 para executar este script.")
        sys.exit(1)
    for var in ("DATABASE_URL", "R2_ENDPOINT", "R2_BUCKET", "R2_KEY", "R2_SECRET"):
        if not os.environ.get(var):
            print(f"ERRO: {var} não definida.")
            sys.exit(1)


def _get_conn():
    import psycopg2  # noqa: PLC0415
    from psycopg2.extras import RealDictCursor  # noqa: PLC0415
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def _get_r2():
    import boto3  # noqa: PLC0415
    return boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT"],
        aws_access_key_id=os.environ["R2_KEY"],
        aws_secret_access_key=os.environ["R2_SECRET"],
        region_name="auto",
    )


def _download(url: str, dest: Path, label: str) -> str:
    """Download com barra de progresso simples. Retorna sha256 do arquivo."""
    import requests  # noqa: PLC0415

    print(f"  [{label}] Baixando {url}")
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    sha = hashlib.sha256()

    with dest.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            sha.update(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded * 100 // total
                print(f"\r  [{label}] {pct}% ({downloaded}/{total} bytes)", end="", flush=True)

    print(f"\r  [{label}] download completo — {downloaded} bytes")
    return sha.hexdigest()


def _upload_r2(r2, local_path: Path, r2_key: str, label: str) -> str:
    """Upload para R2. Retorna URL pública (ou chave se bucket privado)."""
    bucket = os.environ["R2_BUCKET"]
    size = local_path.stat().st_size
    print(f"  [{label}] Fazendo upload para R2: {r2_key} ({size:,} bytes)")
    r2.upload_file(
        str(local_path),
        bucket,
        r2_key,
        ExtraArgs={"ContentType": "application/octet-stream"},
    )
    print(f"  [{label}] upload concluído → {r2_key}")
    return r2_key


def _register_db(conn, model_cfg: dict, r2_key: str, sha256: str) -> None:
    """Upsert no registry `models`."""
    import json  # noqa: PLC0415

    metrics = dict(model_cfg["metrics"])
    metrics["sha256"] = sha256
    metrics["r2_key"] = r2_key

    force = os.environ.get("REGISTER_FORCE") == "1"

    with conn.cursor() as cur:
        if force:
            cur.execute(
                "DELETE FROM models WHERE tenant_id = %s AND name = %s",
                (TEST_TENANT_ID, model_cfg["name"]),
            )
            deleted = cur.rowcount
            if deleted:
                print(f"  [{model_cfg['name']}] {deleted} linha(s) antiga(s) deletada(s)")

        cur.execute(
            """
            INSERT INTO models (id, tenant_id, name, model_key, metrics, is_default)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (
                str(uuid.uuid4()),
                TEST_TENANT_ID,
                model_cfg["name"],
                r2_key,
                json.dumps(metrics),
                model_cfg["is_default"],
            ),
        )
        row = cur.fetchone()
        if row:
            print(f"  [{model_cfg['name']}] inserido: id={row['id']}")
        else:
            print(f"  [{model_cfg['name']}] já existia (ON CONFLICT DO NOTHING) — use REGISTER_FORCE=1 para recriar")

    conn.commit()


def main() -> None:
    _gate()

    print("Conectando ao banco e R2...")
    conn = _get_conn()
    r2 = _get_r2()

    with tempfile.TemporaryDirectory() as tmpdir:
        for model_cfg in MODELS:
            label = model_cfg["name"]
            print(f"\n--- {label} ---")

            local_path = Path(tmpdir) / Path(model_cfg["r2_key"]).name
            sha256 = _download(model_cfg["url"], local_path, label)
            r2_key = _upload_r2(r2, local_path, model_cfg["r2_key"], label)
            _register_db(conn, model_cfg, r2_key, sha256)

    conn.close()

    print("\n=== Registro concluído ===")
    print(f"  tenant_id: {TEST_TENANT_ID}")
    for m in MODELS:
        print(f"  {m['name']:40s} default={m['is_default']}")
    print("\nPróximo passo: configurar DETECTOR_MODEL_PATH no Railway worker")
    print("  DETECTOR_BACKEND=yolox_onnx")
    print("  DETECTOR_MODEL_PATH=<caminho_local_ou_presigned_url>")
    print("  VIOLATION_CLASSES=person  # teste COCO; EPI: no_helmet,no_vest,no_gloves")


if __name__ == "__main__":
    main()
