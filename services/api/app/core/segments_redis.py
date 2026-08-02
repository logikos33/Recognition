"""
Recognition — Redis client dedicado aos segmentos de vídeo do live view.

Contexto (mutirão item 1.6): o Redis de produção roda `maxmemory=0` +
`noeviction`. As chaves de segmento HLS empurradas pelo edge
(`epi:edge_hls:{camera_id}:{filename}`, TTL ~20s) e o estado "tem espectador
agora"/lock de FFmpeg (`epi:stream:{camera_id}:active`,
`epi:stream:{camera_id}:ffmpeg_lock`) compartilham a MESMA instância com o
estado de SEGURANÇA — a blocklist de JWT revogado (`revoked_jti:*`, ver
app/domain/services/session_service.py). Com `noeviction`, uma instância
cheia de tráfego de segmento faz as escritas falharem — inclusive as de
segurança.

`allkeys-lru` foi DESCARTADO por decisão: despejaria `revoked_jti:*` também
(um token revogado voltaria a valer). A separação real é rotear o tráfego de
segmento pra uma instância/DB distinta via `SEGMENTS_REDIS_URL`. Ver
docs/runbooks/REDIS_SEGMENTS_SEPARATION.md para como provisionar e o
fallback (`volatile-ttl` + TTL do `revoked_jti:*` >= vida restante do token)
quando a infra não permitir uma instância dedicada.

Uso: todo leitor/escritor de `epi:edge_hls:*` ou `epi:stream:*` deve passar
por get_segments_redis()/get_segments_redis_binary() — nunca montar um
client próprio com REDIS_URL para essas chaves, ou a separação fica
inconsistente entre quem escreve e quem lê a MESMA chave (ex.: `:active` é
escrita por stream_handlers.serve_hls e lida por
edge/routes.list_live_view_wanted — os dois precisam apontar pro mesmo
Redis).
"""
import os


def segments_redis_url() -> str:
    """URL efetiva do Redis de segmentos.

    `SEGMENTS_REDIS_URL` se setada; senão a mesma `REDIS_URL` padrão usada
    pelo resto do sistema — comportamento atual INALTERADO quando a env não
    existe (zero mudança silenciosa de default).
    """
    return os.environ.get("SEGMENTS_REDIS_URL") or os.environ.get(
        "REDIS_URL", "redis://localhost:6379"
    )


def get_segments_redis():  # type: ignore[no-untyped-def]
    """Cliente Redis (texto, decode_responses=True) para `epi:stream:*`."""
    import redis as _redis  # noqa: PLC0415
    return _redis.from_url(segments_redis_url(), socket_timeout=5, decode_responses=True)


def get_segments_redis_binary():  # type: ignore[no-untyped-def]
    """Variante binária (sem decode_responses) — segmento `.ts` não é UTF-8."""
    import redis as _redis  # noqa: PLC0415
    return _redis.from_url(segments_redis_url(), socket_timeout=5)
