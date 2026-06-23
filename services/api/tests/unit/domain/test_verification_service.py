"""
Tests: VerificationService — submit_for_verification, get_human_queue,
human_review, get_queue_count.

All DB calls go through a mocked DatabasePool; verify_alert task is stubbed
via patch.dict(sys.modules) to avoid needing celery installed.
"""
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from app.domain.services.verification_service import VerificationService

_POOL_PATH = "app.domain.services.verification_service.DatabasePool"
_VERIFICATION_MODULE = "app.infrastructure.queue.tasks.verification"


def _make_service() -> VerificationService:
    return VerificationService()


def _pool_with_cursor(mock_cursor):
    """Build a pool mock whose get_connection() yields a conn with mock_cursor."""
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


# ---------------------------------------------------------------------------
# submit_for_verification
# ---------------------------------------------------------------------------

class TestSubmitForVerification:

    def _call(self, mock_task, **kwargs):
        mock_mod = MagicMock()
        mock_mod.verify_alert = mock_task
        with patch.dict(sys.modules, {_VERIFICATION_MODULE: mock_mod}):
            _make_service().submit_for_verification(
                alert_id=kwargs.get("alert_id", "alert-1"),
                camera_id=kwargs.get("camera_id", "cam-1"),
                class_name=kwargs.get("class_name", "no_helmet"),
                confidence=kwargs.get("confidence", 0.7),
                module_code=kwargs.get("module_code", "epi"),
            )
        return mock_task

    def test_calls_verify_alert_delay(self):
        mock_task = MagicMock()
        self._call(mock_task)
        mock_task.delay.assert_called_once()

    def test_passes_correct_kwargs(self):
        mock_task = MagicMock()
        self._call(mock_task, alert_id="a-1", camera_id="c-1",
                   class_name="no_vest", confidence=0.65, module_code="epi")
        kw = mock_task.delay.call_args[1]
        assert kw["alert_id"] == "a-1"
        assert kw["camera_id"] == "c-1"
        assert kw["class_name"] == "no_vest"
        assert kw["confidence"] == 0.65
        assert kw["module_code"] == "epi"

    def test_exception_in_delay_is_swallowed(self):
        mock_task = MagicMock()
        mock_task.delay.side_effect = Exception("broker unreachable")
        # Should not raise — fire-and-forget with error logging
        self._call(mock_task)

    def test_default_module_code_is_epi(self):
        mock_task = MagicMock()
        mock_mod = MagicMock()
        mock_mod.verify_alert = mock_task
        with patch.dict(sys.modules, {_VERIFICATION_MODULE: mock_mod}):
            _make_service().submit_for_verification(
                alert_id="a", camera_id="c", class_name="no_helmet", confidence=0.5
            )
        kw = mock_task.delay.call_args[1]
        assert kw["module_code"] == "epi"


# ---------------------------------------------------------------------------
# get_human_queue
# ---------------------------------------------------------------------------

class TestGetHumanQueue:

    def test_pool_none_returns_empty(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            result = _make_service().get_human_queue()
        assert result == []

    def test_returns_list_of_dicts(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": "a1", "camera_name": "Cam A", "verification_status": "needs_human"},
        ]
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().get_human_queue()
        assert len(result) == 1
        assert result[0]["id"] == "a1"

    def test_empty_fetchall_returns_empty_list(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().get_human_queue()
        assert result == []

    def test_camera_id_filter_adds_param(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().get_human_queue(camera_id="cam-42")
        call_args = mock_cursor.execute.call_args
        query, params = call_args[0]
        assert "camera_id" in query
        assert "cam-42" in params

    def test_db_exception_returns_empty(self):
        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = Exception("DB down")
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            result = _make_service().get_human_queue()
        assert result == []

    def test_limit_passed_as_last_param(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().get_human_queue(limit=10)
        _, params = mock_cursor.execute.call_args[0]
        assert 10 in params


# ---------------------------------------------------------------------------
# human_review
# ---------------------------------------------------------------------------

class TestHumanReview:

    def test_invalid_verdict_raises_value_error(self):
        with pytest.raises(ValueError, match="verdict"):
            _make_service().human_review("alert-1", "maybe", "user-1")

    def test_pool_none_raises_runtime_error(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            with pytest.raises(RuntimeError, match="Database"):
                _make_service().human_review("a-1", "approve", "u-1")

    def test_approve_sets_human_approved_status(self):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().human_review("a-1", "approve", "u-1")
        assert result is True
        params = mock_cursor.execute.call_args[0][1]
        assert "human_approved" in params

    def test_reject_sets_human_rejected_status(self):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().human_review("a-1", "reject", "u-1")
        assert result is True
        params = mock_cursor.execute.call_args[0][1]
        assert "human_rejected" in params

    def test_no_rows_affected_returns_false(self):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            result = _make_service().human_review("a-1", "approve", "u-1")
        assert result is False

    def test_user_id_included_in_query_params(self):
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            _make_service().human_review("alert-xyz", "approve", "user-99")
        params = mock_cursor.execute.call_args[0][1]
        assert any("user-99" in str(p) for p in params)


# ---------------------------------------------------------------------------
# get_queue_count
# ---------------------------------------------------------------------------

class TestGetQueueCount:

    def test_pool_none_returns_zero(self):
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = None
            assert _make_service().get_queue_count() == 0

    def test_returns_count_from_db(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (7,)
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            assert _make_service().get_queue_count() == 7

    def test_fetchone_none_returns_zero(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = _pool_with_cursor(mock_cursor)
            assert _make_service().get_queue_count() == 0

    def test_db_exception_returns_zero(self):
        mock_pool = MagicMock()
        mock_pool.get_connection.side_effect = Exception("DB crash")
        with patch(_POOL_PATH) as pool_cls:
            pool_cls.get_instance.return_value = mock_pool
            assert _make_service().get_queue_count() == 0
