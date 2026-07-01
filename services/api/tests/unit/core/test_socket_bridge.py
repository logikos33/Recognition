"""
Tests: socket_bridge.py — _register_trained_model, _maybe_verify_detections,
_create_alert_and_verify, start_redis_bridge (item-24).

All lazy imports are patched at source; no Redis or celery required.
"""
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4


# Stub verification module so lazy import in _create_alert_and_verify doesn't
# require celery to be installed
_mock_verify_task = MagicMock()
_mock_verification_mod = MagicMock()
_mock_verification_mod.verify_alert = _mock_verify_task
# Force-set (not setdefault) so our stub wins regardless of import order in the
# full test suite. The real module would pull in celery which is not installed.
sys.modules["app.infrastructure.queue.tasks.verification"] = _mock_verification_mod

from app.core.socket_bridge import (  # noqa: E402
    _create_alert_and_verify,
    _maybe_verify_detections,
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
# _maybe_verify_detections
# ---------------------------------------------------------------------------

class TestMaybeVerifyDetections:

    def test_no_detections_no_thread(self):
        with patch("threading.Thread") as mock_thread:
            _maybe_verify_detections("cam-1", {"detections": []})
        mock_thread.assert_not_called()

    def test_positive_detection_only_no_thread(self):
        data = {"detections": [{"class": "helmet", "confidence": 0.5}]}
        with patch("threading.Thread") as mock_thread:
            _maybe_verify_detections("cam-1", data)
        mock_thread.assert_not_called()

    def test_violation_above_threshold_no_thread(self):
        data = {"detections": [{"class": "no_helmet", "confidence": 0.95}]}
        with patch.dict("os.environ", {"VERIFICATION_THRESHOLD": "0.90"}), \
             patch("threading.Thread") as mock_thread:
            _maybe_verify_detections("cam-1", data)
        mock_thread.assert_not_called()

    def test_violation_below_threshold_spawns_thread(self):
        data = {"detections": [{"class": "no_vest", "confidence": 0.70}]}
        mock_thread_instance = MagicMock()
        with patch.dict("os.environ", {"VERIFICATION_THRESHOLD": "0.85"}), \
             patch("threading.Thread", return_value=mock_thread_instance) as mock_thread_cls:
            _maybe_verify_detections("cam-1", data)
        mock_thread_cls.assert_called_once()
        mock_thread_instance.start.assert_called_once()

    def test_picks_max_confidence_violation(self):
        data = {
            "detections": [
                {"class": "no_helmet", "confidence": 0.5},
                {"class": "no_vest", "confidence": 0.75},  # higher — should be picked
            ]
        }
        captured_args = {}
        def _capture_thread(**kwargs):
            captured_args.update(kwargs)
            t = MagicMock()
            return t

        with patch.dict("os.environ", {"VERIFICATION_THRESHOLD": "0.85"}), \
             patch("threading.Thread", side_effect=_capture_thread):
            _maybe_verify_detections("cam-1", data)

        # args[1] is the args tuple passed to thread (camera_id, detection)
        _, detection_arg = captured_args["args"]
        assert detection_arg["confidence"] == 0.75


# ---------------------------------------------------------------------------
# _create_alert_and_verify
# ---------------------------------------------------------------------------

class TestCreateAlertAndVerify:

    def _build_pool(self, alert_id=None):
        mock_cursor = MagicMock()
        mock_row = {"id": alert_id or uuid4()}
        mock_cursor.fetchone.return_value = mock_row
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=mock_conn)
        cm.__exit__ = MagicMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.get_connection.return_value = cm
        return mock_pool, mock_cursor

    def test_pool_none_returns_early(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            _create_alert_and_verify("cam-1", {"class": "no_helmet", "confidence": 0.7})
        _mock_verify_task.delay.assert_not_called()

    def test_creates_alert_and_queues_verification(self):
        _mock_verify_task.reset_mock()
        alert_id = uuid4()
        mock_pool, _ = self._build_pool(alert_id=alert_id)

        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            _create_alert_and_verify("cam-abc", {"class": "no_gloves", "confidence": 0.65})

        _mock_verify_task.delay.assert_called_once()
        kwargs = _mock_verify_task.delay.call_args[1]
        assert kwargs["camera_id"] == "cam-abc"
        assert kwargs["class_name"] == "no_gloves"

    def test_fetchone_none_skips_verify(self):
        _mock_verify_task.reset_mock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=mock_conn)
        cm.__exit__ = MagicMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.get_connection.return_value = cm

        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            _create_alert_and_verify("cam-1", {"class": "no_helmet", "confidence": 0.7})

        _mock_verify_task.delay.assert_not_called()

    def test_exception_logged_not_raised(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.side_effect = Exception("DB crashed")
            _create_alert_and_verify("cam-1", {"class": "no_helmet", "confidence": 0.7})


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

    def test_det_channel_with_violation_calls_maybe_verify(self):
        mock_io = MagicMock()
        msgs = [_msg("det:cam-5", {"detections": [{"class": "no_helmet", "confidence": 0.6}], "has_violation": True})]
        with patch("app.core.socket_bridge._maybe_verify_detections") as mock_verify:
            _run_bridge_with_messages(msgs, mock_io)
        mock_verify.assert_called_once()

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
