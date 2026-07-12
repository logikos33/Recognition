"""Tests: GateRepository — all CRUD, stats, and dashboard methods."""
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from app.api.v1.quality.gate_repository import GateRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pool(cursor):
    @contextmanager
    def _conn_ctx():
        conn = MagicMock()
        conn.cursor.return_value = cursor
        yield conn

    pool = MagicMock()
    pool.get_connection.side_effect = _conn_ctx
    return pool


def _repo(cursor):
    return GateRepository(_make_pool(cursor))


# ---------------------------------------------------------------------------
# _row_to_dict / _rows_to_list
# ---------------------------------------------------------------------------

class TestRowToDict:

    def test_none_returns_empty_dict(self):
        r = GateRepository(MagicMock())
        assert r._row_to_dict(None) == {}

    def test_uuid_converted_to_str(self):
        uid = uuid4()
        r = GateRepository(MagicMock())
        result = r._row_to_dict({"id": uid, "name": "x"})
        assert result["id"] == str(uid)

    def test_regular_values_pass_through(self):
        r = GateRepository(MagicMock())
        result = r._row_to_dict({"count": 5, "flag": True, "label": "ok"})
        assert result == {"count": 5, "flag": True, "label": "ok"}


class TestRowsList:

    def test_empty_list(self):
        r = GateRepository(MagicMock())
        assert r._rows_to_list([]) == []

    def test_converts_all_rows(self):
        r = GateRepository(MagicMock())
        rows = [{"id": "a", "status": "ok"}, {"id": "b", "status": "nok"}]
        result = r._rows_to_list(rows)
        assert len(result) == 2
        assert result[1]["id"] == "b"


# ---------------------------------------------------------------------------
# create_piece
# ---------------------------------------------------------------------------

class TestCreatePiece:

    def test_returns_piece_dict(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "p-1", "status": "idle", "piece_number": "PN-001"}
        result = _repo(cur).create_piece("tenant_a", {
            "piece_number": "PN-001", "work_order": None,
            "product_type": None, "status": "idle", "operator_id": None,
        })
        assert result["piece_number"] == "PN-001"
        assert result["status"] == "idle"

    def test_set_schema_and_insert_executed(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "p-1"}
        _repo(cur).create_piece("tenant_a", {
            "piece_number": "X", "work_order": None,
            "product_type": None, "status": "idle", "operator_id": None,
        })
        # SET search_path + INSERT = 2 execute calls
        assert cur.execute.call_count >= 2


# ---------------------------------------------------------------------------
# get_piece
# ---------------------------------------------------------------------------

class TestGetPiece:

    def test_returns_dict_when_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "p-1", "status": "idle"}
        result = _repo(cur).get_piece("tenant_a", "p-1")
        assert result["id"] == "p-1"

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        assert _repo(cur).get_piece("tenant_a", "missing") is None


# ---------------------------------------------------------------------------
# get_pieces
# ---------------------------------------------------------------------------

