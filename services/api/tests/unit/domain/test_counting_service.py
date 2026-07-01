"""
Tests: CountingService — start/stop/record/stats (item-24).
"""
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.services.counting_service import CountingService


class TestCountingService:

    def setup_method(self):
        self.repo = MagicMock()
        self.service = CountingService(self.repo)

    # ------------------------------------------------------------------
    # start_session
    # ------------------------------------------------------------------

    def test_start_session_success(self):
        tenant_id = uuid4()
        camera_id = uuid4()
        self.repo.create_session.return_value = {
            "id": uuid4(), "status": "active",
            "camera_id": camera_id, "module_code": "epi",
        }
        result = self.service.start_session(tenant_id, camera_id, "epi")
        assert result["status"] == "active"
        self.repo.create_session.assert_called_once()
        assert self.repo.create_session.call_args.args == (tenant_id, camera_id, "epi")

    def test_start_session_empty_module_raises(self):
        with pytest.raises(ValidationError, match="obrigatório"):
            self.service.start_session(uuid4(), uuid4(), "")

    def test_start_session_none_module_raises(self):
        with pytest.raises(ValidationError):
            self.service.start_session(uuid4(), uuid4(), None)

    # ------------------------------------------------------------------
    # stop_session
    # ------------------------------------------------------------------

    def test_stop_session_success(self):
        session_id = uuid4()
        tenant_id = uuid4()
        self.repo.get_session.return_value = {"id": session_id, "status": "active"}
        self.repo.get_session_counts.return_value = [
            {"class_name": "helmet", "count": 5},
            {"class_name": "vest", "count": 3},
        ]
        self.repo.stop_session.return_value = {"id": session_id, "status": "stopped"}

        result = self.service.stop_session(session_id, tenant_id)
        assert result["status"] == "stopped"

        call_kwargs = self.repo.stop_session.call_args
        counts_arg = call_kwargs[0][2]
        assert counts_arg == {"helmet": 5, "vest": 3}

    def test_stop_session_not_found_raises(self):
        self.repo.get_session.return_value = None
        with pytest.raises(NotFoundError):
            self.service.stop_session(uuid4(), uuid4())

    def test_stop_session_no_updated_returns_original_session(self):
        session_id = uuid4()
        original = {"id": session_id, "status": "active"}
        self.repo.get_session.return_value = original
        self.repo.get_session_counts.return_value = []
        self.repo.stop_session.return_value = None  # DB returned nothing

        result = self.service.stop_session(session_id, uuid4())
        assert result == original

    # ------------------------------------------------------------------
    # record_detection
    # ------------------------------------------------------------------

    def test_record_detection_calls_upsert(self):
        session_id = uuid4()
        self.service.record_detection(session_id, track_id=42, class_name="helmet", confidence=0.95)
        self.repo.upsert_event.assert_called_once_with(session_id, 42, "helmet", 0.95)

    def test_record_detection_swallows_exception(self):
        self.repo.upsert_event.side_effect = Exception("DB error")
        # Should not raise
        self.service.record_detection(uuid4(), 1, "helmet", 0.9)

    # ------------------------------------------------------------------
    # get_live_stats
    # ------------------------------------------------------------------

    def test_get_live_stats_returns_counts(self):
        session_id = uuid4()
        tenant_id = uuid4()
        self.repo.get_session.return_value = {
            "id": session_id,
            "status": "active",
            "started_at": None,
        }
        self.repo.get_session_counts.return_value = [
            {"class_name": "helmet", "count": 10},
            {"class_name": "gloves", "count": 4},
        ]

        result = self.service.get_live_stats(session_id, tenant_id)
        assert result["counts"] == {"helmet": 10, "gloves": 4}
        assert result["total"] == 14
        assert result["status"] == "active"

    def test_get_live_stats_not_found_raises(self):
        self.repo.get_session.return_value = None
        with pytest.raises(NotFoundError):
            self.service.get_live_stats(uuid4(), uuid4())

    # ------------------------------------------------------------------
    # list_active
    # ------------------------------------------------------------------

    def test_list_active_delegates_to_repo(self):
        tenant_id = uuid4()
        self.repo.list_active_sessions.return_value = [{"id": uuid4()}]
        result = self.service.list_active(tenant_id)
        assert len(result) == 1
        self.repo.list_active_sessions.assert_called_once_with(tenant_id)
