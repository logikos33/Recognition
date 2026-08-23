"""
Recognition — WebSocket Bridge (Redis → SocketIO → Browser).

Pattern: Observer via Redis pub/sub.
Worker publica detecções no Redis → Bridge assina e emite via SocketIO.
Uses socket_timeout=None + health_check_interval to survive idle periods.

Canais assinados:
  det:*       → emite "detection" em /monitor namespace
  training:*  → emite "training_progress" em /training namespace
                + registra modelo em trained_models quando status=completed
  quality:*, operations:*, edge_telemetry:* → ver route_message()

Isolamento por tenant (C-01)
----------------------------
Nenhum emit é broadcast: todo evento sai com ``to=tenant:<tenant_schema>`` — a
room em que app/core/socket_auth.py coloca cada conexão autenticada. O tenant
vem do próprio canal (quality:*:{schema}:*, edge_telemetry:{tenant_id}) ou é
resolvido por lookup cacheado (det:{camera_id}, operations:*:{op_id},
training:{job_id}) via TenantRoomResolver. **Não resolveu → descarta e loga**;
nunca cai em broadcast.
"""
import json
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)


def _register_trained_model(job_id: str, data: dict) -> None:
    """Registra modelo treinado no DB quando training-service reporta completed.

    Roda no thread do bridge — usa DatabasePool diretamente (sem Flask context).
    """
    model_key = data.get("model_key", "")
    metrics = data.get("metrics", {})
    if not model_key:
        logger.warning("training_completed_no_model_key: job=%s", job_id)
        return
    try:
        from app.infrastructure.database.connection import DatabasePool
        from app.infrastructure.database.repositories.training_repository import TrainingRepository
        from uuid import UUID

        pool = DatabasePool.get_instance()
        if pool is None:
            logger.warning("training_model_register_skipped: pool not ready")
            return

        repo = TrainingRepository(pool)
        job = repo.get_job_by_id(UUID(job_id))
        if not job:
            logger.warning("training_model_register_skipped: job not found job=%s", job_id)
            return

        # Guarda anti-duplicação (ajuste vinculante #2): trained_models.job_id
        # não tem UNIQUE e o fluxo Celery também registra — primeiro a chegar vence.
        if repo.get_model_by_job_id(UUID(job_id)):
            logger.info("training_model_register_skipped: model exists job=%s", job_id)
            return

        model = repo.create_model({
            "user_id": str(job["user_id"]),
            "job_id": job_id,
            # Herda o tenant do JOB (taggeado com get_tenant_id() na criação),
            # NÃO o tenant de casa do user_id: este callback roda fora do Flask
            # context (sem get_tenant_id()), então a fonte correta do contexto
            # assumido é a linha do job. Sem isto o create_model caía no
            # fallback `(SELECT tenant_id FROM users WHERE id=user_id)` = casa,
            # e o modelo ficava 404 na registry sob contexto assumido (#302/#313).
            "tenant_id": str(job["tenant_id"]) if job.get("tenant_id") else None,
            "name": f"model-{job_id[:8]}",
            "model_path": model_key,
            "map50": metrics.get("mAP50"),
            "precision": metrics.get("precision"),
            "recall": metrics.get("recall"),
            "created_by": str(job["user_id"]),
            "origin": metrics.get("source", "training_service"),
            "framework": data.get("framework"),
            # r2_onnx_key só é setado se o payload do training-service o
            # informar explicitamente — model_key (model_path) não é
            # necessariamente um artefato ONNX (pode ser checkpoint nativo
            # do framework), então não assumimos equivalência aqui.
            "r2_onnx_key": data.get("r2_onnx_key"),
            # r2_weights_key (linhagem, migration 098): mesmo padrão de
            # r2_onnx_key — só setado se o training-service informar
            # explicitamente no payload de conclusão. Antes deste fix o
            # campo era descartado aqui (só o fluxo Celery em tasks/
            # training.py persistia r2_weights_key); TrainingRepository.
            # create_model já sabe gravá-lo (coluna opcional, migration
            # 098) — só faltava este caminho repassar o valor recebido.
            "r2_weights_key": data.get("r2_weights_key"),
            "dataset_version_id": job.get("dataset_version_id"),
            "module_code": data.get("module_code"),
        })
        logger.info("trained_model_registered: job=%s path=%s", job_id, model_key)

        # WS-C1 (best-effort): dispara avaliação campeão×desafiante do
        # modelo recém-criado pelo training-service. Nunca derruba o
        # registro do modelo em si — mesmo padrão do dispatch_training
        # Celery (tasks/training.py).
        try:
            from app.infrastructure.queue.tasks.model_evaluation import (
                evaluate_challenger_model,
            )
            evaluate_challenger_model.delay(str(model["id"]))
        except Exception as eval_exc:
            logger.warning(
                "trained_model_eval_trigger_failed: job=%s err=%s", job_id, eval_exc
            )
    except Exception as exc:
        logger.error("trained_model_register_error: job=%s err=%s", job_id, exc)


