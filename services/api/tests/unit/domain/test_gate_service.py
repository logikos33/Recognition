"""Tests: GateService — state machine orchestration, Redis events, and lifecycle methods."""
import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.api.v1.quality.gate_service import GateService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(mock_repo=None, mock_sm=None):
    pool = MagicMock()
    redis = MagicMock()
    svc = GateService(pool, redis)
    if mock_repo is not None:
        svc._get_repo = MagicMock(return_value=mock_repo)
    if mock_sm is not None:
        svc._get_sm = MagicMock(return_value=mock_sm)
    return svc, pool, redis


def _mock_pool_with_row(pool, row):
    """Configure pool context manager to return a cursor with a single fetchone row."""
    @contextmanager
    def _conn_ctx():
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = row
        conn.cursor.return_value = cur
        yield conn
    pool.get_connection.side_effect = _conn_ctx


# ---------------------------------------------------------------------------
# _publish_redis
# ---------------------------------------------------------------------------

class TestPublishRedis:

    def test_publishes_json_to_channel(self):
        svc, _, redis = _make_service()
        svc._publish_redis("quality:test", {"event": "x", "val": 42})
        redis.publish.assert_called_once()
        channel, payload = redis.publish.call_args[0]
        assert channel == "quality:test"
        assert json.loads(payload)["event"] == "x"

    def test_exception_is_swallowed(self):
        svc, _, redis = _make_service()
        redis.publish.side_effect = Exception("redis down")
        svc._publish_redis("quality:test", {})  # must not raise

    def test_serializes_non_str_values_via_default_str(self):
        from uuid import uuid4
        svc, _, redis = _make_service()
        uid = uuid4()
        svc._publish_redis("q:ch", {"id": uid})
        payload = json.loads(redis.publish.call_args[0][1])
        assert payload["id"] == str(uid)


# ---------------------------------------------------------------------------
# _signal_tower
# ---------------------------------------------------------------------------

class TestSignalTower:

    def _run_signal(self, color):
        svc, _, _ = _make_service()
        mock_tc_mod = MagicMock()
        mock_controller = MagicMock()
        mock_tc_mod.get_tower_controller.return_value = mock_controller
        with patch.dict(sys.modules, {"app.api.v1.quality.tower_controller": mock_tc_mod}):
            svc._signal_tower("tenant_a", "BANCADA_A", color)
        return mock_controller

    def test_green_calls_set_green(self):
        ctrl = self._run_signal("green")
        ctrl.set_green.assert_called_once_with("BANCADA_A")

    def test_red_calls_set_red(self):
        ctrl = self._run_signal("red")
        ctrl.set_red.assert_called_once_with("BANCADA_A")

    def test_idle_calls_set_idle(self):
        ctrl = self._run_signal("idle")
        ctrl.set_idle.assert_called_once_with("BANCADA_A")

    def test_exception_is_swallowed(self):
        svc, _, _ = _make_service()
        mock_tc_mod = MagicMock()
        mock_tc_mod.get_tower_controller.side_effect = Exception("hw error")
        with patch.dict(sys.modules, {"app.api.v1.quality.tower_controller": mock_tc_mod}):
            svc._signal_tower("tenant_a", "BANCADA_A", "green")  # must not raise


# ---------------------------------------------------------------------------
# create_piece
# ---------------------------------------------------------------------------

