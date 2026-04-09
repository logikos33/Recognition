import os
import redis as _redis
from . import config

_TTL = config.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400


def _r() -> _redis.Redis:
    return _redis.from_url(os.environ.get("REDIS_URL", ""), socket_timeout=5, decode_responses=True)


def store_refresh(user_id: str, token: str) -> None:
    _r().setex(f"refresh:{user_id}", _TTL, token)


def get_refresh(user_id: str) -> str | None:
    return _r().get(f"refresh:{user_id}")


def revoke_refresh(user_id: str) -> None:
    _r().delete(f"refresh:{user_id}")
