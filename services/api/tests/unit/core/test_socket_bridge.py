"""
Tests: socket_bridge.py — _register_trained_model, start_redis_bridge (item-24).

⚠️ `_maybe_verify_detections` e `_create_alert_and_verify` NÃO existem mais: eram
o segundo caminho de criação de alerta (#132), removido em favor do escritor
único no worker (`inference.py::_save_alert`). A guarda de regressão está em
TestBridgeLoopDetChannel::test_det_channel_com_violacao_NAO_grava_alerta.

All lazy imports are patched at source; no Redis or celery required.
"""
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4


# Stub verification module: outros caminhos ainda fazem lazy import dele e
# celery não está instalado no ambiente de teste unitário.
_mock_verify_task = MagicMock()
_mock_verification_mod = MagicMock()
_mock_verification_mod.verify_alert = _mock_verify_task
# Force-set (not setdefault) so our stub wins regardless of import order in the
# full test suite. The real module would pull in celery which is not installed.
sys.modules["app.infrastructure.queue.tasks.verification"] = _mock_verification_mod

from app.core.socket_bridge import (  # noqa: E402
    _register_trained_model,
    start_redis_bridge,
)

_POOL_PATH = "app.infrastructure.database.connection.DatabasePool"


# ---------------------------------------------------------------------------
# _register_trained_model
# ---------------------------------------------------------------------------