class TestCreatePiece:

    def test_returns_piece_and_publishes_event(self):
        repo = MagicMock()
        repo.create_piece.return_value = {"id": "p-1", "status": "idle", "piece_number": "PN-001"}
        svc, _, redis = _make_service(repo)
        result = svc.create_piece("tenant_a", "PN-001", "WO-1", "TypeA", "op-1")
        assert result["id"] == "p-1"
        repo.create_piece.assert_called_once()
        redis.publish.assert_called_once()

    def test_published_channel_contains_schema(self):
        repo = MagicMock()
        repo.create_piece.return_value = {"id": "p-1", "status": "idle"}
        svc, _, redis = _make_service(repo)
        svc.create_piece("tenant_a", "PN-001")
        channel = redis.publish.call_args[0][0]
        assert "tenant_a" in channel

    def test_piece_data_passed_to_repo(self):
        repo = MagicMock()
        repo.create_piece.return_value = {"id": "p-1"}
        svc, _, _ = _make_service(repo)
        svc.create_piece("tenant_a", "PN-001", "WO-99", "TypeB", "op-99")
        call_data = repo.create_piece.call_args[0][1]
        assert call_data["piece_number"] == "PN-001"
        assert call_data["work_order"] == "WO-99"
        assert call_data["status"] == "idle"


# ---------------------------------------------------------------------------
# identify_piece
# ---------------------------------------------------------------------------

class TestIdentifyPiece:

    def test_transitions_and_returns_updated_piece(self):
        repo = MagicMock()
        sm = MagicMock()
        repo.get_piece.return_value = {"id": "p-1", "status": "idle"}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "identified"}
        svc, _, redis = _make_service(repo, sm)
        result = svc.identify_piece("tenant_a", "p-1", "PN-001")
        assert result["status"] == "identified"
        sm.transition.assert_called_once_with("idle", "identified")
        redis.publish.assert_called_once()

    def test_raises_if_piece_not_found(self):
        repo = MagicMock()
        repo.get_piece.return_value = None
        svc, _, _ = _make_service(repo)
        with pytest.raises(ValueError, match="Peça não encontrada"):
            svc.identify_piece("tenant_a", "missing", "PN-001")

    def test_work_order_included_when_provided(self):
        repo = MagicMock()
        sm = MagicMock()
        repo.get_piece.return_value = {"id": "p-1", "status": "idle"}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "identified"}
        svc, _, _ = _make_service(repo, sm)
        svc.identify_piece("tenant_a", "p-1", "PN-001", work_order="WO-42")
        extra = repo.update_piece_status.call_args[0][3]
        assert extra.get("work_order") == "WO-42"

    def test_work_order_omitted_when_not_provided(self):
        repo = MagicMock()
        sm = MagicMock()
        repo.get_piece.return_value = {"id": "p-1", "status": "idle"}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "identified"}
        svc, _, _ = _make_service(repo, sm)
        svc.identify_piece("tenant_a", "p-1", "PN-001")
        extra = repo.update_piece_status.call_args[0][3]
        assert "work_order" not in extra


# ---------------------------------------------------------------------------
# start_inspection
# ---------------------------------------------------------------------------

