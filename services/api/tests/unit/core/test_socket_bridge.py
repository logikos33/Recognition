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
