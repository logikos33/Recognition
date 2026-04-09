"""
EPI Monitor V2 — Camera Routes.

CRUD de câmeras IP + controle de stream.
Senhas SEMPRE criptografadas — NUNCA retornadas na API.
"""
import json as _json
import logging
import os
import re

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error
from app.domain.services.camera_service import CameraService
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.camera_repository import CameraRepository
from app.infrastructure.database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

cameras_bp = Blueprint("cameras", __name__, url_prefix="/api/cameras")


def _get_camera_service() -> CameraService:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    fernet_key = os.environ.get("CAMERA_SECRET_KEY", "")
    return CameraService(CameraRepository(pool), fernet_key)


def _is_admin(user_id) -> bool:  # type: ignore[no-untyped-def]
    pool = DatabasePool.get_instance()
    if pool is None:
        return False
    repo = UserRepository(pool)
    user = repo.get_by_id(user_id)
    return user is not None and user.get("role") == "admin"


def _get_redis():  # type: ignore[no-untyped-def]
    """Redis com timeout curto para checagens e dispatch de comandos."""
    import redis as _redis
    return _redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379"),
        socket_timeout=5,
        decode_responses=True,
    )


def _is_gateway_online(r) -> bool:  # type: ignore[no-untyped-def]
    try:
        return bool(r.exists("service:gateway:health"))
    except Exception:
        return False


def _is_inference_online(r) -> bool:  # type: ignore[no-untyped-def]
    try:
        return bool(r.exists("service:inference:health"))
    except Exception:
        return False


