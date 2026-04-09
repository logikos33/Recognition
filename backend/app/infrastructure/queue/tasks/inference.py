"""
DEPRECATED: Este módulo é legado V1.

Usar inference-service/ para inferência YOLOv8.
Usar camera-gateway/ para HLS streaming.

Mantido apenas como fallback quando os serviços isolados
estão offline. Será removido na v3.0.
"""
import json
import logging
import os
import subprocess
import time
from datetime import datetime
from uuid import UUID

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_redis_client():
    """Retorna cliente Redis conectado."""
    import redis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    return redis.from_url(redis_url, decode_responses=True)


def _is_stream_active(camera_id: str, r) -> bool:
    """Retorna True enquanto a chave de controle existir no Redis."""
    return bool(r.exists(f"epi:stream:{camera_id}:active"))


def _load_yolo_model(model_path: str):
    """Carrega modelo YOLO com cache em /tmp/epi_models/.

    Retorna instância do modelo ou None se ultralytics não estiver instalado.
    """
    try:
        from ultralytics import YOLO  # type: ignore[import]
    except ImportError:
        logger.warning(
            "yolo_unavailable: ultralytics not installed — running in no-YOLO mode"
        )
        return None

    cache_dir = "/tmp/epi_models"
    os.makedirs(cache_dir, exist_ok=True)

    # Use the provided path; fall back to yolov8n.pt if not found
    resolved = model_path if os.path.isfile(model_path) else "yolov8n.pt"
    logger.info("yolo_model_load: path=%s", resolved)
    return YOLO(resolved)


def _save_alert(camera_id: str, detections: list[dict], frame) -> None:
    """Salva alerta de violação: frame no storage + registro no banco.

    Falhas são logadas mas NÃO propagadas — não devem interromper o loop.
    """
    try:
        import cv2  # type: ignore[import]

        from app.infrastructure.database.connection import DatabasePool
        from app.infrastructure.database.repositories.alert_repository import (
            AlertRepository,
        )
        from app.infrastructure.storage.local_storage import get_storage

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
        evidence_key = f"evidence/{camera_id}/{timestamp}.jpg"

        # Encode frame as JPEG and upload
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            logger.error("alert_frame_encode_failed: camera=%s", camera_id)
            return

        jpeg_bytes = buf.tobytes()
        storage = get_storage()
        storage.upload_bytes(evidence_key, jpeg_bytes, "image/jpeg")

        # Compute aggregate confidence
        avg_confidence = (
            sum(d["confidence"] for d in detections) / len(detections)
            if detections
            else 0.0
        )

        # Persist alert record
        pool = DatabasePool.get_instance()
        if pool is None:
            logger.warning("alert_db_skip: DatabasePool not initialized")
            return

        repo = AlertRepository(pool)
        repo.create(
            camera_id=UUID(camera_id),
            violations=detections,
            confidence=round(avg_confidence, 3),
            evidence_key=evidence_key,
        )
        logger.info(
            "alert_saved: camera=%s, evidence=%s, violations=%d",
            camera_id,
            evidence_key,
            len(detections),
        )

    except Exception as exc:
        logger.error(
            "alert_save_failed: camera=%s, error=%s",
            camera_id,
            exc,
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@celery.task(bind=True, queue="inference", max_retries=5, name="tasks.inference.inference_loop")
def inference_loop(self, camera_id: str, rtsp_url: str, model_path: str = "yolov8n.pt") -> dict:
    """Loop de inferência YOLO por câmera.

    1. Carrega modelo YOLOv8 (lazy, cached em /tmp/epi_models/)
    2. Conecta stream RTSP via OpenCV
    3. A cada N frames: roda inferência
    4. Publica detecções no Redis (canal det:{camera_id})
    5. Salva alertas no banco + storage em caso de violação
    6. Para quando a chave epi:stream:{camera_id}:active sumir do Redis

    Args:
        camera_id: UUID da câmera como string.
        rtsp_url: URL RTSP completa da câmera.
        model_path: Caminho para o arquivo .pt do modelo YOLO.

    Returns:
        dict com camera_id, frames_processed e status.
    """
    import cv2  # type: ignore[import]

    every_n = int(os.environ.get("YOLO_INFERENCE_EVERY_N_FRAMES", "5"))
    detection_confidence = float(
        os.environ.get("DETECTION_CONFIDENCE_THRESHOLD", "0.5")
    )

    redis_client = _get_redis_client()
    model = _load_yolo_model(model_path)

    logger.info(
        "inference_start: camera=%s, model=%s, every_n=%d",
        camera_id,
        model_path,
        every_n,
    )

    cap = cv2.VideoCapture(rtsp_url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    frame_count = 0
    frames_processed = 0

    try:
        while _is_stream_active(camera_id, redis_client):
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            frame_count += 1
            if frame_count % every_n != 0:
                continue

            frames_processed += 1

            # Run YOLO inference
            detections: list[dict] = []
            has_violation = False

            if model is not None:
                results = model(frame, verbose=False)
                for r in results:
                    for box in r.boxes:
                        cls = r.names[int(box.cls)]
                        conf = float(box.conf)
                        if conf >= detection_confidence:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            detections.append(
                                {
                                    "class": cls,
                                    "confidence": round(conf, 3),
                                    "bbox": [x1, y1, x2 - x1, y2 - y1],
                                }
                            )
                            if cls.startswith("no_"):
                                has_violation = True

            # Publish to Redis for SocketIO broadcast
            payload = {
                "camera_id": camera_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "detections": detections,
                "has_violation": has_violation,
            }
            redis_client.publish(f"det:{camera_id}", json.dumps(payload))

            # Persist alert if any EPI violation detected
            if has_violation:
                _save_alert(camera_id, detections, frame)

        logger.info(
            "inference_stopped: camera=%s, frames_processed=%d",
            camera_id,
            frames_processed,
        )
        return {
            "camera_id": camera_id,
            "frames_processed": frames_processed,
            "status": "completed",
        }

    except Exception as exc:
        logger.error(
            "inference_failed: camera=%s, error=%s",
            camera_id,
            exc,
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=30)

    finally:
        cap.release()


@celery.task(bind=True, queue="inference", name="tasks.inference.start_hls_stream")
def start_hls_stream(self, camera_id: str, rtsp_url: str) -> dict:
    """Inicia FFmpeg convertendo RTSP -> HLS.

    Salva em /tmp/hls/{camera_id}/stream.m3u8
    Flask serve via GET /api/cameras/<id>/stream/<file>
    """
    try:
        hls_dir = f"/tmp/hls/{camera_id}"
        os.makedirs(hls_dir, exist_ok=True)

        hls_segment_time = int(os.environ.get("HLS_SEGMENT_TIME", "2"))
        hls_list_size = int(os.environ.get("HLS_LIST_SIZE", "3"))

        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-f", "hls",
            "-hls_time", str(hls_segment_time),
            "-hls_list_size", str(hls_list_size),
            "-hls_flags", "delete_segments",
            f"{hls_dir}/stream.m3u8",
        ]

        logger.info("hls_stream_start: camera=%s", camera_id)

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        return {
            "camera_id": camera_id,
            "pid": process.pid,
            "hls_path": f"{hls_dir}/stream.m3u8",
            "status": "started",
        }

    except Exception as exc:
        logger.error(
            "hls_stream_failed: camera=%s, error=%s",
            camera_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc, countdown=15)
