"""
Recognition — Celery Tasks: Inferência ONNX + HLS Streaming.

Tasks:
  - inference_loop: Loop contínuo de inferência por câmera.
  - start_hls_stream: FFmpeg RTSP→HLS transcoding.

Detector backend selecionável via env:
  DETECTOR_BACKEND = yolox_onnx | rfdetr_onnx | ultralytics  (padrão: yolox_onnx)
  DETECTOR_MODEL_PATH = /path/to/model.onnx  (padrão: models/yolox_s.onnx)
  VIOLATION_CLASSES = no_helmet,no_vest,no_gloves  (classes que geram alerta)
  DETECTION_CONFIDENCE_THRESHOLD = 0.5

Task-055a: caminho de inferência servido NÃO usa ultralytics (AGPL-3.0).
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

# ── Configuração do detector ──────────────────────────────────────────────────

_DETECTOR_BACKEND: str = os.environ.get("DETECTOR_BACKEND", "yolox_onnx")
_DETECTOR_MODEL_PATH: str = os.environ.get(
    "DETECTOR_MODEL_PATH",
    os.environ.get("YOLO_MODEL_PATH", "models/yolox_s.onnx"),
)
_DETECTION_CONFIDENCE: float = float(
    os.environ.get("DETECTION_CONFIDENCE_THRESHOLD", "0.5")
)
# Classes que geram alerta de violação.
# Para modelos EPI: "no_helmet,no_vest,no_gloves".
# Para teste com COCO pré-treinado: setar VIOLATION_CLASSES=person.
_VIOLATION_CLASSES: set[str] = {
    c.strip()
    for c in os.environ.get("VIOLATION_CLASSES", "no_helmet,no_vest,no_gloves").split(",")
    if c.strip()
}
_INFERENCE_EVERY_N: int = int(os.environ.get("YOLO_INFERENCE_EVERY_N_FRAMES", "5"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_redis_client():
    import redis  # noqa: PLC0415
    return redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379"),
        decode_responses=True,
    )


def _is_stream_active(camera_id: str, r) -> bool:
    return bool(r.exists(f"epi:stream:{camera_id}:active"))


def _has_violation(detections: list[dict]) -> bool:
    """True se qualquer detecção é de uma classe que gera alerta."""
    return any(d["class"] in _VIOLATION_CLASSES for d in detections)


def _save_alert(camera_id: str, detections: list[dict], frame) -> None:
    """Salva alerta: frame no storage + registro no banco."""
    try:
        import cv2  # noqa: PLC0415

        from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
        from app.infrastructure.database.repositories.alert_repository import (  # noqa: PLC0415
            AlertRepository,
        )
        from app.infrastructure.storage.local_storage import get_storage  # noqa: PLC0415

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
        evidence_key = f"evidence/{camera_id}/{timestamp}.jpg"

        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            logger.error("alert_frame_encode_failed: camera=%s", camera_id)
            return

        storage = get_storage()
        storage.upload_bytes(evidence_key, buf.tobytes(), "image/jpeg")

        avg_confidence = (
            sum(d["confidence"] for d in detections) / len(detections)
            if detections else 0.0
        )

        pool = DatabasePool.get_instance()
        if pool is None:
            logger.warning("alert_db_skip: DatabasePool not initialized")
            return

        AlertRepository(pool).create(
            camera_id=UUID(camera_id),
            violations=detections,
            confidence=round(avg_confidence, 3),
            evidence_key=evidence_key,
        )
        logger.info(
            "alert_saved: camera=%s evidence=%s violations=%d",
            camera_id, evidence_key, len(detections),
        )
    except Exception as exc:
        logger.error("alert_save_failed: camera=%s error=%s", camera_id, exc, exc_info=True)


# ── Cache do detector (singleton por processo) ────────────────────────────────

_detector_instance = None
_detector_lock = None


def _get_detector():
    """Retorna o detector singleton para este processo (lazy init, thread-safe)."""
    global _detector_instance, _detector_lock  # noqa: PLW0603
    import threading  # noqa: PLC0415

    if _detector_lock is None:
        _detector_lock = threading.Lock()

    with _detector_lock:
        if _detector_instance is None:
            from app.domain.detectors.factory import get_detector  # noqa: PLC0415
            _detector_instance = get_detector(
                backend=_DETECTOR_BACKEND,
                model_path=_DETECTOR_MODEL_PATH,
                confidence=_DETECTION_CONFIDENCE,
            )
            logger.info(
                "detector_initialized: backend=%s model=%s ready=%s",
                _DETECTOR_BACKEND, _DETECTOR_MODEL_PATH,
                _detector_instance.is_ready,
            )
    return _detector_instance


# ── Tasks ─────────────────────────────────────────────────────────────────────

@celery.task(
    bind=True,
    queue="inference",
    max_retries=5,
    name="tasks.inference.inference_loop",
)
def inference_loop(
    self,
    camera_id: str,
    rtsp_url: str,
    model_path: str | None = None,
) -> dict:
    """
    Loop de inferência ONNX por câmera.

    1. Obtém o detector singleton (ONNX — Apache 2.0 por padrão).
    2. Conecta stream RTSP via OpenCV.
    3. A cada N frames: roda inferência.
    4. Publica detecções no Redis (canal det:{camera_id}).
    5. Salva alertas no banco + storage em caso de violação.
    6. Para quando a chave epi:stream:{camera_id}:active sumir do Redis.

    model_path (obsoleto): ignorado — use DETECTOR_MODEL_PATH env.
    """
    import cv2  # noqa: PLC0415

    redis_client = _get_redis_client()
    detector = _get_detector()

    logger.info(
        "inference_start: camera=%s backend=%s every_n=%d",
        camera_id, _DETECTOR_BACKEND, _INFERENCE_EVERY_N,
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
            if frame_count % _INFERENCE_EVERY_N != 0:
                continue

            frames_processed += 1
            detections: list[dict] = []
            has_violation = False

            if detector.is_ready:
                detections = detector.predict(frame)
                has_violation = _has_violation(detections)

            payload = {
                "camera_id": camera_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "detections": detections,
                "has_violation": has_violation,
            }
            redis_client.publish(f"det:{camera_id}", json.dumps(payload))

            if has_violation:
                _save_alert(camera_id, detections, frame)

        logger.info(
            "inference_stopped: camera=%s frames_processed=%d",
            camera_id, frames_processed,
        )
        return {
            "camera_id": camera_id,
            "frames_processed": frames_processed,
            "status": "completed",
        }

    except Exception as exc:
        logger.error("inference_failed: camera=%s error=%s", camera_id, exc, exc_info=True)
        raise self.retry(exc=exc, countdown=30)

    finally:
        cap.release()


@celery.task(
    bind=True,
    queue="inference",
    name="tasks.inference.start_hls_stream",
)
def start_hls_stream(self, camera_id: str, rtsp_url: str) -> dict:
    """
    Inicia FFmpeg convertendo RTSP → HLS.
    Salva em /tmp/hls/{camera_id}/stream.m3u8
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
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        return {
            "camera_id": camera_id,
            "pid": process.pid,
            "hls_path": f"{hls_dir}/stream.m3u8",
            "status": "started",
        }

    except Exception as exc:
        logger.error("hls_stream_failed: camera=%s error=%s", camera_id, exc, exc_info=True)
        raise self.retry(exc=exc, countdown=15)
