"""
Admin Introspection Route — diagnóstico de recursos do processo (mutirão 1.2).

Blueprint /api/v1/admin:
  GET /introspection — payload cru de recursos do worker vivo, o que separa
  "platô" de "vazamento" de memória numa investigação de produção. Sem esta
  rota a investigação de memória sempre parte do zero.

Campos do payload:
  ru_maxrss        — resource.getrusage(RUSAGE_SELF).ru_maxrss cru (unidade
                      depende do SO: KB no Linux, bytes no macOS) +
                      ru_maxrss_mb já normalizado por sys.platform.
  rss_current_mb   — VmRSS de /proc/self/status (Linux/produção). None fora
                      do Linux ou se o arquivo não existir (dev macOS/sandbox).
  uptime_seconds   — desde o import deste módulo (_PROCESS_START).
  requests_served  — contador in-process, POR WORKER, incrementado via
                      before_app_request registrado por este blueprint.
                      NÃO é cross-worker (cada processo gunicorn/gevent tem
                      seu próprio contador) e zera a cada recycle do worker.
  storage_backend  — "r2" | "local" | "desconhecido", derivado de
                      type(get_storage()).__name__.
  worker_class     — "gevent" se o módulo já estiver carregado (proxy do
                      worker class real do gunicorn/socketio), senão
                      "sync/desconhecido".
  service_type     — os.environ.get("SERVICE_TYPE") (api/worker/...).
  live_view        — gauges do live-view via edge lidos do Redis
                      (epi:edge_hls:* e epi:stream:*:active) via SCAN —
                      NUNCA KEYS. Não instrumenta o caminho quente de
                      stream_handlers.py (outros PRs do mutirão mexem
                      nesse arquivo — decisão já tomada). Redis fora →
                      campos None + degraded=true; a rota ainda responde
                      200 (é diagnóstico, não pode derrubar o painel).

Segurança: @require_superadmin (issue #787). Era `@require_admin` até
09/2026 — e o argumento de que "não tem dado de tenant" é justamente o
motivo de NÃO ser de admin de tenant: memória, uptime, requests servidos,
backend de storage, worker class e o agregado de live view são telemetria
de infraestrutura da PLATAFORMA, do processo inteiro. Conta de cliente não
inspeciona o processo que serve os outros clientes.
"""
import logging
import os
import resource
import sys
import threading
import time

from flask import Blueprint

from app.core.responses import error, success
from app.core.tenant import require_superadmin

logger = logging.getLogger(__name__)

admin_introspection_bp = Blueprint(
    "admin_introspection", __name__, url_prefix="/api/v1/admin"
)

# Marca de início do processo — módulo é importado uma vez por worker no boot.
_PROCESS_START = time.monotonic()

_requests_served = 0
_requests_lock = threading.Lock()


@admin_introspection_bp.before_app_request
def _count_request() -> None:
    """Incrementa o contador in-process a cada requisição servida por este worker.

    Registrado via before_app_request (dispara para TODAS as rotas do app,
    não só as deste blueprint) no momento em que este blueprint é registrado
    em app/__init__.py::_register_blueprints — mesmo ponto onde os demais
    blueprints/hooks admin são inicializados.
    """
    global _requests_served  # noqa: PLW0603
    with _requests_lock:
        _requests_served += 1


def _get_requests_served() -> int:
    with _requests_lock:
        return _requests_served


def _ru_maxrss_mb(raw: int) -> float:
    """Normaliza ru_maxrss para MB — Linux reporta KB, macOS reporta bytes."""
    if sys.platform == "darwin":
        return round(raw / (1024 * 1024), 2)
    return round(raw / 1024, 2)


def _rss_current_mb() -> float | None:
    """Lê VmRSS de /proc/self/status (Linux). None fora do Linux / sandbox."""
    try:
        with open("/proc/self/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    kb = int(line.split()[1])
                    return round(kb / 1024, 2)
    except (OSError, ValueError, IndexError):
        return None
    return None


def _storage_backend() -> str:
    """"r2" | "local" | "desconhecido" — nunca derruba a rota por credencial parcial."""
    try:
        from app.infrastructure.storage.local_storage import get_storage  # noqa: PLC0415

        storage_cls = type(get_storage()).__name__
    except Exception as exc:  # noqa: BLE001
        logger.warning("introspection_storage_backend_failed: %s", exc)
        return "desconhecido"
    return "r2" if storage_cls == "R2Storage" else "local"


def _worker_class() -> str:
    return "gevent" if "gevent" in sys.modules else "sync/desconhecido"


def _get_redis():  # type: ignore[no-untyped-def]
    """Cliente Redis com timeout curto — só leitura de gauges, nunca escreve."""
    import redis as _redis  # noqa: PLC0415

    return _redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379"),
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def _live_view_snapshot() -> dict:
    """Gauges do live-view via edge (epi:edge_hls:*, epi:stream:*:active).

    SCAN nunca KEYS (produção com muitas chaves). Lê apenas — não toca em
    stream_handlers.py, que outros PRs do mutirão estão alterando em paralelo.
    """
    try:
        r = _get_redis()

        segments_buffered = 0
        bytes_buffered = 0
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match="epi:edge_hls:*", count=100)
            for key in keys:
                segments_buffered += 1
                try:
                    bytes_buffered += int(r.strlen(key))
                except Exception:  # noqa: BLE001
                    logger.warning("introspection_strlen_failed: key=%s", key)
            if cursor == 0:
                break

        streams_active = 0
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match="epi:stream:*:active", count=100)
            streams_active += len(keys)
            if cursor == 0:
                break

        avg_segment_bytes = (
            round(bytes_buffered / segments_buffered, 2) if segments_buffered else 0
        )
        return {
            "segments_buffered": segments_buffered,
            "bytes_buffered": bytes_buffered,
            "avg_segment_bytes": avg_segment_bytes,
            "streams_active": streams_active,
            "degraded": False,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("introspection_live_view_degraded: %s", exc)
        return {
            "segments_buffered": None,
            "bytes_buffered": None,
            "avg_segment_bytes": None,
            "streams_active": None,
            "degraded": True,
        }


@admin_introspection_bp.route("/introspection", methods=["GET"])
@require_superadmin
def introspection():
    """Diagnóstico de recursos do processo — separa platô de vazamento de memória."""
    try:
        raw_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        payload = {
            "ru_maxrss": raw_maxrss,
            "ru_maxrss_mb": _ru_maxrss_mb(raw_maxrss),
            "rss_current_mb": _rss_current_mb(),
            "uptime_seconds": round(time.monotonic() - _PROCESS_START, 2),
            "requests_served": _get_requests_served(),
            "storage_backend": _storage_backend(),
            "worker_class": _worker_class(),
            "service_type": os.environ.get("SERVICE_TYPE"),
            "live_view": _live_view_snapshot(),
        }
        return success(payload)
    except Exception as exc:  # noqa: BLE001
        logger.error("introspection_error: %s", exc, exc_info=True)
        return error("Erro ao coletar introspecção do processo", 500)