class TestStartInspection:

    def test_from_identified_transitions_to_validating_v1(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.is_rework.return_value = False
        sm.get_validation_type.return_value = "v1"
        repo.get_piece.return_value = {"id": "p-1", "status": "identified"}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "validating_v1"}
        svc, _, redis = _make_service(repo, sm)
        result = svc.start_inspection("tenant_a", "p-1")
        assert result["status"] == "validating_v1"
        repo.update_piece_status.assert_called_once_with("tenant_a", "p-1", "validating_v1")
        redis.publish.assert_called_once()

    def test_from_rework_v2_transitions_to_validating_v2(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.is_rework.return_value = True
        sm.get_validation_type.return_value = "v2"
        repo.get_piece.return_value = {"id": "p-1", "status": "rework_v2"}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "validating_v2"}
        svc, _, _ = _make_service(repo, sm)
        svc.start_inspection("tenant_a", "p-1")
        repo.update_piece_status.assert_called_once_with("tenant_a", "p-1", "validating_v2")

    def test_from_rework_v3_transitions_to_validating_v3(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.is_rework.return_value = True
        sm.get_validation_type.return_value = "v3"
        repo.get_piece.return_value = {"id": "p-1", "status": "rework_v3"}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "validating_v3"}
        svc, _, _ = _make_service(repo, sm)
        svc.start_inspection("tenant_a", "p-1")
        repo.update_piece_status.assert_called_once_with("tenant_a", "p-1", "validating_v3")

    def test_invalid_state_raises(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.is_rework.return_value = False
        repo.get_piece.return_value = {"id": "p-1", "status": "idle"}
        svc, _, _ = _make_service(repo, sm)
        with pytest.raises(ValueError, match="Não é possível iniciar inspeção"):
            svc.start_inspection("tenant_a", "p-1")

    def test_piece_not_found_raises(self):
        repo = MagicMock()
        repo.get_piece.return_value = None
        svc, _, _ = _make_service(repo)
        with pytest.raises(ValueError, match="Peça não encontrada"):
            svc.start_inspection("tenant_a", "missing")

    def test_camera_id_triggers_celery_dispatch(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.is_rework.return_value = False
        sm.get_validation_type.return_value = "v1"
        repo.get_piece.return_value = {"id": "p-1", "status": "identified"}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "validating_v1"}
        svc, _, _ = _make_service(repo, sm)
        mock_task = MagicMock()
        mock_qi_mod = MagicMock()
        mock_qi_mod.run_quality_gate_inspection = mock_task
        with patch.dict(sys.modules, {
            "app.infrastructure.queue.tasks.quality_inference": mock_qi_mod
        }):
            svc.start_inspection("tenant_a", "p-1", camera_id="cam-1")
        mock_task.delay.assert_called_once()
        kwargs = mock_task.delay.call_args[1]
        assert kwargs["piece_id"] == "p-1"
        assert kwargs["camera_id"] == "cam-1"

    def test_no_camera_id_skips_celery_dispatch(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.is_rework.return_value = False
        sm.get_validation_type.return_value = "v1"
        repo.get_piece.return_value = {"id": "p-1", "status": "identified"}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "validating_v1"}
        svc, _, _ = _make_service(repo, sm)
        # With no camera, the dispatch block is never entered
        result = svc.start_inspection("tenant_a", "p-1", camera_id=None)
        assert result["status"] == "validating_v1"

    def test_celery_exception_swallowed(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.is_rework.return_value = False
        sm.get_validation_type.return_value = "v1"
        repo.get_piece.return_value = {"id": "p-1", "status": "identified"}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "validating_v1"}
        svc, _, _ = _make_service(repo, sm)
        mock_task = MagicMock()
        mock_task.delay.side_effect = Exception("celery unavailable")
        mock_qi_mod = MagicMock()
        mock_qi_mod.run_quality_gate_inspection = mock_task
        with patch.dict(sys.modules, {
            "app.infrastructure.queue.tasks.quality_inference": mock_qi_mod
        }):
            svc.start_inspection("tenant_a", "p-1", camera_id="cam-1")  # must not raise


# ---------------------------------------------------------------------------
# process_inspection_result
# ---------------------------------------------------------------------------

class TestProcessInspectionResult:

    def test_ok_result_advances_to_next_state(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.get_validation_type.return_value = "v1"
        sm.get_next_validation.return_value = "validating_v2"
        repo.get_piece.return_value = {"id": "p-1", "status": "validating_v1", "total_rework_count": 0}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "validating_v2"}
        svc, _, redis = _make_service(repo, sm)
        result = svc.process_inspection_result("tenant_a", "p-1", "ok", 0.95)
        assert result["status"] == "validating_v2"
        redis.publish.assert_called_once()

    def test_ok_to_approved_sets_approved_at_in_extra(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.get_validation_type.return_value = "v2"
        sm.get_next_validation.return_value = "approved"
        repo.get_piece.return_value = {"id": "p-1", "status": "validating_v2", "total_rework_count": 0}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "approved"}
        svc, _, _ = _make_service(repo, sm)
        svc.process_inspection_result("tenant_a", "p-1", "ok", 0.99)
        args = repo.update_piece_status.call_args[0]
        assert args[2] == "approved"
        assert "approved_at" in args[3]

    def test_ok_to_approved_triggers_wiser_export(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.get_validation_type.return_value = "v2"
        sm.get_next_validation.return_value = "approved"
        repo.get_piece.return_value = {"id": "p-1", "status": "validating_v2", "total_rework_count": 0}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "approved"}
        svc, _, _ = _make_service(repo, sm)
        mock_wiser = MagicMock()
        mock_wiser.export_piece.return_value = {"success": True, "method": "file_share", "path": "/f"}
        mock_wi_mod = MagicMock()
        mock_wi_mod.get_wiser_integration.return_value = mock_wiser
        with patch.dict(sys.modules, {"app.api.v1.quality.wiser_integration": mock_wi_mod}):
            svc.process_inspection_result("tenant_a", "p-1", "ok", 0.99, photo_path="/photo.jpg")
        mock_wiser.export_piece.assert_called_once()
        repo.update_piece.assert_called_once()
        repo.create_export_log.assert_called_once()

    def test_ok_to_approved_wiser_failure_logs_warning(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.get_validation_type.return_value = "v2"
        sm.get_next_validation.return_value = "approved"
        repo.get_piece.return_value = {"id": "p-1", "status": "validating_v2", "total_rework_count": 0}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "approved"}
        svc, _, _ = _make_service(repo, sm)
        mock_wiser = MagicMock()
        mock_wiser.export_piece.return_value = {"success": False, "error": "disk full"}
        mock_wi_mod = MagicMock()
        mock_wi_mod.get_wiser_integration.return_value = mock_wiser
        with patch.dict(sys.modules, {"app.api.v1.quality.wiser_integration": mock_wi_mod}):
            svc.process_inspection_result("tenant_a", "p-1", "ok", 0.99, photo_path="/p")
        # Should not raise; update_piece and create_export_log NOT called
        repo.update_piece.assert_not_called()

    def test_ok_with_station_code_signals_green_tower(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.get_validation_type.return_value = "v1"
        sm.get_next_validation.return_value = "validating_v2"
        repo.get_piece.return_value = {"id": "p-1", "status": "validating_v1", "total_rework_count": 0}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "validating_v2"}
        svc, _, _ = _make_service(repo, sm)
        svc._signal_tower = MagicMock()
        svc.process_inspection_result("tenant_a", "p-1", "ok", 0.9, station_code="BANCADA_A")
        svc._signal_tower.assert_called_once_with("tenant_a", "BANCADA_A", "green")

    def test_nok_creates_rework_record(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.get_validation_type.return_value = "v1"
        sm.get_rework_state.return_value = "rework_v1"
        repo.get_piece.return_value = {"id": "p-1", "status": "validating_v1", "total_rework_count": 0}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "rework_v1"}
        svc, _, _ = _make_service(repo, sm)
        svc.process_inspection_result("tenant_a", "p-1", "nok", 0.30, defect_description="scratch")
        repo.create_rework.assert_called_once()
        rework_data = repo.create_rework.call_args[0][1]
        assert rework_data["defect_description"] == "scratch"
        assert rework_data["validation_type"] == "v1"

    def test_nok_increments_rework_count(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.get_validation_type.return_value = "v1"
        sm.get_rework_state.return_value = "rework_v1"
        repo.get_piece.return_value = {"id": "p-1", "status": "validating_v1", "total_rework_count": 2}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "rework_v1"}
        svc, _, _ = _make_service(repo, sm)
        svc.process_inspection_result("tenant_a", "p-1", "nok", 0.2)
        extra = repo.update_piece_status.call_args[0][3]
        assert extra["total_rework_count"] == 3

    def test_nok_with_station_code_signals_red_tower(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.get_validation_type.return_value = "v1"
        sm.get_rework_state.return_value = "rework_v1"
        repo.get_piece.return_value = {"id": "p-1", "status": "validating_v1", "total_rework_count": 0}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "rework_v1"}
        svc, _, _ = _make_service(repo, sm)
        svc._signal_tower = MagicMock()
        svc.process_inspection_result("tenant_a", "p-1", "nok", 0.2, station_code="BANCADA_A")
        svc._signal_tower.assert_called_once_with("tenant_a", "BANCADA_A", "red")

    def test_piece_not_found_raises(self):
        repo = MagicMock()
        repo.get_piece.return_value = None
        svc, _, _ = _make_service(repo)
        with pytest.raises(ValueError, match="Peça não encontrada"):
            svc.process_inspection_result("tenant_a", "missing", "ok", 0.9)

    def test_not_in_validation_state_raises(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.get_validation_type.return_value = None
        repo.get_piece.return_value = {"id": "p-1", "status": "idle", "total_rework_count": 0}
        svc, _, _ = _make_service(repo, sm)
        with pytest.raises(ValueError, match="não está em estado de validação"):
            svc.process_inspection_result("tenant_a", "p-1", "ok", 0.9)

    def test_no_next_state_raises(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.get_validation_type.return_value = "v1"
        sm.get_next_validation.return_value = None
        repo.get_piece.return_value = {"id": "p-1", "status": "validating_v1", "total_rework_count": 0}
        svc, _, _ = _make_service(repo, sm)
        with pytest.raises(ValueError, match="Sem próximo estado"):
            svc.process_inspection_result("tenant_a", "p-1", "ok", 0.9)


# ---------------------------------------------------------------------------
# mark_false_positive
# ---------------------------------------------------------------------------

class TestMarkFalsePositive:

    def test_reverts_to_identified_and_publishes(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.is_validating.return_value = True
        repo.get_piece.return_value = {"id": "p-1", "status": "validating_v1"}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "identified"}
        svc, _, redis = _make_service(repo, sm)
        result = svc.mark_false_positive("tenant_a", "p-1")
        assert result["status"] == "identified"
        sm.transition.assert_called_once_with("validating_v1", "identified")
        redis.publish.assert_called_once()

    def test_piece_not_found_raises(self):
        repo = MagicMock()
        repo.get_piece.return_value = None
        svc, _, _ = _make_service(repo)
        with pytest.raises(ValueError, match="Peça não encontrada"):
            svc.mark_false_positive("tenant_a", "missing")

    def test_not_in_validating_state_raises(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.is_validating.return_value = False
        repo.get_piece.return_value = {"id": "p-1", "status": "idle"}
        svc, _, _ = _make_service(repo, sm)
        with pytest.raises(ValueError, match="Falso positivo só permitido"):
            svc.mark_false_positive("tenant_a", "p-1")

    def test_with_inspection_id_triggers_sql_update(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.is_validating.return_value = True
        repo.get_piece.return_value = {"id": "p-1", "status": "validating_v1"}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "identified"}
        svc, pool, _ = _make_service(repo, sm)
        _mock_pool_with_row(pool, None)
        svc.mark_false_positive("tenant_a", "p-1", inspection_id="insp-1")
        pool.get_connection.assert_called_once()

    def test_inspection_sql_exception_swallowed(self):
        repo = MagicMock()
        sm = MagicMock()
        sm.is_validating.return_value = True
        repo.get_piece.return_value = {"id": "p-1", "status": "validating_v1"}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "identified"}
        svc, pool, _ = _make_service(repo, sm)
        pool.get_connection.side_effect = Exception("db error")
        svc.mark_false_positive("tenant_a", "p-1", inspection_id="insp-1")  # must not raise


# ---------------------------------------------------------------------------
# release_to_bench_b
# ---------------------------------------------------------------------------

class TestReleaseToBenchB:

    def test_transitions_to_validating_v3(self):
        repo = MagicMock()
        sm = MagicMock()
        repo.get_piece.return_value = {"id": "p-1", "status": "waiting_bench_b"}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "validating_v3"}
        svc, _, redis = _make_service(repo, sm)
        result = svc.release_to_bench_b("tenant_a", "p-1")
        assert result["status"] == "validating_v3"
        sm.transition.assert_called_once_with("waiting_bench_b", "validating_v3")
        redis.publish.assert_called_once()

    def test_with_station_code_signals_idle_tower(self):
        repo = MagicMock()
        sm = MagicMock()
        repo.get_piece.return_value = {"id": "p-1", "status": "waiting_bench_b"}
        repo.update_piece_status.return_value = {"id": "p-1", "status": "validating_v3"}
        svc, _, _ = _make_service(repo, sm)
        svc._signal_tower = MagicMock()
        svc.release_to_bench_b("tenant_a", "p-1", station_code="BANCADA_B")
        svc._signal_tower.assert_called_once_with("tenant_a", "BANCADA_B", "idle")

    def test_piece_not_found_raises(self):
        repo = MagicMock()
        repo.get_piece.return_value = None
        svc, _, _ = _make_service(repo)
        with pytest.raises(ValueError, match="Peça não encontrada"):
            svc.release_to_bench_b("tenant_a", "missing")


# ---------------------------------------------------------------------------
# start_rework
# ---------------------------------------------------------------------------

class TestStartRework:

    def test_creates_rework_and_publishes(self):
        repo = MagicMock()
        repo.create_rework.return_value = {"id": "rw-1", "piece_id": "p-1"}
        svc, _, redis = _make_service(repo)
        result = svc.start_rework("tenant_a", "p-1", "v1", "surface_scratch")
        assert result["id"] == "rw-1"
        repo.create_rework.assert_called_once()
        redis.publish.assert_called_once()

    def test_published_event_is_rework_started(self):
        repo = MagicMock()
        repo.create_rework.return_value = {"id": "rw-1"}
        svc, _, redis = _make_service(repo)
        svc.start_rework("tenant_a", "p-1", "v1", "defect_type")
        payload = json.loads(redis.publish.call_args[0][1])
        assert payload["event"] == "rework_started"

    def test_rework_data_passed_correctly(self):
        repo = MagicMock()
        repo.create_rework.return_value = {"id": "rw-1"}
        svc, _, _ = _make_service(repo)
        svc.start_rework("tenant_a", "p-1", "v2", "scratch", "desc text", "/photo.jpg", "op-1")
        data = repo.create_rework.call_args[0][1]
        assert data["validation_type"] == "v2"
        assert data["defect_type"] == "scratch"
        assert data["defect_description"] == "desc text"
        assert data["photo_before_path"] == "/photo.jpg"
        assert data["operator_id"] == "op-1"


# ---------------------------------------------------------------------------
# complete_rework
# ---------------------------------------------------------------------------

class TestCompleteRework:

    def _setup_pool_for_rework(self, svc, pool, rework_row):
        call_count = [0]

        @contextmanager
        def _conn_ctx():
            conn = MagicMock()
            cur = MagicMock()
            if call_count[0] == 0:
                cur.fetchone.return_value = rework_row
            call_count[0] += 1
            conn.cursor.return_value = cur
            yield conn

        pool.get_connection.side_effect = _conn_ctx

    def test_calculates_duration_from_datetime_object(self):
        repo = MagicMock()
        svc, pool, redis = _make_service(repo)
        started = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        self._setup_pool_for_rework(svc, pool, {"id": "rw-1", "started_at": started, "piece_id": "p-1"})
        repo.complete_rework.return_value = {"id": "rw-1"}
        svc.complete_rework("tenant_a", "rw-1")
        duration = repo.complete_rework.call_args[0][3]
        assert duration > 0
        redis.publish.assert_called_once()

    def test_calculates_duration_from_iso_string(self):
        repo = MagicMock()
        svc, pool, _ = _make_service(repo)
        self._setup_pool_for_rework(svc, pool, {
            "id": "rw-1", "started_at": "2026-06-01T10:00:00", "piece_id": None
        })
        repo.complete_rework.return_value = {"id": "rw-1"}
        svc.complete_rework("tenant_a", "rw-1")
        duration = repo.complete_rework.call_args[0][3]
        assert duration >= 0

    def test_no_started_at_gives_zero_duration(self):
        repo = MagicMock()
        svc, pool, _ = _make_service(repo)
        self._setup_pool_for_rework(svc, pool, {"id": "rw-1", "started_at": None, "piece_id": None})
        repo.complete_rework.return_value = {"id": "rw-1"}
        svc.complete_rework("tenant_a", "rw-1")
        duration = repo.complete_rework.call_args[0][3]
        assert duration == 0

    def test_rework_not_found_raises(self):
        svc, pool, _ = _make_service()
        _mock_pool_with_row(pool, None)
        with pytest.raises(ValueError, match="Retrabalho não encontrado"):
            svc.complete_rework("tenant_a", "missing")

    def test_piece_time_updated_when_piece_id_present(self):
        repo = MagicMock()
        svc, pool, _ = _make_service(repo)
        started = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        self._setup_pool_for_rework(svc, pool, {"id": "rw-1", "started_at": started, "piece_id": "p-1"})
        repo.complete_rework.return_value = {"id": "rw-1"}
        svc.complete_rework("tenant_a", "rw-1")
        # First pool call = SELECT rework; second = UPDATE quality_pieces
        assert pool.get_connection.call_count == 2

    def test_piece_update_exception_swallowed(self):
        repo = MagicMock()
        svc, pool, _ = _make_service(repo)
        started = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        call_count = [0]

        @contextmanager
        def _conn_ctx():
            conn = MagicMock()
            cur = MagicMock()
            if call_count[0] == 0:
                cur.fetchone.return_value = {"id": "rw-1", "started_at": started, "piece_id": "p-1"}
            else:
                cur.execute.side_effect = Exception("db error")
            call_count[0] += 1
            conn.cursor.return_value = cur
            yield conn

        pool.get_connection.side_effect = _conn_ctx
        repo.complete_rework.return_value = {"id": "rw-1"}
        svc.complete_rework("tenant_a", "rw-1")  # must not raise


# ---------------------------------------------------------------------------
# get_station_status
# ---------------------------------------------------------------------------

class TestGetStationStatus:

    def test_station_not_found_returns_default(self):
        repo = MagicMock()
        repo.get_station.return_value = None
        svc, _, _ = _make_service(repo)
        result = svc.get_station_status("tenant_a", "BANCADA_X")
        assert result == {"station_code": "BANCADA_X", "current_piece": None, "cameras": []}

    def test_station_found_with_piece(self):
        repo = MagicMock()
        repo.get_station.return_value = {
            "station_code": "BANCADA_A",
            "current_piece_id": "p-1",
            "camera_ids": ["cam-1"],
        }
        repo.get_piece.return_value = {"id": "p-1", "status": "identified"}
        svc, _, _ = _make_service(repo)
        result = svc.get_station_status("tenant_a", "BANCADA_A")
        assert result["current_piece"]["id"] == "p-1"
        assert result["cameras"] == ["cam-1"]

    def test_station_found_without_current_piece(self):
        repo = MagicMock()
        repo.get_station.return_value = {
            "station_code": "BANCADA_A",
            "current_piece_id": None,
            "camera_ids": [],
        }
        svc, _, _ = _make_service(repo)
        result = svc.get_station_status("tenant_a", "BANCADA_A")
        assert result["current_piece"] is None
        repo.get_piece.assert_not_called()

    def test_camera_ids_defaults_to_empty_list(self):
        repo = MagicMock()
        repo.get_station.return_value = {
            "station_code": "BANCADA_A",
            "current_piece_id": None,
        }
        svc, _, _ = _make_service(repo)
        result = svc.get_station_status("tenant_a", "BANCADA_A")
        assert result["cameras"] == []