# ── Criação de alerta: NÃO acontece aqui (#132) ───────────────────────────────
#
# Este bridge já criou alertas: `_maybe_verify_detections` +
# `_create_alert_and_verify` inseriam em `alerts` por SQL cru, na thread da
# API, para a MESMA detecção que o worker já havia gravado em
# `inference.py::_save_alert`. Dois processos, sem coordenação, duas linhas —
# e o operador via o mesmo evento duas vezes, justamente nos casos de baixa
# confiança, que são os que mais precisam de revisão.
#
# O escritor único agora é `_save_alert`, no worker: é ele que tem o frame de
# evidência, o tenant/módulo resolvidos, a lista inteira de detecções e o hook
# de auto-captura (WS-B3). O disparo de `verify_alert` — a única coisa que só
# este caminho fazia — mudou para lá, ao lado do INSERT.
#
# ⛔ Não reintroduza escrita de alerta neste arquivo. O trabalho do bridge é
# repassar o que chega do Redis para o SocketIO.


class TenantRoomResolver:
    """Resolve identificadores dos canais → ``tenant_schema`` (room), com cache.

    Hits ficam 1h (tenant de câmera/operação/job não muda na prática); misses
    60s (câmera recém-criada aparece sem martelar o banco a 5 msg/s). Qualquer
    erro de infra → None (o bridge descarta a mensagem — C-01).
    """

    HIT_TTL_S = 3600
    MISS_TTL_S = 60

    def __init__(self, repo_factory=None, clock=time.monotonic) -> None:  # type: ignore[no-untyped-def]
        self._repo_factory = repo_factory or self._default_repo
        self._clock = clock
        self._cache: dict[tuple[str, str], tuple[str | None, float]] = {}

    @staticmethod
    def _default_repo():  # type: ignore[no-untyped-def]
        from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
        from app.infrastructure.database.repositories.tenant_schema_lookup_repository import (  # noqa: PLC0415
            TenantSchemaLookupRepository,
        )

        pool = DatabasePool.get_instance()
        return TenantSchemaLookupRepository(pool) if pool is not None else None

    def _lookup(self, kind: str, key: str, fn_name: str, *args) -> str | None:  # type: ignore[no-untyped-def]
        now = self._clock()
        hit = self._cache.get((kind, key))
        if hit and hit[1] > now:
            return hit[0]
        value: str | None = None
        try:
            repo = self._repo_factory()
            if repo is not None:
                value = getattr(repo, fn_name)(*args)
        except Exception as exc:  # noqa: BLE001
            logger.warning("tenant_room_lookup_failed: kind=%s key=%s err=%s", kind, key, exc)
            return None  # erro de infra não entra no cache
        ttl = self.HIT_TTL_S if value else self.MISS_TTL_S
        self._cache[(kind, key)] = (value, now + ttl)
        return value

    def for_camera(self, camera_id: str) -> str | None:
        return self._lookup("camera", camera_id, "schema_for_camera", camera_id)

    def for_operation(self, op_id: str) -> str | None:
        if not op_id.isdigit():
            return None
        return self._lookup("operation", op_id, "schema_for_operation", int(op_id))

    def for_training_job(self, job_id: str) -> str | None:
        return self._lookup("training_job", job_id, "schema_for_training_job", job_id)

    def for_tenant_id(self, tenant_id: str) -> str | None:
        return self._lookup("tenant", tenant_id, "schema_for_tenant", tenant_id)


def _room(schema: str | None) -> str | None:
    from app.core.socket_auth import tenant_room  # noqa: PLC0415

    return tenant_room(schema) if schema else None


