"""
Módulo de Qualidade — Segurança de acesso a vídeos e clips.

Regras obrigatórias:
- r2_key DEVE começar com "quality-" — rejeitar qualquer outro prefixo
- Tenant extraído do r2_key deve bater com tenant_schema do JWT
- TTL máximo: 900s (nunca aceitar maior)
- Presigned GET sem ResponseContentDisposition de nenhum tipo
- Rate limit: 60 URLs por user por hora via Redis
- Todo acesso registrado em public.quality_video_access_log
- Andon: aceito apenas de IPs internos (exceto ANDON_ALLOW_EXTERNAL=true)
"""
import ipaddress
import logging
import os

logger = logging.getLogger(__name__)

# TTL máximo absoluto para presigned URLs de vídeo — nunca ultrapassar
MAX_VIDEO_URL_TTL = 900

# Rate limit: max requests por user por hora
RATE_LIMIT_MAX = 60
RATE_LIMIT_WINDOW = 3600  # 1 hora em segundos

# Prefixos R2 válidos para o módulo qualidade
VALID_QUALITY_PREFIXES = (
    "quality-recordings/",
    "quality-clips/",
    "quality-frames/",
    "quality-models/",
    "quality-snapshots/",
)

# Redes privadas aceitas para o monitor Andon
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]


class SecurityError(Exception):
    """Tentativa de acesso não autorizado a recurso de qualidade."""


class RateLimitError(Exception):
    """Rate limit de URLs de vídeo excedido."""


def _extract_tenant_from_key(r2_key: str) -> str | None:
    """
    Extrai o tenant_schema do r2_key.

    Formato esperado: quality-{type}/{tenant_schema}/...
    Ex: quality-clips/rvb/camera-123/inspection-456.mp4 → 'rvb'
    """
    parts = r2_key.split("/")
    if len(parts) >= 2:
        return parts[1]
    return None


def _check_rate_limit(user_id: str) -> None:
    """
    Verifica rate limit de 60 URLs por usuário por hora.
    Incrementa contador Redis. Raises RateLimitError se excedido.
    """
    try:
        import redis as _redis
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        r = _redis.from_url(redis_url, decode_responses=True, socket_timeout=3)
        key = f"quality:ratelimit:{user_id}"
        count = r.incr(key)
        if count == 1:
            r.expire(key, RATE_LIMIT_WINDOW)
        if count > RATE_LIMIT_MAX:
            logger.warning("quality_video_rate_limit: user=%s count=%d", user_id, count)
            raise RateLimitError(f"Limite de {RATE_LIMIT_MAX} URLs de vídeo por hora excedido")
    except RateLimitError:
        raise
    except Exception as exc:
        # Se Redis falhar, não bloquear o acesso — apenas logar
        logger.warning("quality_ratelimit_redis_error: user=%s err=%s", user_id, exc)


def _log_access(
    user_id: str,
    tenant_schema: str,
    resource_type: str,
    resource_id: str,
    ip_address: str | None,
) -> None:
    """
    Registra acesso a vídeo em public.quality_video_access_log.
    Best-effort — nunca falha a requisição original.
    """
    try:
        from app.infrastructure.database.connection import DatabasePool
        pool = DatabasePool.get_instance()
        if pool is None:
            return
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO public.quality_video_access_log
                    (user_id, tenant_schema, resource_type, resource_id, ip_address)
                VALUES (%s, %s, %s, %s, %s::inet)
                """,
                (user_id, tenant_schema, resource_type, resource_id, ip_address),
            )
    except Exception as exc:
        logger.warning("quality_access_log_error: user=%s err=%s", user_id, exc)


def generate_quality_view_url(
    r2_key: str,
    tenant_schema: str,
    user_id: str,
    resource_type: str,
    resource_id: str,
    ttl: int = 900,
    ip_address: str | None = None,
) -> dict:
    """
    Gera presigned GET URL para recurso de vídeo do módulo qualidade.

    Segurança obrigatória:
    1. r2_key deve começar com prefixo "quality-*"
    2. Tenant extraído do r2_key deve coincidir com tenant_schema do JWT
    3. TTL forçado a máximo 900s
    4. Rate limit 60/hora por usuário
    5. Sem ResponseContentDisposition (nunca attachment)
    6. INSERT em quality_video_access_log

    Returns:
        {"url": str, "expires_in": int}
    Raises:
        SecurityError: acesso não autorizado
        RateLimitError: limite excedido
    """
    # 1. Validar prefixo — rejeitar qualquer chave que não seja do módulo qualidade
    if not any(r2_key.startswith(p) for p in VALID_QUALITY_PREFIXES):
        logger.error(
            "quality_video_invalid_prefix: user=%s key_prefix=%s",
            user_id,
            r2_key[:30],
        )
        raise SecurityError("Acesso negado: recurso fora do módulo qualidade")

    # 2. Validar isolamento de tenant
    key_tenant = _extract_tenant_from_key(r2_key)
    if key_tenant != tenant_schema:
        logger.error(
            "quality_video_tenant_mismatch: user=%s key_tenant=%s jwt_tenant=%s",
            user_id,
            key_tenant,
            tenant_schema,
        )
        raise SecurityError("Acesso negado: recurso pertence a outro tenant")

    # 3. Cap do TTL — nunca aceitar maior que 900s
    safe_ttl = min(ttl, MAX_VIDEO_URL_TTL)

    # 4. Rate limit
    _check_rate_limit(user_id)

    # 5. Gerar presigned URL sem Content-Disposition
    try:
        from app.infrastructure.storage.r2_storage import R2Storage
        storage = R2Storage.get_instance()
        url = storage.generate_presigned_download_url(r2_key, expires_in=safe_ttl)
    except Exception as exc:
        logger.error("quality_video_presign_error: key=%s err=%s", r2_key[:50], exc)
        raise

    # 6. Registrar acesso (best-effort, não falha)
    _log_access(user_id, tenant_schema, resource_type, resource_id, ip_address)

    logger.info(
        "quality_video_url_generated: user=%s type=%s ttl=%d",
        user_id,
        resource_type,
        safe_ttl,
    )

    return {"url": url, "expires_in": safe_ttl}


def verify_andon_access(remote_addr: str) -> bool:
    """
    Verifica se o IP remoto tem permissão para acessar o monitor Andon.

    Aceita apenas redes privadas (192.168.x.x, 10.x.x.x, 172.16-31.x.x, 127.x.x.x)
    a menos que ANDON_ALLOW_EXTERNAL=true esteja configurado (modo dev).

    Args:
        remote_addr: IP do cliente (request.remote_addr)

    Returns:
        True se acesso permitido, False caso contrário
    """
    # Modo desenvolvimento — aceitar qualquer IP
    if os.environ.get("ANDON_ALLOW_EXTERNAL", "false").lower() == "true":
        return True

    if not remote_addr:
        return False

    try:
        ip = ipaddress.ip_address(remote_addr)
        return any(ip in network for network in _PRIVATE_NETWORKS)
    except ValueError:
        logger.warning("andon_invalid_ip: addr=%s", remote_addr)
        return False
