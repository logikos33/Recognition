"""
Factory de conexão Redis para o Inference Service.

Dois modos:
- padrão (socket_timeout=5): para PUBLISH/SET
- subscribe (socket_timeout=None): para psubscribe/listen bloqueante
"""
import os
import redis


def make_redis(for_subscribe: bool = False) -> redis.Redis:
    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    kwargs: dict = {"decode_responses": True}
    if for_subscribe:
        kwargs.update({
            "socket_timeout": None,
            "socket_keepalive": True,
            "health_check_interval": 25,
        })
    else:
        kwargs["socket_timeout"] = 5
    return redis.from_url(url, **kwargs)