@cameras_bp.route("", methods=["GET"])
@jwt_required()
def list_cameras():  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - cameras
    summary: Listar câmeras do usuário
    security:
      - Bearer: []
    responses:
      200:
        description: Lista de câmeras
    """
    try:
        user_id = get_current_user_id()
        service = _get_camera_service()
        cameras = service.list_cameras(user_id, _is_admin(user_id))
        try:
            r = _get_redis()
            gw_raw = r.get("service:gateway:health")
            inf_raw = r.get("service:inference:health")
            gateway_status = _json.loads(gw_raw) if gw_raw else {"status": "offline"}
            inference_status = _json.loads(inf_raw) if inf_raw else {"status": "offline"}
        except Exception:
            gateway_status = {"status": "unavailable"}
            inference_status = {"status": "unavailable"}
        return success({
            "cameras": cameras,
            "gateway_status": gateway_status,
            "inference_status": inference_status,
        })
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_cameras_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@cameras_bp.route("", methods=["POST"])
@jwt_required()
def create_camera():  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - cameras
    summary: Criar nova câmera IP
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          required: [name, host]
          properties:
            name: {type: string, example: "Câmera Baia 1"}
            host: {type: string, example: "192.168.1.100"}
            manufacturer: {type: string, example: generic}
            port: {type: integer, example: 554}
            username: {type: string, example: admin}
            password: {type: string}
    responses:
      201:
        description: Câmera criada
      400:
        description: Dados inválidos
    """
    try:
        user_id = get_current_user_id()
        data = request.get_json() or {}
        service = _get_camera_service()
        camera = service.create_camera(user_id, data)
        return success(camera, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("create_camera_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@cameras_bp.route("/<camera_id>", methods=["GET"])
@jwt_required()
def get_camera(camera_id: str):  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - cameras
    summary: Obter câmera por ID
    security:
      - Bearer: []
    parameters:
      - in: path
        name: camera_id
        type: string
        required: true
    responses:
      200:
        description: Dados da câmera (sem senha)
      403:
        description: Sem permissão
      404:
        description: Câmera não encontrada
    """
    try:
        from uuid import UUID
        user_id = get_current_user_id()
        service = _get_camera_service()
        camera = service.get_camera(UUID(camera_id))
        # Ownership check: operator vê só suas câmeras
        if camera.get("user_id") and str(camera["user_id"]) != str(user_id) and not _is_admin(user_id):
            return error("Sem permissão", 403)
        return success(camera)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_camera_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@cameras_bp.route("/<camera_id>", methods=["DELETE"])
@jwt_required()
def delete_camera(camera_id: str):  # type: ignore[no-untyped-def]
    """
    ---
    tags:
      - cameras
    summary: Deletar câmera
    security:
      - Bearer: []
    parameters:
      - in: path
        name: camera_id
        type: string
        required: true
    responses:
      200:
        description: Câmera deletada
      403:
        description: Sem permissão
      404:
        description: Câmera não encontrada
    """
    try:
        from uuid import UUID
        user_id = get_current_user_id()
        service = _get_camera_service()
        service.delete_camera(UUID(camera_id), user_id, _is_admin(user_id))
        return success({"deleted": True})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("delete_camera_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@cameras_bp.route("/<camera_id>/stream/start", methods=["POST"])
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
        rtsp_url = service.build_rtsp_url(UUID(camera_id), user_id, _is_admin(user_id))

        r = _get_redis()
        r.setex(f"epi:stream:{camera_id}:active", 3600, "1")

        if _is_gateway_online(r):
            # Novo path: despacha para camera-gateway via Redis
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
            # Fallback: tarefas Celery existentes (gateway offline ou não deployado)
            from app.infrastructure.queue.tasks.inference import start_hls_stream, inference_loop  # noqa: PLC0415
            start_hls_stream.delay(camera_id=camera_id, rtsp_url=rtsp_url)
            model_path = os.environ.get("YOLO_MODEL_PATH", "yolov8n.pt")
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


@cameras_bp.route("/<camera_id>/stream/stop", methods=["POST"])
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


@cameras_bp.route("/<camera_id>/test", methods=["POST"])
@jwt_required()
def test_camera(camera_id: str):  # type: ignore[no-untyped-def]
    """Testa conectividade TCP da câmera (porta RTSP)."""
    import socket  # noqa: PLC0415
    import urllib.parse  # noqa: PLC0415
    from uuid import UUID
    try:
        user_id = get_current_user_id()
        service = _get_camera_service()
        rtsp_url = service.build_rtsp_url(UUID(camera_id), user_id, _is_admin(user_id))

        # Extrai host:port da URL RTSP (rtsp://user:pass@host:port/...)
        parsed = urllib.parse.urlparse(rtsp_url)
        host = parsed.hostname or ""
        port = parsed.port or 554

        if not host:
            return error("URL RTSP inválida — host não encontrado", 400)

        # Verifica conectividade TCP (não abre RTSP, mas confirma porta acessível)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            result = sock.connect_ex((host, port))
            reachable = result == 0
        finally:
            sock.close()

        if reachable:
            return success({"status": "connected", "rtsp_reachable": True, "host": host, "port": port})
        return error(f"Câmera inacessível em {host}:{port} — verifique IP, porta e rede", 400)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("test_camera_error: %s", exc, exc_info=True)
        return error("Erro ao testar câmera", 500)


@cameras_bp.route("/<camera_id>/stream/status", methods=["GET"])
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


@cameras_bp.route("/<camera_id>/model", methods=["GET"])
@jwt_required()
def get_camera_model(camera_id: str):  # type: ignore[no-untyped-def]
    """Retorna modelo YOLO ativo da câmera."""
    try:
        from uuid import UUID
        r = _get_redis()
        model_key = r.get(f"camera:model:{camera_id}")
        return success({
            "camera_id": camera_id,
            "model_key": model_key,
        })
    except Exception as exc:
        logger.error("get_camera_model_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


@cameras_bp.route("/<camera_id>/model", methods=["PUT"])
@jwt_required()
def set_camera_model(camera_id: str):  # type: ignore[no-untyped-def]
    """Define qual modelo YOLO a câmera usa."""
    try:
        data = request.get_json() or {}
        model_key = data.get("model_key", "")
        r = _get_redis()
        if model_key:
            r.set(f"camera:model:{camera_id}", model_key)
            r.publish(f"camera:model_change:{camera_id}", _json.dumps({
                "camera_id": camera_id,
                "model_key": model_key,
            }))
            logger.info("camera_model_set: camera=%s model=%s", camera_id, model_key)
        else:
            r.delete(f"camera:model:{camera_id}")
        return success({"camera_id": camera_id, "model_key": model_key or None})
    except Exception as exc:
        logger.error("set_camera_model_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


_SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_.-]+$')


@cameras_bp.route("/<camera_id>/stream/<path:filename>", methods=["GET"])
def serve_hls(camera_id: str, filename: str):  # type: ignore[no-untyped-def]
    """Serve HLS segments. No JWT — hls.js cannot send auth headers."""
    if not _SAFE_FILENAME.match(filename):
        return error("Filename inválido", 400)

    hls_dir = f"/tmp/hls/{camera_id}"
    from flask import send_from_directory
    try:
        return send_from_directory(hls_dir, filename)
    except FileNotFoundError:
        return error("Arquivo não encontrado", 404)