def route_message(channel: str, data: dict, resolver: TenantRoomResolver):  # type: ignore[no-untyped-def]
    """Canal Redis + payload → (evento, payload, namespace, room) ou None.

    Função pura (fora do laço) para ser testável sem Redis. ``room=None`` é
    devolvido quando o tenant não pôde ser determinado — o chamador DESCARTA
    (nunca emite sem room). Os shapes dos eventos são os de sempre; aqui só se
    decide destino.
    """
    parts = channel.split(":")
    if channel.startswith("det:"):
        cam_id = parts[1]
        return ("detection", {"camera_id": cam_id, **data}, "/monitor", _room(resolver.for_camera(cam_id)))
    if channel.startswith("training:"):
        job_id = parts[1]
        return ("training_progress", {"job_id": job_id, **data}, "/training", _room(resolver.for_training_job(job_id)))
    if channel.startswith("quality:training_progress:"):
        # quality:training_progress:{schema}:{job_id}; forma antiga (só job_id) → sem room
        schema = parts[2] if len(parts) >= 4 else None
        return ("quality_training", data, "/training", _room(schema))
    quality_schema_events = {
        "quality:inspection:": "quality_inspection",          # :{schema}:{camera_id}
        "quality:cep_alert:": "quality_cep_alert",            # :{schema}:{camera_id}
        "quality:piece_identified:": "quality_piece_identified",
        "quality:inspection_started:": "quality_inspection_started",
        "quality:inspection_result:": "quality_inspection_result",
        "quality:station_state:": "quality_station_state",
    }
    for prefix, event in quality_schema_events.items():
        if channel.startswith(prefix):
            schema = parts[2] if len(parts) >= 3 and parts[2] else None
            return (event, data, "/quality", _room(schema))
    if channel.startswith("quality:andon_live:"):
        cam_id = parts[2] if len(parts) >= 3 else ""
        return ("quality_andon", data, "/quality", _room(resolver.for_camera(cam_id)))
    if channel.startswith("operations:reload:"):
        op_id = parts[-1]
        payload = {"operation_id": int(op_id) if op_id.isdigit() else op_id, **data}
        return ("operation:reloaded", payload, "/monitor", _room(resolver.for_operation(op_id)))
    if channel.startswith("operations:status:"):
        op_id = parts[-1]
        return ("operation:status_changed", data, "/monitor", _room(resolver.for_operation(op_id)))
    if channel.startswith("edge_telemetry:"):
        tenant_id = parts[1]
        return ("edge_telemetry", data, "/monitor", _room(resolver.for_tenant_id(tenant_id)))
    return None


def _make_bridge_pubsub(redis_url: str):
    """Dedicated pubsub connection — no socket_timeout (listen blocks)."""
    import redis

    r = redis.from_url(
        redis_url,
        socket_timeout=None,
        socket_keepalive=True,
        health_check_interval=25,
    )
    ps = r.pubsub()
    # quality:* adicionado para o módulo de Qualidade Industrial
    # edge_telemetry:* alimenta o Dashboard Integrado ao vivo (task-112, ADR-0053)
    ps.psubscribe(
        "det:*", "training:*", "quality:*", "operations:*", "edge_telemetry:*"
    )
    return ps


def start_redis_bridge(socketio) -> None:  # type: ignore[no-untyped-def]
    """Start background thread: Redis pub/sub → SocketIO.

    Channels:
    - det:*       → camera detections → namespace /monitor
    - training:*  → training progress → namespace /training

    Reconnects with exponential backoff on any failure.
    """
    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        logger.info("redis_bridge: REDIS_URL not set, bridge disabled")
        return

    def _bridge_loop() -> None:
        backoff = 2
        resolver = TenantRoomResolver()
        while True:
            pubsub = None
            try:
                pubsub = _make_bridge_pubsub(redis_url)
                logger.info("redis_bridge: subscribed to det:* and training:*")
                backoff = 2

                for message in pubsub.listen():
                    if message["type"] != "pmessage":
                        continue
                    try:
                        channel = message["channel"]
                        if isinstance(channel, bytes):
                            channel = channel.decode()
                        data = json.loads(message["data"])

                        # Efeito colateral independente da entrega WS (mantido
                        # como antes, ANTES do gate de room): registra o modelo
                        # quando o training-service reporta conclusão.
                        if channel.startswith("training:") and data.get("status") == "completed":
                            job_id = channel.split(":")[1]
                            threading.Thread(
                                target=_register_trained_model,
                                args=(job_id, data),
                                daemon=True,
                                name=f"register-model-{job_id[:8]}",
                            ).start()

                        routed = route_message(channel, data, resolver)
                        if routed is None:
                            continue
                        event, payload, namespace, room = routed
                        if room is None:
                            # C-01: sem tenant resolvido NÃO há broadcast.
                            logger.warning(
                                "redis_bridge_dropped_no_tenant: channel=%s event=%s", channel, event
                            )
                            continue
                        socketio.emit(event, payload, namespace=namespace, to=room)
                    except Exception as exc:
                        logger.warning("redis_bridge_message_error: %s", exc)

            except Exception as exc:
                logger.error("redis_bridge_failed: %s -- reconnecting in %ds", exc, backoff)
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
            finally:
                if pubsub is not None:
                    try:
                        pubsub.close()
                    except Exception:
                        pass

    thread = threading.Thread(target=_bridge_loop, daemon=True, name="redis-bridge")
    thread.start()
    logger.info("redis_bridge: thread started")