class TestRegisterTrainedModel:

    def test_no_model_key_returns_early(self):
        _register_trained_model("job-1", {})  # data has no model_key

    def test_empty_model_key_returns_early(self):
        _register_trained_model("job-1", {"model_key": ""})

    def test_pool_none_returns_early(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            _register_trained_model("job-1", {"model_key": "models/v1.pt"})

    def test_job_not_found_returns_early(self):
        mock_repo = MagicMock()
        mock_repo.get_job_by_id.return_value = None
        mock_pool = MagicMock()

        with patch(_POOL_PATH) as pool_cls, \
             patch("app.infrastructure.database.repositories.training_repository.TrainingRepository",
                   return_value=mock_repo):
            pool_cls.get_instance.return_value = mock_pool
            _register_trained_model(str(uuid4()), {"model_key": "models/v1.pt"})

        mock_repo.create_model.assert_not_called()

    def test_job_found_creates_model(self):
        job_id = str(uuid4())
        user_id = str(uuid4())
        mock_job = {"user_id": user_id, "id": job_id}
        mock_repo = MagicMock()
        mock_repo.get_job_by_id.return_value = mock_job
        mock_repo.get_model_by_job_id.return_value = None
        mock_pool = MagicMock()

        with patch(_POOL_PATH) as pool_cls, \
             patch("app.infrastructure.database.repositories.training_repository.TrainingRepository",
                   return_value=mock_repo):
            pool_cls.get_instance.return_value = mock_pool
            _register_trained_model(job_id, {
                "model_key": "models/v1.pt",
                "metrics": {"mAP50": 0.9, "precision": 0.88, "recall": 0.85},
            })

        mock_repo.create_model.assert_called_once()
        call_data = mock_repo.create_model.call_args[0][0]
        assert call_data["model_path"] == "models/v1.pt"
        assert call_data["user_id"] == user_id

    def test_r2_weights_key_forwarded_to_create_model(self):
        """Linhagem completa (mesmo padrão de r2_onnx_key): quando o
        training-service reporta r2_weights_key no payload de conclusão, o
        bridge precisa repassar pro create_model. Falha-antes/passa-depois:
        antes deste fix o campo era descartado — trained_models.
        r2_weights_key nunca era persistido por este caminho (só pelo fluxo
        Celery em tasks/training.py)."""
        job_id = str(uuid4())
        user_id = str(uuid4())
        mock_repo = MagicMock()
        mock_repo.get_job_by_id.return_value = {"user_id": user_id, "id": job_id}
        mock_repo.get_model_by_job_id.return_value = None
        mock_pool = MagicMock()

        with patch(_POOL_PATH) as pool_cls, \
             patch("app.infrastructure.database.repositories.training_repository.TrainingRepository",
                   return_value=mock_repo):
            pool_cls.get_instance.return_value = mock_pool
            _register_trained_model(job_id, {
                "model_key": "models/v1.onnx",
                "r2_weights_key": "models/tenant/v1/weights.pth",
                "metrics": {},
            })

        call_data = mock_repo.create_model.call_args[0][0]
        assert call_data["r2_weights_key"] == "models/tenant/v1/weights.pth"

    def test_r2_weights_key_absent_is_none(self):
        """Sem r2_weights_key no payload (training-service legado/checkpoint
        nativo) — repassa None, não quebra nem inventa valor."""
        job_id = str(uuid4())
        user_id = str(uuid4())
        mock_repo = MagicMock()
        mock_repo.get_job_by_id.return_value = {"user_id": user_id, "id": job_id}
        mock_repo.get_model_by_job_id.return_value = None
        mock_pool = MagicMock()

        with patch(_POOL_PATH) as pool_cls, \
             patch("app.infrastructure.database.repositories.training_repository.TrainingRepository",
                   return_value=mock_repo):
            pool_cls.get_instance.return_value = mock_pool
            _register_trained_model(job_id, {"model_key": "models/v1.pt"})

        call_data = mock_repo.create_model.call_args[0][0]
        assert call_data["r2_weights_key"] is None

    def test_model_inherits_job_tenant_not_home_tenant(self):
        """Contexto assumido: create_model herda o tenant do JOB (taggeado com
        get_tenant_id() na criação), NÃO o tenant de casa do user_id.

        Este callback roda fora do Flask context (sem get_tenant_id()), então a
        fonte correta do contexto assumido é a linha do job.

        Falha-antes/passa-depois: antes do fix o dict de create_model não levava
        tenant_id → o repository caía no fallback casa
        `(SELECT tenant_id FROM users WHERE id=user_id)`. Um modelo treinado sob
        contexto assumido (job.tenant_id = B) ficava taggeado com o tenant de
        casa A e 404 na registry sob contexto B (get_for_tenant escopa por
        get_tenant_id()=B). Ver #302/#313.
        """
        job_id = str(uuid4())
        assumed_tenant = str(uuid4())  # tenant B do job (contexto assumido)
        mock_repo = MagicMock()
        mock_repo.get_job_by_id.return_value = {
            "user_id": str(uuid4()),  # dono/superadmin (tenant de casa A)
            "id": job_id,
            "tenant_id": assumed_tenant,
            "dataset_version_id": None,
        }
        mock_repo.get_model_by_job_id.return_value = None
        mock_repo.create_model.return_value = {"id": str(uuid4())}

        with patch(_POOL_PATH) as pool_cls, \
             patch("app.infrastructure.database.repositories.training_repository.TrainingRepository",
                   return_value=mock_repo):
            pool_cls.get_instance.return_value = MagicMock()
            _register_trained_model(job_id, {"model_key": "models/v1.onnx", "metrics": {}})

        payload = mock_repo.create_model.call_args[0][0]
        assert payload["tenant_id"] == assumed_tenant

    def test_existing_model_for_job_skips_create(self):
        """Guarda anti-duplicação (ajuste #2): fluxo Celery pode ter registrado antes."""
        job_id = str(uuid4())
        mock_repo = MagicMock()
        mock_repo.get_job_by_id.return_value = {"user_id": str(uuid4()), "id": job_id}
        mock_repo.get_model_by_job_id.return_value = {"id": "ja-registrado"}
        mock_pool = MagicMock()

        with patch(_POOL_PATH) as pool_cls, \
             patch("app.infrastructure.database.repositories.training_repository.TrainingRepository",
                   return_value=mock_repo):
            pool_cls.get_instance.return_value = mock_pool
            _register_trained_model(job_id, {"model_key": "models/v1.pt"})

        mock_repo.create_model.assert_not_called()

    def test_exception_during_create_logged_not_raised(self):
        job_id = str(uuid4())
        mock_repo = MagicMock()
        mock_repo.get_job_by_id.return_value = {"user_id": str(uuid4()), "id": job_id}
        mock_repo.create_model.side_effect = Exception("DB error")
        mock_pool = MagicMock()

        with patch(_POOL_PATH) as pool_cls, \
             patch("app.infrastructure.database.repositories.training_repository.TrainingRepository",
                   return_value=mock_repo):
            pool_cls.get_instance.return_value = mock_pool
            _register_trained_model(job_id, {"model_key": "models/v1.pt"})  # should not raise


# ---------------------------------------------------------------------------
# start_redis_bridge
# ---------------------------------------------------------------------------

class TestStartRedisBridge:

    def test_no_redis_url_returns_without_thread(self):
        mock_socketio = MagicMock()
        with patch.dict("os.environ", {"REDIS_URL": ""}), \
             patch("threading.Thread") as mock_thread:
            start_redis_bridge(mock_socketio)
        mock_thread.assert_not_called()

    def test_with_redis_url_starts_daemon_thread(self):
        mock_socketio = MagicMock()
        mock_thread_instance = MagicMock()
        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379"}), \
             patch("threading.Thread", return_value=mock_thread_instance) as mock_thread_cls:
            start_redis_bridge(mock_socketio)
        mock_thread_cls.assert_called_once()
        call_kwargs = mock_thread_cls.call_args[1]
        assert call_kwargs.get("daemon") is True
        mock_thread_instance.start.assert_called_once()


# ---------------------------------------------------------------------------
# _make_bridge_pubsub (lines 125-136)
# ---------------------------------------------------------------------------

class TestMakeBridgePubsub:

    def test_creates_redis_connection_and_subscribes(self):
        from app.core.socket_bridge import _make_bridge_pubsub

        mock_redis = MagicMock()
        mock_pubsub = MagicMock()
        mock_redis.pubsub.return_value = mock_pubsub

        with patch("redis.from_url", return_value=mock_redis) as mock_from_url:
            result = _make_bridge_pubsub("redis://localhost:6379/0")

        mock_from_url.assert_called_once_with(
            "redis://localhost:6379/0",
            socket_timeout=None,
            socket_keepalive=True,
            health_check_interval=25,
        )
        mock_pubsub.psubscribe.assert_called_once()
        subscribed = mock_pubsub.psubscribe.call_args[0]
        assert "det:*" in subscribed
        assert "training:*" in subscribed
        assert "quality:*" in subscribed
        assert "operations:*" in subscribed
        assert result is mock_pubsub


# ---------------------------------------------------------------------------
# Bridge loop message routing (lines 154-241)
#
# Pattern: capture _bridge_loop from threading.Thread, run synchronously.
# First _make_bridge_pubsub call yields finite messages; second raises
# SystemExit (not caught by `except Exception`) to stop the while-True loop.
# ---------------------------------------------------------------------------

def _run_bridge_with_messages(messages, mock_socketio):
    """Capture _bridge_loop, feed it controlled messages, exit cleanly."""
    call_count = [0]

    def _fake_pubsub(url):
        call_count[0] += 1
        if call_count[0] == 1:
            ps = MagicMock()
            ps.listen.return_value = iter(messages)
            return ps
        raise SystemExit(0)

    captured = [None]

    class _CapThread:
        def __init__(self, target, **kwargs):
            captured[0] = target
        def start(self):
            pass

    with patch("app.core.socket_bridge._make_bridge_pubsub", side_effect=_fake_pubsub), \
         patch("app.core.socket_bridge.time.sleep"), \
         patch("threading.Thread", side_effect=_CapThread), \
         patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}):
        start_redis_bridge(mock_socketio)
        try:
            captured[0]()
        except SystemExit:
            pass


