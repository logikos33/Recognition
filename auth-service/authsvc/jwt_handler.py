import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from . import config


def create_access_token(user_id: str, email: str, role: str, tenant_id: str = "") -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sub": user_id, "email": email, "role": role,
        "tenant_id": tenant_id, "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    }, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sub": user_id, "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=config.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    }, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
    except Exception:
        return None


def decode_unsafe(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, config.JWT_SECRET_KEY,
                          algorithms=[config.JWT_ALGORITHM],
                          options={"verify_exp": False})
    except Exception:
        return None
