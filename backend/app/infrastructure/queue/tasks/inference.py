"""
EPI Monitor V2 — Inference + HLS Tasks.

Celery tasks para inferência YOLO contínua e HLS streaming.
Rodam no Railway worker service.
"""
import json
import logging
import os
import subprocess

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, queue="inference", max_retries=5, name="tasks.inference.inference_loop")
def inference_loop(self, camera_id: str, rtsp_url: str, model_path: str = "yolov8n.pt") -> dict:
    """Loop de inferência YOLO por câmera.

    1. Carrega modelo YOLOv8
    2. Conecta stream RTSP via OpenCV
    3. A cada N frames: roda inferência
    4. Publica detecções no Redis
    5. Salva alertas no PostgreSQL via R2
    """
    try:
        logger.info(
            "inference_start: camera=%s, model=%s",
            camera_id, model_path,
        )

        # Implementação completa requer:
        # - cv2.VideoCapture(rtsp_url) com buffer mínimo
        # - YOLO model loading (cache em /tmp/models/)
        # - Redis pub/sub para detecções
        # - Alert saving para violations

        # Estrutura do loop:
        # while camera_active(camera_id):
        #     ret, frame = cap.read()
        #     if frame_count % N == 0:
        #         results = model(frame)
        #         detections = parse(results)
        #         redis.publish(f"det:{camera_id}", json.dumps(detections))
        #         if has_violation(detections):
        #             save_alert(camera_id, detections, frame)

        return {
            "camera_id": camera_id,
            "status": "completed",
        }

    except Exception as exc:
        logger.error(
            "inference_failed: camera=%s, error=%s",
            camera_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc, countdown=30)


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
