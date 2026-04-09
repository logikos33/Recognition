"""
Pre-Annotation Service — Flask app factory.

Pré-anota frames com Grounding DINO + SAM e prioriza via Active Learning.
"""
import logging
import os

from flask import Flask, jsonify

from src.api.routes import api_bp
from src.models.dino_loader import dino_model
from src.models.sam_loader import sam_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.register_blueprint(api_bp)

# Tentar carregar modelos na inicialização (não crítico — /health reporta status)
_dino_ok = dino_model.load()
_sam_ok = sam_model.load()
logger.info("startup: dino=%s sam=%s", _dino_ok, _sam_ok)


@app.route("/health")
def health():
    """Health check completo: modelos + banco + storage."""
    checks = {
        "dino": dino_model.model is not None,
        "sam": sam_model.predictor is not None,
        "database": False,
        "storage": False,
    }

    # Database
    try:
        import psycopg2
        from src.config import config
        db_url = config.DATABASE_URL
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(db_url, connect_timeout=5)
        conn.close()
        checks["database"] = True
    except Exception as exc:
        logger.warning("health_db_failed: %s", exc)

    # Storage (R2)
    try:
        import boto3
        from src.config import config
        if config.R2_ENDPOINT and config.R2_KEY:
            s3 = boto3.client(
                "s3",
                endpoint_url=config.R2_ENDPOINT,
                aws_access_key_id=config.R2_KEY,
                aws_secret_access_key=config.R2_SECRET,
                region_name="auto",
            )
            s3.list_objects_v2(Bucket=config.R2_BUCKET, MaxKeys=1)
            checks["storage"] = True
    except Exception as exc:
        logger.warning("health_storage_failed: %s", exc)

    all_ok = checks["database"]  # mínimo necessário: banco OK
    return jsonify({
        "service": "pre-annotation-service",
        "status": "healthy" if all_ok else "degraded",
        "checks": checks,
    }), 200 if all_ok else 503


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
