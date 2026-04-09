"""
EPI Monitor V2 — Camera route helpers.

Shared utilities used across camera route handlers.
"""
import os

from app.domain.services.camera_service import CameraService
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.camera_repository import CameraRepository
from app.infrastructure.database.repositories.user_repository import UserRepository


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