def _msg(channel, data):
    return {"type": "pmessage", "channel": channel, "data": __import__("json").dumps(data)}


class TestBridgeLoopNonPmessageSkipped:

    def test_subscribe_type_messages_ignored(self):
        mock_io = MagicMock()
        msgs = [{"type": "subscribe", "channel": "det:*", "data": 1}]
        _run_bridge_with_messages(msgs, mock_io)
        mock_io.emit.assert_not_called()


class TestBridgeLoopDetChannel:

    def test_det_channel_emits_detection(self):
        mock_io = MagicMock()
        msgs = [_msg("det:cam-42", {"detections": [], "has_violation": False})]
        _run_bridge_with_messages(msgs, mock_io)
        mock_io.emit.assert_any_call(
            "detection",
            {"camera_id": "cam-42", "detections": [], "has_violation": False},
            namespace="/monitor",
        )

    def test_det_channel_com_violacao_NAO_grava_alerta(self):
        """Guarda de regressão do #132.

        Este bridge já inseria em `alerts` por SQL cru para a MESMA detecção
        que o worker gravava em `_save_alert` — duas linhas por evento, sempre
        que a confiança ficava abaixo do limiar de verificação. O escritor
        único agora é o worker; aqui só pode sair emit.

        O teste falha se alguém reintroduzir escrita: qualquer uso do pool
        derruba a asserção, e não só o nome de função que existia antes.
        """
        mock_io = MagicMock()
        mock_pool = MagicMock()
        msgs = [_msg(
            "det:cam-5",
            {"detections": [{"class": "no_helmet", "confidence": 0.6}], "has_violation": True},
        )]

        with patch(f"{_POOL_PATH}.get_instance", return_value=mock_pool):
            _run_bridge_with_messages(msgs, mock_io)

        mock_pool.get_connection.assert_not_called()
        _mock_verify_task.delay.assert_not_called()
        mock_io.emit.assert_any_call(
            "detection",
            {
                "camera_id": "cam-5",
                "detections": [{"class": "no_helmet", "confidence": 0.6}],
                "has_violation": True,
            },
            namespace="/monitor",
        )

    def test_det_channel_bytes_decoded(self):
        import json
        mock_io = MagicMock()
        msgs = [{"type": "pmessage", "channel": b"det:cam-99", "data": json.dumps({"detections": []})}]
        _run_bridge_with_messages(msgs, mock_io)
        mock_io.emit.assert_any_call(
            "detection", {"camera_id": "cam-99", "detections": []}, namespace="/monitor"
        )


