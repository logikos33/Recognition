"""
Recognition — Operations Worker (runner de I/O do OperationsEngine).

Assina o stream de detecção do Redis (`det:{camera_id}`, mesmo canal que o
socket_bridge) e dirige o `OperationsEngine` para avaliar operações e popular
`operation_results` em produção — fora do /test (Bloco 3 do go-live RVB).

Também assina `operations:reload:{op_id}` para hot-reload quando o operador muda
uma operação na UI (D2 — reload estrutural sem derrubar o pipeline). O socket_bridge
já encaminha `operations:reload:*` e `operations:status:*` para o frontend; aqui só
CONSUMIMOS o reload (nunca republicamos reload — evita laço).

Padrão espelha `app/core/socket_bridge.py`: thread daemon, backoff exponencial,
conexão pubsub dedicada. Habilitado por env (`OPERATIONS_WORKER_ENABLED`) para não
surpreender ambientes que não querem o motor no processo da API.
"""
import json
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

_RELOAD_INTERVAL_S = 30.0   # recarrega o mapa inteiro periodicamente (rede de segurança)
_started = False
_lock = threading.Lock()


def _make_pubsub(redis_url: str):
    import redis

    r = redis.from_url(
        redis_url, socket_timeout=None, socket_keepalive=True, health_check_interval=25
    )
    ps = r.pubsub()
    ps.psubscribe("det:*", "operations:reload:*")
    return ps


def _make_publisher(redis_url: str):
    """Callable (channel, payload)->None para o engine emitir status/reload."""
    import redis

    r = redis.from_url(redis_url, socket_timeout=5, socket_keepalive=True)

    def _publish(channel: str, payload: dict) -> None:
        r.publish(channel, json.dumps(payload, default=str))

    return _publish


def _extract_frame(cam_id: str, data: dict) -> tuple[list, dict]:
    """Extrai (detections, frame_meta) do payload de `det:{camera_id}`.

    Tolerante ao formato: usa `data['detections']` se existir; frame_meta vem de
    `data['frame_meta']` ou é montado a partir de width/height/timestamp do payload.
    """
    detections = data.get("detections")
    if not isinstance(detections, list):
        detections = []
    frame_meta = data.get("frame_meta")
    if not isinstance(frame_meta, dict):
        frame_meta = {
            "camera_id": cam_id,
            "width": data.get("width", 640),
            "height": data.get("height", 360),
            "timestamp": data.get("timestamp"),
        }
    else:
        frame_meta.setdefault("camera_id", cam_id)
    return detections, frame_meta


def start_operations_worker() -> None:
    """Inicia o worker de operações (idempotente, opt-in por env).

    Requer `REDIS_URL` e `OPERATIONS_WORKER_ENABLED=true`.
    """
    global _started
    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        logger.info("operations_worker: REDIS_URL ausente — worker desabilitado")
        return
    if os.environ.get("OPERATIONS_WORKER_ENABLED", "").lower() != "true":
        logger.info("operations_worker: OPERATIONS_WORKER_ENABLED != true — desabilitado")
        return
    with _lock:
        if _started:
            logger.info("operations_worker: já iniciado — ignorando")
            return
        _started = True

    def _loop() -> None:
        # imports tardios: evita custo/erro no import da app quando desabilitado
        from app.domain.services.operations import canonical  # noqa: F401 (registra tipos)
        from app.domain.services.operations.engine import OperationsEngine
        from app.infrastructure.database.connection import DatabasePool
        from app.infrastructure.database.repositories.operation_repository import (
            OperationRepository,
        )

        repo = OperationRepository(DatabasePool.get_instance())
        publisher = _make_publisher(redis_url)
        engine = OperationsEngine(repo, publish=publisher, now=time.monotonic)

        backoff = 2
        while True:
            pubsub = None
            try:
                pubsub = _make_pubsub(redis_url)
                _safe_load(engine)
                last_reload = time.monotonic()
                logger.info(
                    "operations_worker: assinado det:* + operations:reload:* (%s)",
                    engine.stats(),
                )
                backoff = 2
                while True:
                    msg = pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1.0
                    )
                    now = time.monotonic()
                    if now - last_reload >= _RELOAD_INTERVAL_S:
                        _safe_load(engine)
                        last_reload = now
                    if msg is None or msg.get("type") != "pmessage":
                        continue
                    _handle(engine, msg)
            except Exception as exc:
                logger.error(
                    "operations_worker_failed: %s — reconecta em %ds", exc, backoff
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
            finally:
                if pubsub is not None:
                    try:
                        pubsub.close()
                    except Exception:
                        pass

    t = threading.Thread(target=_loop, daemon=True, name="operations-worker")
    t.start()
    logger.info("operations_worker: thread iniciada")


def _safe_load(engine) -> None:  # type: ignore[no-untyped-def]
    try:
        engine.load_all()
    except Exception as exc:
        logger.error("operations_worker_load_failed: %s", exc)


def _handle(engine, msg: dict) -> None:  # type: ignore[no-untyped-def]
    channel = msg["channel"]
    if isinstance(channel, bytes):
        channel = channel.decode()
    try:
        if channel.startswith("det:"):
            cam_id = channel.split(":", 1)[1]
            data = json.loads(msg["data"])
            if not isinstance(data, dict):
                return
            detections, frame_meta = _extract_frame(cam_id, data)
            engine.process_frame(cam_id, detections, frame_meta)
        elif channel.startswith("operations:reload:"):
            op_id = channel.rsplit(":", 1)[1]
            if op_id.isdigit():
                engine.reload_operation(int(op_id))
    except Exception as exc:
        logger.warning("operations_worker_message_error: channel=%s err=%s", channel, exc)
