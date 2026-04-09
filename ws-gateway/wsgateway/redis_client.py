"""Factory de conexão Redis — dois modos."""
import os
import redis as _redis


def make_redis(for_subscribe: bool = False) -> _redis.Redis:
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
    return _redis.from_url(url, **kwargs)
