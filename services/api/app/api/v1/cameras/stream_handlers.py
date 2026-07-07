"""
Recognition — Stream handlers for camera routes.

Handlers: start_stream, stop_stream, stream_status, serve_hls.
"""
import json as _json
import logging
import os
import re
import uuid as _uuid

from flask import request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error

from .helpers import _get_camera_service, _is_admin, _get_redis, _is_gateway_online

logger = logging.getLogger(__name__)

_SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_.-]+$')
# Aligns with HLS_INACTIVITY_TIMEOUT in local_stream_manager — watchdog kills
# streams whose active key expired.  Old default (3600s) kept streams alive for
# an hour after the last viewer left; 30s matches the watchdog intent.
_HLS_INACTIVITY_TTL = int(os.environ.get("HLS_INACTIVITY_TIMEOUT", "30"))


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
        # task-067: live view prefers the substream (live_view_subtype) for
        # lower latency. Does not affect /api/cameras/test (connectivity
        # check), which still calls build_stream_url without for_live_view.
        rtsp_url = service.build_stream_url(UUID(camera_id), user_id, _is_admin(user_id), for_live_view=True)

        r = _get_redis()
        r.setex(f"epi:stream:{camera_id}:active", _HLS_INACTIVITY_TTL, "1")

        if _is_gateway_online(r):
            cmd = {
                "action": "start_stream",
                "camera_id": camera_id,
                "rtsp_url": rtsp_url,
                "hls_segment_time": int(os.environ.get("HLS_SEGMENT_TIME", "1")),
                "hls_list_size": int(os.environ.get("HLS_LIST_SIZE", "3")),
            }
            r.publish("gateway:commands", _json.dumps(cmd))
            dispatch_mode = "gateway"
            logger.info("start_stream: gateway dispatch, camera=%s", camera_id)
        else:
            # Run FFmpeg locally so serve_hls can find /tmp/hls/ in this same container.
            # Dispatching to Celery would write to the inference container's /tmp/hls/,
            # which is invisible to the API container — causing 404 on serve_hls.
            from .local_stream_manager import LocalStreamManager  # noqa: PLC0415

            # task-067: cheap string-only computation (no I/O/FFmpeg) of the main
            # stream URL, passed as runtime fallback in case the substream isn't
            # actually configured on the camera hardware. Only used if it differs
            # from the primary URL (e.g. rtsp_url_override makes both identical).
            fallback_rtsp_url = None
            try:
                candidate = service.build_stream_url(
                    UUID(camera_id), user_id, _is_admin(user_id), subtype_override=0
                )
                if candidate != rtsp_url:
                    fallback_rtsp_url = candidate
            except EpiMonitorError:
                fallback_rtsp_url = None

            LocalStreamManager.get_instance().start(
                camera_id=camera_id, rtsp_url=rtsp_url, fallback_rtsp_url=fallback_rtsp_url
            )
            dispatch_mode = "local"
            logger.info("start_stream: local ffmpeg dispatch, camera=%s", camera_id)

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
        from .local_stream_manager import LocalStreamManager  # noqa: PLC0415
        LocalStreamManager.get_instance().stop(camera_id)
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

        # Guard-rail 1: surface FFmpeg error when local process is dead
        ffmpeg_info: dict = {}  # type: ignore[type-arg]
        if not gateway_online:
            try:
                from .local_stream_manager import LocalStreamManager  # noqa: PLC0415
                ffmpeg_info = LocalStreamManager.get_instance().status(camera_id)
            except Exception:
                pass

        return success({
            "camera_id": camera_id,
            "streaming": active,
            "gateway_online": gateway_online,
            "ttl_seconds": ttl,
            "ffmpeg_running": ffmpeg_info.get("running"),
            "ffmpeg_error": ffmpeg_info.get("stderr_tail") if not ffmpeg_info.get("running") else None,
        })
    except Exception as exc:
        logger.error("stream_status_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def serve_hls(camera_id: str, filename: str):  # type: ignore[no-untyped-def]
    """Serve HLS segments. No JWT — hls.js cannot send auth headers.

    Proxies to camera-gateway when it is online (FFmpeg runs there).
    Falls back to local /tmp/hls/ for single-process dev setups.
    """
    try:
        _uuid.UUID(camera_id)
    except ValueError:
        return error("Camera ID inválido", 400)
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
    # Renew activity key so the watchdog keeps this stream alive while a viewer is watching.
    try:
        _inactivity_timeout = int(os.environ.get("HLS_INACTIVITY_TIMEOUT", "30"))
        r_local = _get_redis()
        r_local.setex(f"epi:stream:{camera_id}:active", _inactivity_timeout, "1")
    except Exception:
        pass  # Redis unavailable — watchdog will eventually time out

    hls_dir = f"/tmp/hls/{camera_id}"
    hls_path = os.path.join(hls_dir, filename)

    # serve_hls is unauthenticated (hls.js can't send auth headers).
    # send_from_directory raises werkzeug.exceptions.NotFound — not FileNotFoundError —
    # so we must check with os.path.isfile() before attempting to serve.
    if os.path.isfile(hls_path):
        from flask import send_from_directory
        return send_from_directory(hls_dir, filename)

    # GR-6a — Lazy-start: auto-start FFmpeg on first .m3u8 request.
    # The camera_id UUID was served via a JWT-authenticated request, so the caller
    # has already proved ownership. The ownership re-check is intentionally skipped here.
    _lazy_started = False
    try:
        from .local_stream_manager import LocalStreamManager  # noqa: PLC0415
        mgr = LocalStreamManager.get_instance()
        if not mgr.is_running(camera_id):
            try:
                from uuid import UUID as _UUID  # noqa: PLC0415
                from app.domain.services.camera_service import CameraService  # noqa: PLC0415
                from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
                from app.infrastructure.database.repositories.camera_repository import CameraRepository  # noqa: PLC0415
                pool = DatabasePool.get_instance()
                if pool is not None:
                    fernet_key = os.environ.get("CAMERA_SECRET_KEY", "")
                    svc = CameraService(CameraRepository(pool), fernet_key)
                    rtsp_url = svc.build_stream_url_for_lazy_start(_UUID(camera_id))

                    # task-067: cheap string-only computation (no I/O/FFmpeg) of
                    # the main stream URL as runtime fallback in case the
                    # substream isn't actually configured on the hardware.
                    fallback_rtsp_url = None
                    try:
                        candidate = svc.build_stream_url_for_lazy_start(
                            _UUID(camera_id), subtype_override=0
                        )
                        if candidate != rtsp_url:
                            fallback_rtsp_url = candidate
                    except EpiMonitorError:
                        fallback_rtsp_url = None

                    result = mgr.start(
                        camera_id=camera_id, rtsp_url=rtsp_url, fallback_rtsp_url=fallback_rtsp_url
                    )
                    _lazy_started = result.get("status") in (
                        "started", "already_starting", "already_running"
                    )
                    logger.info(
                        "serve_hls_lazy_start: camera=%s result=%s",
                        camera_id, result.get("status"),
                    )
                else:
                    logger.warning(
                        "serve_hls_lazy_start_failed: camera=%s reason=db_pool_not_initialized",
                        camera_id,
                    )
            except Exception as exc:
                logger.warning("serve_hls_lazy_start_failed: camera=%s error=%s", camera_id, exc)
        else:
            _lazy_started = True

        st = mgr.status(camera_id)
        if not st.get("running") and st.get("stderr_tail"):
            logger.warning(
                "serve_hls_ffmpeg_error: camera=%s error=%s",
                camera_id, st["stderr_tail"][-200:],
            )
    except Exception as exc:
        logger.debug("serve_hls_lazy_start_error: camera=%s: %s", camera_id, exc)

    if _lazy_started:
        # FFmpeg is initialising — tell hls.js to retry in 2 seconds.
        from flask import Response  # noqa: PLC0415
        return Response("Stream initializing", status=425, headers={"Retry-After": "2"})

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

        # Módulo passado pelo frontend via ?module=fueling — evita lookup de schema
        camera_module: str | None = request.args.get("module") or None

        # Tenta obter vídeo demo (retorna None se não for superadmin)
        try:
            demo = demo_video_service.get_for_camera(camera_id, role, module=camera_module)
        except Exception as exc:
            logger.warning("stream_info_demo_check_failed camera=%s: %s", camera_id, exc)
            demo = None

        if demo:
            return success({
                "type": "demo_video",
                "url": demo["r2_url"],
                "label": demo.get("label"),
            })

        # A6: dual-mode — edge site with deployment_mode='edge' gets its own type
        # so the frontend can label/display the feed appropriately.
        # Any failure here is non-fatal: falls back to standard 'hls'.
        stream_type = "hls"
        try:
            from app.core.auth import get_tenant_id
            from app.infrastructure.database.connection import DatabasePool
            from app.infrastructure.database.repositories.camera_repository import CameraRepository
            from app.infrastructure.database.repositories.edge_site_repository import EdgeSiteRepository

            pool = DatabasePool.get_instance()
            if pool is not None:
                tenant_id = get_tenant_id()
                cam = CameraRepository(pool).get_by_id_and_tenant(camera_id, tenant_id)
                if cam and cam.get("site_id"):
                    site = EdgeSiteRepository(pool).get_site_by_id(str(cam["site_id"]), tenant_id)
                    if site and site.get("deployment_mode") == "edge":
                        stream_type = "edge_hls"
        except Exception as exc:
            logger.warning("stream_info_site_check_failed camera=%s: %s", camera_id, exc)

        return success({
            "type": stream_type,
            "url": f"/api/cameras/{camera_id}/stream/stream.m3u8",
        })

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("stream_info_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
