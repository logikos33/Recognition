"""Pre-annotator: DINO + SAM pipeline por frame."""
import io
import json
import logging
from datetime import UTC, datetime

import boto3
import numpy as np
import psycopg2
import psycopg2.extras
from PIL import Image

from src.config import config
from src.models.dino_loader import dino_model
from src.models.sam_loader import sam_model

logger = logging.getLogger(__name__)


def _get_s3():
    return boto3.client(
        "s3",
        endpoint_url=config.R2_ENDPOINT,
        aws_access_key_id=config.R2_KEY,
        aws_secret_access_key=config.R2_SECRET,
        region_name="auto",
    )


def _get_conn():
    db_url = config.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def pre_annotate_frame(frame_id: str) -> dict:
    """
    Pré-anota um frame com DINO + SAM.

    1. Busca frame no banco
    2. Baixa imagem do R2
    3. DINO detecta objetos
    4. SAM refina cada bbox
    5. Salva pre_annotations + status no banco
    """
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, filename, module_code, pre_annotated_at FROM training_frames WHERE id = %s",
            (frame_id,),
        )
        frame = cur.fetchone()

        if not frame:
            raise ValueError(f"Frame {frame_id} não encontrado")

        if frame["pre_annotated_at"] is not None:
            return {"frame_id": frame_id, "status": "skipped", "reason": "already processed"}

        # Baixar imagem do R2
        frame_key = frame["filename"]
        logger.info("downloading_frame: id=%s key=%s", frame_id, frame_key)

        try:
            s3 = _get_s3()
            obj = s3.get_object(Bucket=config.R2_BUCKET, Key=frame_key)
            image_data = obj["Body"].read()
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
        except Exception as exc:
            logger.warning("r2_download_failed: %s — using empty annotations", exc)
            image = None

        annotations = []
        if image is not None:
            # DINO detection
            text_prompt = dino_model.get_prompt(frame.get("module_code") or "epi")
            detections = dino_model.predict(image, text_prompt)
            logger.info("dino_detections: frame=%s count=%d", frame_id, len(detections))

            # SAM refinement
            img_array = np.array(image)
            for det in detections:
                refined_bbox = sam_model.refine_box(img_array, det["bbox"])
                annotations.append({
                    **det,
                    "bbox": refined_bbox,
                    "source": "dino+sam" if refined_bbox != det["bbox"] else "dino",
                })

        cur.execute(
            """
            UPDATE training_frames
            SET pre_annotations = %s::jsonb,
                pre_annotated_at = %s
            WHERE id = %s
            """,
            (json.dumps(annotations), datetime.now(tz=UTC), frame_id),
        )
        conn.commit()
        logger.info("pre_annotated: frame=%s count=%d", frame_id, len(annotations))

        return {
            "frame_id": frame_id,
            "status": "success",
            "annotations_count": len(annotations),
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def pre_annotate_batch(frame_ids: list) -> dict:
    """Pré-anota lista de frames. Continua mesmo se alguns falharem."""
    results = {"total": len(frame_ids), "success": 0, "failed": 0, "frames": []}

    for frame_id in frame_ids:
        try:
            result = pre_annotate_frame(frame_id)
            results["success"] += 1
            results["frames"].append(result)
        except Exception as exc:
            logger.error("batch_frame_failed: frame=%s err=%s", frame_id, exc)
            results["failed"] += 1
            results["frames"].append({"frame_id": frame_id, "status": "error", "error": str(exc)})

    return results