class TestGetPieces:

    def test_no_filters_returns_all(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "p-1"}, {"id": "p-2"}]
        result = _repo(cur).get_pieces("tenant_a")
        assert len(result) == 2

    def test_status_filter_added_to_query(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        _repo(cur).get_pieces("tenant_a", filters={"status": "idle"})
        sql = cur.execute.call_args[0][0]
        assert "status" in sql

    def test_all_filters_applied(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        _repo(cur).get_pieces("tenant_a", filters={
            "status": "approved", "work_order": "WO1",
            "product_type": "TypeA", "date_from": "2026-01-01", "date_to": "2026-06-30",
        })
        sql = cur.execute.call_args[0][0]
        assert "work_order" in sql
        assert "product_type" in sql
        assert "date_from" in sql
        assert "date_to" in sql

    def test_empty_filter_values_ignored(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        _repo(cur).get_pieces("tenant_a", filters={"status": "", "work_order": None})
        sql = cur.execute.call_args[0][0]
        assert "work_order" not in sql


# ---------------------------------------------------------------------------
# update_piece_status
# ---------------------------------------------------------------------------

class TestUpdatePieceStatus:

    def test_no_extra_fields(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "p-1", "status": "identified"}
        result = _repo(cur).update_piece_status("tenant_a", "p-1", "identified")
        assert result["status"] == "identified"

    def test_with_extra_fields_included_in_sql(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "p-1", "status": "approved"}
        _repo(cur).update_piece_status(
            "tenant_a", "p-1", "approved",
            {"approved_at": "2026-01-01T00:00:00", "last_inspection_confidence": 0.95},
        )
        sql = cur.execute.call_args[0][0]
        assert "approved_at" in sql

    def test_returns_empty_dict_when_row_none(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        result = _repo(cur).update_piece_status("tenant_a", "p-1", "idle")
        assert result == {}


# ---------------------------------------------------------------------------
# update_piece
# ---------------------------------------------------------------------------

class TestUpdatePiece:

    def test_empty_data_falls_back_to_get_piece(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "p-1", "status": "idle"}
        result = _repo(cur).update_piece("tenant_a", "p-1", {})
        assert result["id"] == "p-1"

    def test_with_data_updates_field(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "p-1", "wiser_exported": True}
        _repo(cur).update_piece("tenant_a", "p-1", {"wiser_exported": True})
        sql = cur.execute.call_args[0][0]
        assert "wiser_exported" in sql

    def test_returns_empty_dict_when_row_none(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        result = _repo(cur).update_piece("tenant_a", "p-1", {"wiser_exported": True})
        assert result == {}


# ---------------------------------------------------------------------------
# create_rework
# ---------------------------------------------------------------------------

class TestCreateRework:

    def test_returns_rework_dict(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "rw-1", "piece_id": "p-1", "validation_type": "v1"}
        result = _repo(cur).create_rework("tenant_a", {
            "piece_id": "p-1", "validation_type": "v1", "defect_type": None,
            "defect_description": None, "photo_before_path": None,
            "photo_before_r2_key": None, "operator_id": None,
        })
        assert result["piece_id"] == "p-1"
        assert result["validation_type"] == "v1"


# ---------------------------------------------------------------------------
# complete_rework
# ---------------------------------------------------------------------------

class TestCompleteRework:

    def test_returns_updated_rework(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "rw-1", "completed_at": "2026-06-01T12:00:00"}
        now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = _repo(cur).complete_rework("tenant_a", "rw-1", now, 300)
        assert result["id"] == "rw-1"

    def test_with_photo_paths_in_params(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "rw-1"}
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        _repo(cur).complete_rework("tenant_a", "rw-1", now, 120, "/photo.jpg", "r2/key")
        params = cur.execute.call_args[0][1]
        assert params["photo_after_path"] == "/photo.jpg"
        assert params["photo_after_r2_key"] == "r2/key"

    def test_returns_empty_dict_when_row_none(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        result = _repo(cur).complete_rework("tenant_a", "rw-1", now, 0)
        assert result == {}


# ---------------------------------------------------------------------------
# get_reworks_for_piece / get_reworks
# ---------------------------------------------------------------------------

class TestGetReworksForPiece:

    def test_returns_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "rw-1"}, {"id": "rw-2"}]
        result = _repo(cur).get_reworks_for_piece("tenant_a", "p-1")
        assert len(result) == 2


class TestGetReworks:

    def test_no_filters(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        _repo(cur).get_reworks("tenant_a")
        sql = cur.execute.call_args[0][0]
        assert "quality_reworks" in sql

    def test_all_filters_applied(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        _repo(cur).get_reworks("tenant_a", filters={
            "piece_id": "p-1", "validation_type": "v1",
            "date_from": "2026-01-01", "date_to": "2026-06-30",
        })
        sql = cur.execute.call_args[0][0]
        assert "piece_id" in sql
        assert "validation_type" in sql
        assert "date_from" in sql

    def test_empty_filter_ignored(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        _repo(cur).get_reworks("tenant_a", filters={"piece_id": None, "validation_type": ""})
        sql = cur.execute.call_args[0][0]
        assert "piece_id" not in sql


# ---------------------------------------------------------------------------
# create_export_log / get_exports_for_piece
# ---------------------------------------------------------------------------

class TestCreateExportLog:

    def test_returns_log_dict(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "exp-1", "success": True}
        result = _repo(cur).create_export_log("tenant_a", {
            "piece_id": "p-1", "export_method": "file_share",
            "file_path": "/export/p1.json", "success": True, "error_message": "",
        })
        assert result["success"] is True


class TestGetExportsForPiece:

    def test_returns_export_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "exp-1"}, {"id": "exp-2"}]
        result = _repo(cur).get_exports_for_piece("tenant_a", "p-1")
        assert len(result) == 2


# ---------------------------------------------------------------------------
# quality_stations
# ---------------------------------------------------------------------------

class TestCreateOrUpdateStation:

    def test_returns_station_dict(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "st-1", "station_code": "BANCADA_A"}
        result = _repo(cur).create_or_update_station("tenant_a", {
            "station_code": "BANCADA_A", "name": "Bancada A",
            "description": None, "current_piece_id": None, "camera_ids": [],
        })
        assert result["station_code"] == "BANCADA_A"


class TestGetStation:

    def test_returns_dict_when_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "st-1", "station_code": "BANCADA_A"}
        result = _repo(cur).get_station("tenant_a", "BANCADA_A")
        assert result["station_code"] == "BANCADA_A"

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        assert _repo(cur).get_station("tenant_a", "MISSING") is None


class TestGetAllStations:

    def test_returns_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"station_code": "A"}, {"station_code": "B"}]
        result = _repo(cur).get_all_stations("tenant_a")
        assert len(result) == 2

    def test_empty_returns_empty_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        assert _repo(cur).get_all_stations("tenant_a") == []


# ---------------------------------------------------------------------------
# get_overview_stats
# ---------------------------------------------------------------------------

class TestGetOverviewStats:

    def test_returns_stats_with_rework_count(self):
        cur = MagicMock()
        cur.fetchone.side_effect = [
            {"pieces_today": 10, "pieces_approved": 8, "pieces_nok": 2, "nok_rate": 20.0},
            {"rework_count": 3},
        ]
        result = _repo(cur).get_overview_stats("tenant_a")
        assert result["pieces_today"] == 10
        assert result["rework_count"] == 3

    def test_rework_count_zero_when_row_is_none(self):
        cur = MagicMock()
        cur.fetchone.side_effect = [
            {"pieces_today": 0, "pieces_approved": 0, "pieces_nok": 0, "nok_rate": None},
            None,
        ]
        result = _repo(cur).get_overview_stats("tenant_a")
        assert result["rework_count"] == 0


# ---------------------------------------------------------------------------
# get_rework_stats
# ---------------------------------------------------------------------------

class TestGetReworkStats:

    def test_returns_by_validation_avg_and_defect(self):
        cur = MagicMock()
        cur.fetchall.return_value = [
            {"validation_type": "v1", "count": 5},
            {"validation_type": "v2", "count": 2},
        ]
        cur.fetchone.side_effect = [
            {"avg_duration": 120.5},
            {"defect_type": "surface_scratch"},
        ]
        result = _repo(cur).get_rework_stats("tenant_a")
        assert result["by_validation"]["v1"] == 5
        assert result["avg_rework_duration_seconds"] == 120.5
        assert result["most_common_defect"] == "surface_scratch"

    def test_no_reworks_returns_zero_defaults(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        cur.fetchone.side_effect = [{"avg_duration": None}, None]
        result = _repo(cur).get_rework_stats("tenant_a")
        assert result["by_validation"] == {}
        assert result["avg_rework_duration_seconds"] == 0.0
        assert result["most_common_defect"] is None


# ---------------------------------------------------------------------------
# get_dashboard_summary
# ---------------------------------------------------------------------------

class TestGetDashboardSummary:

    def test_ok_pct_calculated_correctly(self):
        cur = MagicMock()
        cur.fetchone.side_effect = [
            {"pieces_total": 10, "pieces_approved": 8, "nok_count": 2, "rework_active": 1},
            {"stations_total": 3, "stations_active": 2},
        ]
        result = _repo(cur).get_dashboard_summary("tenant_a")
        assert result["ok_pct"] == 80.0
        assert result["pieces_total"] == 10
        assert result["stations_active"] == 2

    def test_ok_pct_zero_when_no_pieces(self):
        cur = MagicMock()
        cur.fetchone.side_effect = [
            {"pieces_total": 0, "pieces_approved": 0, "nok_count": 0, "rework_active": 0},
            {"stations_total": 1, "stations_active": 0},
        ]
        result = _repo(cur).get_dashboard_summary("tenant_a")
        assert result["ok_pct"] == 0.0

    def test_none_values_coerced_to_zero(self):
        cur = MagicMock()
        cur.fetchone.side_effect = [
            {"pieces_total": None, "pieces_approved": None, "nok_count": None, "rework_active": None},
            {"stations_total": None, "stations_active": None},
        ]
        result = _repo(cur).get_dashboard_summary("tenant_a")
        assert result["pieces_total"] == 0
        assert result["nok_count"] == 0


# ---------------------------------------------------------------------------
# get_stations_live
# ---------------------------------------------------------------------------

def _station_row(piece_status=None, total_rework=0, has_piece=True, with_operator=False):
    return {
        "station_id": "st-1",
        "station_code": "BANCADA_A",
        "station_name": "Bancada A",
        "camera_ids": ["cam-1"],
        "is_active": True,
        "piece_id": "p-1" if has_piece else None,
        "piece_number": "PN-001" if has_piece else None,
        "work_order": "WO-1" if has_piece else None,
        "product_type": "TypeA" if has_piece else None,
        "piece_status": piece_status,
        "piece_step_started_at": None,
        "total_rework_count": total_rework,
        "operator_id": "op-1" if with_operator else None,
        "operator_name": "João" if with_operator else None,
    }


class TestGetStationsLive:

    def test_no_piece_returns_ok_status(self):
        cur = MagicMock()
        cur.fetchall.return_value = [_station_row(piece_status=None, has_piece=False)]
        result = _repo(cur).get_stations_live("tenant_a")
        assert result[0]["status"] == "ok"
        assert result[0]["active_piece"] is None

    def test_rework_v1_one_count_is_warning(self):
        cur = MagicMock()
        cur.fetchall.return_value = [_station_row(piece_status="rework_v1", total_rework=1)]
        result = _repo(cur).get_stations_live("tenant_a")
        assert result[0]["status"] == "warning"

    def test_rework_v2_two_reworks_is_critical(self):
        cur = MagicMock()
        cur.fetchall.return_value = [_station_row(piece_status="rework_v2", total_rework=2)]
        result = _repo(cur).get_stations_live("tenant_a")
        assert result[0]["status"] == "critical"

    def test_validating_state_is_ok(self):
        cur = MagicMock()
        cur.fetchall.return_value = [_station_row(piece_status="validating_v1")]
        result = _repo(cur).get_stations_live("tenant_a")
        assert result[0]["status"] == "ok"

    def test_operator_included_when_present(self):
        cur = MagicMock()
        cur.fetchall.return_value = [_station_row(piece_status="identified", with_operator=True)]
        result = _repo(cur).get_stations_live("tenant_a")
        assert result[0]["operator"]["name"] == "João"

    def test_operator_none_when_absent(self):
        cur = MagicMock()
        cur.fetchall.return_value = [_station_row(piece_status="identified", with_operator=False)]
        result = _repo(cur).get_stations_live("tenant_a")
        assert result[0]["operator"] is None

    def test_step_started_at_converted_to_isoformat(self):
        now = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
        cur = MagicMock()
        row = _station_row(piece_status="identified")
        row["piece_step_started_at"] = now
        cur.fetchall.return_value = [row]
        result = _repo(cur).get_stations_live("tenant_a")
        assert result[0]["active_piece"]["started_at"] == now.isoformat()

    def test_status_label_for_approved(self):
        cur = MagicMock()
        cur.fetchall.return_value = [_station_row(piece_status="approved")]
        result = _repo(cur).get_stations_live("tenant_a")
        assert result[0]["active_piece"]["status_label"] == "Aprovada"

    def test_status_label_fallback_for_unknown(self):
        cur = MagicMock()
        cur.fetchall.return_value = [_station_row(piece_status="unknown_state")]
        result = _repo(cur).get_stations_live("tenant_a")
        assert result[0]["active_piece"]["status_label"] == "unknown_state"

    def test_empty_returns_empty_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        assert _repo(cur).get_stations_live("tenant_a") == []

    def test_camera_ids_defaults_to_empty_list(self):
        cur = MagicMock()
        row = _station_row(piece_status=None, has_piece=False)
        row["camera_ids"] = None
        cur.fetchall.return_value = [row]
        result = _repo(cur).get_stations_live("tenant_a")
        assert result[0]["camera_ids"] == []