class TestBridgeLoopTrainingChannel:

    def test_training_progress_emitted(self):
        mock_io = MagicMock()
        msgs = [_msg("training:job-7", {"status": "running", "progress": 0.5})]
        _run_bridge_with_messages(msgs, mock_io)
        mock_io.emit.assert_any_call(
            "training_progress",
            {"job_id": "job-7", "status": "running", "progress": 0.5},
            namespace="/training",
        )

    def test_training_completed_spawns_register_thread(self):
        mock_io = MagicMock()
        msgs = [_msg("training:job-9", {"status": "completed", "model_key": "k.pt", "metrics": {}})]
        spawned_targets = []

        call_count = [0]

        def _fake_pubsub(url):
            call_count[0] += 1
            if call_count[0] == 1:
                ps = MagicMock()
                ps.listen.return_value = iter(msgs)
                return ps
            raise SystemExit(0)

        captured_bridge = [None]

        def _thread_factory(target=None, daemon=False, name="", **kwargs):
            t = MagicMock()
            if name == "redis-bridge":
                captured_bridge[0] = target
            else:
                spawned_targets.append(target)
            return t

        with patch("app.core.socket_bridge._make_bridge_pubsub", side_effect=_fake_pubsub), \
             patch("app.core.socket_bridge.time.sleep"), \
             patch("threading.Thread", side_effect=_thread_factory), \
             patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}):
            start_redis_bridge(mock_io)
            try:
                captured_bridge[0]()
            except SystemExit:
                pass

        assert len(spawned_targets) >= 1


