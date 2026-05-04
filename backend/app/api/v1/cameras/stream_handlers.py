"""
Recognition — Stream handlers for camera routes.

Handlers: start_stream, stop_stream, stream_status, serve_hls.
"""
import json as _json
import logging
import os
import re

from flask import request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error

from .helpers import _get_camera_service, _is_admin, _get_redis, _is_gateway_online

logger = logging.getLogger(__name__)

_SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_.-]+$')


@jwt_required()
def start_stream(camera_id: str):  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - cameras
    summary: Iniciar stream HLS + inferência YOLO
    security:
      - Bearer: []
    parameters:
      - in: path
        name: camera_id
        type: string
        required: true
    responses:
      200:
        description: Stream iniciado
        schema:
          properties:
            camera_id: {type: string}
            hls_url: {type: string, example: /api/cameras/{id}/stream/stream.m3u8}
            status: {type: string, example: starting}
    """
    try:
        from uuid import UUID
        user_id = get_current_user_id()
        service = _get_camera_service()
        rtsp_url = service.build_stream_url(UUID(camera_id), user_id, _is_admin(user_id))

        r = _get_redis()
        r.setex(f"epi:stream:{camera_id}:active", 3600, "1")

        if _is_gateway_online(r):
            cmd = {
                "action": "start_stream",
                "camera_id": camera_id,
                "rtsp_url": rtsp_url,
                "hls_segment_time": int(os.environ.get("HLS_SEGMENT_TIME", "2")),
                "hls_list_size": int(os.environ.get("HLS_LIST_SIZE", "3")),
            }
            r.publish("gateway:commands", _json.dumps(cmd))
            dispatch_mode = "gateway"
            logger.info("start_stream: gateway dispatch, camera=%s", camera_id)
        else:
            from app.infrastructure.queue.tasks.inference import start_hls_stream, inference_loop  # noqa: PLC0415
            start_hls_stream.delay(camera_id=camera_id, rtsp_url=rtsp_url)
            model_path = os.environ.get("YOLO_MODEL_PATH", "yolo26n.pt")
            inference_loop.delay(camera_id=camera_id, rtsp_url=rtsp_url, model_path=model_path)
            dispatch_mode = "celery_fallback"
            logger.info("start_stream: celery fallback, camera=%s", camera_id)

        return success({
            "camera_id": camera_id,
            "rtsp_url_validated": True,
            "hls_url": f"/api/cameras/{camera_id}/stream/stream.m3u8",
            "status": "starting",
            "dispatch_mode": dispatch_mode,
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("start_stream_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@jwt_required()
def stop_stream(camera_id: str):  # type: ignore[no-untyped-def]
    """Para stream de uma câmera."""
    try:
        r = _get_redis()
        r.delete(f"epi:stream:{camera_id}:active")
        try:
            r.publish("gateway:commands", _json.dumps({"action": "stop_stream", "camera_id": camera_id}))
        except Exception as exc:
            logger.warning("stop_stream_gateway_publish_failed: %s", exc)
        return success({"camera_id": camera_id, "status": "stopped"})
    except Exception as exc:
        logger.error("stop_stream_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@jwt_required()
def stream_status(camera_id: str):  # type: ignore[no-untyped-def]
    """Status em tempo real do stream."""
    try:
        r = _get_redis()
        active = bool(r.exists(f"epi:stream:{camera_id}:active"))
        gateway_online = _is_gateway_online(r)
        ttl = r.ttl(f"epi:stream:{camera_id}:active") if active else -1
        return success({"camera_id": camera_id, "streaming": active,
                        "gateway_online": gateway_online, "ttl_seconds": ttl})
    except Exception as exc:
        logger.error("stream_status_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def serve_hls(camera_id: str, filename: str):  # type: ignore[no-untyped-def]
    """Serve HLS segments. No JWT — hls.js cannot send auth headers.

    Proxies to camera-gateway when it is online (FFmpeg runs there).
    Falls back to local /tmp/hls/ for single-process dev setups.
    """
    if not _SAFE_FILENAME.match(filename):
        return error("Filename inválido", 400)

    # Try gateway proxy first (production: separate containers)
    try:
        r = _get_redis()
        if _is_gateway_online(r):
            gateway_url = os.environ.get(
                "GATEWAY_INTERNAL_URL", "http://camera-gateway.railway.internal:8080"
            )
            import requests as _requests
            resp = _requests.get(
                f"{gateway_url}/hls/{camera_id}/{filename}",
                timeout=5,
                stream=True,
            )
            if resp.status_code == 200:
                from flask import Response
                headers = {}
                ct = resp.headers.get("Content-Type")
                if ct:
                    headers["Content-Type"] = ct
                return Response(
                    resp.iter_content(chunk_size=8192),
                    status=200,
                    headers=headers,
                )
    except Exception as exc:
        logger.debug("serve_hls_proxy_failed: %s", exc)

    # Fallback: local filesystem (dev or co-located FFmpeg)
    hls_dir = f"/tmp/hls/{camera_id}"
    from flask import send_from_directory
    try:
        return send_from_directory(hls_dir, filename)
    except FileNotFoundError:
        return error("Stream não disponível", 404)


@jwt_required()
def stream_info(camera_id: str):  # type: ignore[no-untyped-def]
    """
    Retorna o tipo de feed da câmera e a URL correspondente.

    Para superadmin com vídeo demo associado: type='demo_video', url=r2_url (loop MP4).
    Para todos os outros casos: type='hls', url=hls_url.

    ISOLAMENTO CRÍTICO: demo_video_service.get_for_camera() retorna None para
    qualquer role != superadmin, garantindo que clientes jamais recebam vídeos demo.
    """
    try:
        from app.core.auth import get_role
        from app.domain.services import demo_video_service

        role = get_role()

        # Tenta obter vídeo demo (retorna None se não for superadmin)
        try:
            camera_id_int = int(camera_id)
            demo = demo_video_service.get_for_camera(camera_id_int, role)
        except (ValueError, Exception) as exc:
            logger.warning("stream_info_demo_check_failed camera=%s: %s", camera_id, exc)
            demo = None

        if demo:
            return success({
                "type": "demo_video",
                "url": demo["r2_url"],
                "label": demo.get("label"),
            })

        # Feed HLS padrão
        return success({
            "type": "hls",
            "url": f"/api/cameras/{camera_id}/stream/stream.m3u8",
        })

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("stream_info_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
