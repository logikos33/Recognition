"""
Upload ONNX → R2 + registrar no models table (linhagem completa).

Uso local após provision_and_train.sh baixar artefatos:
  export DATABASE_URL=postgresql://...
  export R2_ENDPOINT_URL=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... R2_BUCKET_NAME=...
  python3 training/vast/upload_and_register.py --runs-dir training/vast/runs/20260701_120000

Env vars:
  DATABASE_URL          — PostgreSQL de staging/produção
  R2_ENDPOINT_URL       — Cloudflare R2 endpoint
  R2_ACCESS_KEY_ID      — R2 access key
  R2_SECRET_ACCESS_KEY  — R2 secret key
  R2_BUCKET_NAME        — bucket (ex: recognition-r2)
  TEST_TENANT_ID        — UUID do tenant de teste (default: 00000000-0000-0000-0000-0000000000AA)
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import os
import sys
import uuid
from pathlib import Path

import boto3
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TEST_TENANT_ID = os.environ.get("TEST_TENANT_ID", "00000000-0000-0000-0000-0000000000AA")
R2_PREFIX = "models"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _upload_to_r2(path: Path, r2_key: str) -> str:
    """Faz upload do arquivo para R2 e retorna a chave."""
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )
    bucket = os.environ["R2_BUCKET_NAME"]
    logger.info("Enviando %s → s3://%s/%s ...", path.name, bucket, r2_key)
    s3.upload_file(
        Filename=str(path),
        Bucket=bucket,
        Key=r2_key,
        ExtraArgs={"ContentType": "application/octet-stream"},
    )
    logger.info("Upload concluído: %s", r2_key)
    return r2_key


def _register_in_db(
    tenant_id: str,
    name: str,
    model_key: str,
    metrics: dict,
    is_default: bool = False,
) -> str:
    """Insere ou atualiza linha em public.models. Retorna o UUID."""
    db_url = os.environ["DATABASE_URL"]
    model_id = str(uuid.uuid4())

    with psycopg2.connect(db_url, cursor_factory=RealDictCursor) as conn:
        with conn.cursor() as cur:
            # Se is_default, limpar flag anterior
            if is_default:
                cur.execute(
                    "UPDATE models SET is_default = FALSE WHERE tenant_id = %s",
                    (tenant_id,),
                )

            cur.execute(
                """
                INSERT INTO models (id, tenant_id, name, model_key, metrics, is_default, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (tenant_id, name) DO UPDATE
                  SET model_key = EXCLUDED.model_key,
                      metrics   = EXCLUDED.metrics,
                      is_default = EXCLUDED.is_default,
                      created_at = NOW()
                RETURNING id
                """,
                (model_id, tenant_id, name, model_key, json.dumps(metrics), is_default),
            )
            row = cur.fetchone()
            model_id = str(row["id"]) if row else model_id
        conn.commit()

    logger.info("Model registrado: id=%s name=%s key=%s", model_id, name, model_key)
    return model_id


def process_model(onnx_path: Path, metrics: dict, runs_dir: Path) -> dict:
    """Upload + register para um arquivo ONNX. Retorna resultado."""
    sha = _sha256(onnx_path)
    stem = onnx_path.stem   # ex: yolox_s_epi

    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    r2_key = f"{R2_PREFIX}/{TEST_TENANT_ID}/vast/{stem}_{timestamp}.onnx"

    # Linhagem completa para rastreabilidade
    lineage_metrics = {
        **metrics,
        "sha256": sha,
        "size_bytes": onnx_path.stat().st_size,
        "r2_key": r2_key,
        "trained_at": timestamp,
        "source": "vast_ai_training",
        "license": metrics.get("license", "CC BY 4.0"),
        "dataset": metrics.get("dataset", "unknown"),
        "epochs": metrics.get("epochs"),
    }

    _upload_to_r2(onnx_path, r2_key)

    model_name = f"{stem.replace('_epi', '')}-epi-vast-{timestamp}"
    model_id = _register_in_db(
        tenant_id=TEST_TENANT_ID,
        name=model_name,
        model_key=r2_key,
        metrics=lineage_metrics,
        is_default=True,   # modelos Vast.ai viram padrão automaticamente
    )

    return {"model_id": model_id, "model_key": r2_key, "sha256": sha, "metrics": lineage_metrics}


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload ONNX + register no model registry")
    parser.add_argument("--runs-dir", required=True, help="Diretório com artefatos baixados da instância")
    parser.add_argument("--tenant-id", default=TEST_TENANT_ID, help="Tenant UUID de destino")
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    if not runs_dir.exists():
        logger.error("Diretório não encontrado: %s", runs_dir)
        sys.exit(1)

    onnx_files = list(runs_dir.glob("*.onnx"))
    if not onnx_files:
        logger.error("Nenhum arquivo .onnx encontrado em %s", runs_dir)
        sys.exit(1)

    # Carregar métricas combinadas se disponíveis
    metrics_path = runs_dir / "metrics.json"
    metrics_raw: dict = {}
    if metrics_path.exists():
        metrics_raw = json.loads(metrics_path.read_text())
        logger.info("Métricas carregadas de %s", metrics_path)

    results = []
    for onnx_path in onnx_files:
        logger.info("Processando %s ...", onnx_path.name)
        # Seleciona métricas por modelo (yolox / rfdetr)
        model_key_hint = "yolox" if "yolox" in onnx_path.name else "rfdetr"
        model_metrics = metrics_raw.get(model_key_hint, metrics_raw)

        result = process_model(onnx_path, model_metrics, runs_dir)
        results.append({"file": onnx_path.name, **result})

    # Salvar relatório de registro
    report_path = runs_dir / "registry_report.json"
    report_path.write_text(json.dumps(results, indent=2))
    logger.info("Relatório salvo em %s", report_path)

    for r in results:
        logger.info("  %s → model_id=%s key=%s", r["file"], r["model_id"], r["model_key"])

    logger.info("=== Registro concluído (%d modelo(s)) ===", len(results))


if __name__ == "__main__":
    main()