class TestBridgeLoopQualityChannels:

    def test_quality_inspection(self):
        mock_io = MagicMock()
        msgs = [_msg("quality:inspection:st-1", {"result": "OK"})]
        _run_bridge_with_messages(msgs, mock_io)
        mock_io.emit.assert_any_call("quality_inspection", {"result": "OK"}, namespace="/quality")

    def test_quality_training_progress(self):
        mock_io = MagicMock()
        msgs = [_msg("quality:training_progress:job-1", {"pct": 40})]
        _run_bridge_with_messages(msgs, mock_io)
        mock_io.emit.assert_any_call("quality_training", {"pct": 40}, namespace="/training")

    def test_quality_cep_alert(self):
        mock_io = MagicMock()
        msgs = [_msg("quality:cep_alert:st-1", {"metric": "diameter"})]
        _run_bridge_with_messages(msgs, mock_io)
        mock_io.emit.assert_any_call("quality_cep_alert", {"metric": "diameter"}, namespace="/quality")

    def test_quality_andon_live(self):
        mock_io = MagicMock()
        msgs = [_msg("quality:andon_live:st-1", {"value": 12})]
        _run_bridge_with_messages(msgs, mock_io)
        mock_io.emit.assert_any_call("quality_andon", {"value": 12}, namespace="/quality")

    def test_quality_piece_identified(self):
        mock_io = MagicMock()
        msgs = [_msg("quality:piece_identified:st-1", {"piece_id": "P001"})]
        _run_bridge_with_messages(msgs, mock_io)
        mock_io.emit.assert_any_call("quality_piece_identified", {"piece_id": "P001"}, namespace="/quality")

    def test_quality_inspection_started(self):
        mock_io = MagicMock()
        msgs = [_msg("quality:inspection_started:st-1", {"batch": "B01"})]
        _run_bridge_with_messages(msgs, mock_io)
        mock_io.emit.assert_any_call("quality_inspection_started", {"batch": "B01"}, namespace="/quality")

    def test_quality_inspection_result(self):
        mock_io = MagicMock()
        msgs = [_msg("quality:inspection_result:st-1", {"status": "NOK"})]
        _run_bridge_with_messages(msgs, mock_io)
        mock_io.emit.assert_any_call("quality_inspection_result", {"status": "NOK"}, namespace="/quality")

    def test_quality_station_state(self):
        mock_io = MagicMock()
        msgs = [_msg("quality:station_state:st-1", {"state": "idle"})]
        _run_bridge_with_messages(msgs, mock_io)
        mock_io.emit.assert_any_call("quality_station_state", {"state": "idle"}, namespace="/quality")


class TestBridgeLoopOperationsChannels:

    def test_operations_reload_numeric_id(self):
        mock_io = MagicMock()
        msgs = [_msg("operations:reload:42", {"config": {}})]
        _run_bridge_with_messages(msgs, mock_io)
        mock_io.emit.assert_any_call(
            "operation:reloaded",
            {"operation_id": 42, "config": {}},
            namespace="/monitor",
        )

    def test_operations_reload_non_numeric_id(self):
        mock_io = MagicMock()
        msgs = [_msg("operations:reload:my-op", {"config": {}})]
        _run_bridge_with_messages(msgs, mock_io)
        mock_io.emit.assert_any_call(
            "operation:reloaded",
            {"operation_id": "my-op", "config": {}},
            namespace="/monitor",
        )

    def test_operations_status_changed(self):
        mock_io = MagicMock()
        msgs = [_msg("operations:status:cam-1", {"status": "running"})]
        _run_bridge_with_messages(msgs, mock_io)
        mock_io.emit.assert_any_call(
            "operation:status_changed", {"status": "running"}, namespace="/monitor"
        )


class TestBridgeLoopErrorHandling:

    def test_malformed_json_does_not_crash_loop(self):
        mock_io = MagicMock()
        msgs = [{"type": "pmessage", "channel": "det:cam-1", "data": "NOT_JSON"}]
        # Should process without raising — per-message exception is caught
        _run_bridge_with_messages(msgs, mock_io)

    def test_pubsub_closed_in_finally_on_reconnect(self):
        """pubsub.close() is called in the finally block after a failure."""
        mock_io = MagicMock()
        call_count = [0]
        closed = []

        def _fake_pubsub(url):
            call_count[0] += 1
            if call_count[0] == 1:
                ps = MagicMock()
                ps.listen.side_effect = RuntimeError("connection lost")
                ps.close.side_effect = lambda: closed.append(True)
                return ps
            raise SystemExit(0)

        captured = [None]

        class _CapThread:
            def __init__(self, target, **kwargs):
                captured[0] = target
            def start(self): pass

        with patch("app.core.socket_bridge._make_bridge_pubsub", side_effect=_fake_pubsub), \
             patch("app.core.socket_bridge.time.sleep"), \
             patch("threading.Thread", side_effect=_CapThread), \
             patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}):
            start_redis_bridge(mock_io)
            try:
                captured[0]()
            except SystemExit:
                pass

        assert closed  # pubsub.close() was called
