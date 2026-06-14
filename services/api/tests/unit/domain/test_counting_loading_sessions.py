"""Tests: campos de carga/descarga em CountingSession (CD-03/CD-06/CD-07).

Cobre:
  - roundtrip do model CountingSession (from_row → to_dict) com campos novos
  - update parcial via CountingService.update_session (whitelist + validações)
  - cálculo de erro/agregado do relatório de aceite (validation report)
  - whitelist do CountingRepository.update_session_fields
"""
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.models.counting_session import CountingSession
from app.domain.services.counting_service import CountingService
from app.infrastructure.database.repositories.counting_repository import (
    UPDATABLE_SESSION_FIELDS,
    CountingRepository,
)


def _session_row(**overrides):
    row = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "camera_id": uuid4(),
        "module_code": "fueling",
        "status": "running",
        "total_counts": {"product_box": 42},
        "started_at": datetime(2026, 6, 11, 8, 0, 0),
        "ended_at": None,
        "bay_id": uuid4(),
        "truck_plate": "ABC-1234",
        "direction": "load",
        "expected_count": 100,
        "divergence": -2,
        "video_clip_url": "https://r2.test/clips/sessao.mp4",
        "manual_count": 98,
        "acceptance_status": "accepted",
    }
    row.update(overrides)
    return row


class TestCountingSessionModel:
    """Roundtrip dos campos novos no dataclass."""

    def test_from_row_carries_loading_fields(self):
        row = _session_row()
        session = CountingSession.from_row(row)
        assert session.bay_id == row["bay_id"]
        assert session.truck_plate == "ABC-1234"
        assert session.direction == "load"
        assert session.expected_count == 100
        assert session.divergence == -2
        assert session.video_clip_url == "https://r2.test/clips/sessao.mp4"
        assert session.manual_count == 98
        assert session.acceptance_status == "accepted"

    def test_from_row_defaults_when_fields_absent(self):
        row = _session_row()
        for key in (
            "bay_id", "truck_plate", "direction", "expected_count",
            "divergence", "video_clip_url", "manual_count", "acceptance_status",
        ):
            del row[key]
        session = CountingSession.from_row(row)
        assert session.bay_id is None
        assert session.truck_plate is None
        assert session.acceptance_status is None

    def test_to_dict_serializes_uuids_and_dates(self):
        row = _session_row()
        data = CountingSession.from_row(row).to_dict()
        assert data["id"] == str(row["id"])
        assert data["bay_id"] == str(row["bay_id"])
        assert data["started_at"] == "2026-06-11T08:00:00"
        assert data["ended_at"] is None
        assert data["manual_count"] == 98
        assert data["acceptance_status"] == "accepted"

    def test_roundtrip_preserves_all_loading_fields(self):
        row = _session_row()
        data = CountingSession.from_row(row).to_dict()
        for key in (
            "truck_plate", "direction", "expected_count", "divergence",
            "video_clip_url", "manual_count", "acceptance_status",
        ):
            assert data[key] == row[key]


class TestUpdateSession:
    """PATCH parcial via service."""

    def setup_method(self) -> None:
        self.repo = MagicMock()
        self.service = CountingService(self.repo)
        self.tenant_id = uuid4()
        self.session_id = uuid4()
        self.repo.get_session.return_value = {
            "id": self.session_id,
            "tenant_id": self.tenant_id,
            "status": "running",
        }
        self.repo.update_session_fields.return_value = {"id": self.session_id}

    def test_updates_allowed_fields(self):
        result = self.service.update_session(
            self.session_id, self.tenant_id,
            {"truck_plate": "XYZ-9999", "manual_count": 87,
             "acceptance_status": "accepted"},
        )
        assert result["id"] == self.session_id
        sent = self.repo.update_session_fields.call_args[0][2]
        assert sent["truck_plate"] == "XYZ-9999"
        assert sent["manual_count"] == 87
        assert sent["acceptance_status"] == "accepted"

    def test_rejects_unknown_fields_only(self):
        with pytest.raises(ValidationError, match="atualizável"):
            self.service.update_session(
                self.session_id, self.tenant_id, {"status": "stopped"},
            )

    def test_invalid_acceptance_status(self):
        with pytest.raises(ValidationError, match="acceptance_status"):
            self.service.update_session(
                self.session_id, self.tenant_id, {"acceptance_status": "maybe"},
            )

    def test_invalid_direction(self):
        with pytest.raises(ValidationError, match="direction"):
            self.service.update_session(
                self.session_id, self.tenant_id, {"direction": "sideways"},
            )

    def test_negative_manual_count(self):
        with pytest.raises(ValidationError, match="manual_count"):
            self.service.update_session(
                self.session_id, self.tenant_id, {"manual_count": -1},
            )

    def test_tenant_mismatch_raises_not_found(self):
        self.repo.get_session.return_value = {
            "id": self.session_id, "tenant_id": uuid4(),
        }
        with pytest.raises(NotFoundError):
            self.service.update_session(
                self.session_id, self.tenant_id, {"truck_plate": "AAA-0000"},
            )

    def test_session_missing_raises_not_found(self):
        self.repo.get_session.return_value = None
        with pytest.raises(NotFoundError):
            self.service.update_session(
                self.session_id, self.tenant_id, {"truck_plate": "AAA-0000"},
            )

    def test_expected_count_autocomputes_divergence(self):
        self.repo.get_session_total.return_value = 95
        self.service.update_session(
            self.session_id, self.tenant_id, {"expected_count": 100},
        )
        sent = self.repo.update_session_fields.call_args[0][2]
        assert sent["divergence"] == -5  # system 95 - expected 100

    def test_explicit_divergence_not_overwritten(self):
        self.service.update_session(
            self.session_id, self.tenant_id,
            {"expected_count": 100, "divergence": 7},
        )
        sent = self.repo.update_session_fields.call_args[0][2]
        assert sent["divergence"] == 7
        self.repo.get_session_total.assert_not_called()


class TestValidationReport:
    """CD-07: cálculo de erro por sessão + agregado + pass/fail."""

    def setup_method(self) -> None:
        self.repo = MagicMock()
        self.service = CountingService(self.repo)
        self.tenant_id = uuid4()
        self.start = datetime(2026, 6, 1)
        self.end = datetime(2026, 6, 8)

    def _report(self, sessions, daily, threshold=5.0):
        self.repo.get_validation_sessions.return_value = sessions
        self.repo.get_validation_daily.return_value = daily
        return self.service.get_validation_report(
            self.tenant_id, self.start, self.end, threshold_pct=threshold,
        )

    def test_pass_fail_per_session(self):
        sessions = [
            {"id": uuid4(), "system_count": 100, "manual_count": 100,
             "abs_error": 0, "error_pct": Decimal("0.00")},
            {"id": uuid4(), "system_count": 110, "manual_count": 100,
             "abs_error": 10, "error_pct": Decimal("10.00")},
        ]
        report = self._report(sessions, [], threshold=5.0)
        assert report["sessions"][0]["passed"] is True
        assert report["sessions"][1]["passed"] is False

    def test_threshold_is_inclusive(self):
        sessions = [
            {"id": uuid4(), "system_count": 105, "manual_count": 100,
             "abs_error": 5, "error_pct": Decimal("5.00")},
        ]
        report = self._report(sessions, [], threshold=5.0)
        assert report["sessions"][0]["passed"] is True

    def test_summary_aggregates_all_sessions(self):
        sessions = [
            {"id": uuid4(), "system_count": 100, "manual_count": 100,
             "abs_error": 0, "error_pct": Decimal("0.00")},
            {"id": uuid4(), "system_count": 110, "manual_count": 100,
             "abs_error": 10, "error_pct": Decimal("10.00")},
        ]
        report = self._report(sessions, [], threshold=5.0)
        summary = report["summary"]
        assert summary["sessions_validated"] == 2
        assert summary["system_count"] == 210
        assert summary["manual_count"] == 200
        assert summary["abs_error"] == 10
        assert summary["error_pct"] == 5.0
        assert summary["passed"] is True  # 5.0 <= 5.0

    def test_manual_count_zero_passes_only_if_system_zero(self):
        sessions = [
            {"id": uuid4(), "system_count": 0, "manual_count": 0,
             "abs_error": 0, "error_pct": None},
            {"id": uuid4(), "system_count": 3, "manual_count": 0,
             "abs_error": 3, "error_pct": None},
        ]
        report = self._report(sessions, [])
        assert report["sessions"][0]["passed"] is True
        assert report["sessions"][1]["passed"] is False

    def test_daily_aggregate_pass_fail(self):
        daily = [
            {"day": date(2026, 6, 2), "sessions": 4, "system_total": 400,
             "manual_total": 404, "abs_error": 4, "error_pct": Decimal("0.99")},
            {"day": date(2026, 6, 3), "sessions": 2, "system_total": 150,
             "manual_total": 100, "abs_error": 50, "error_pct": Decimal("50.00")},
        ]
        report = self._report([], daily, threshold=2.0)
        assert report["daily"][0]["passed"] is True
        assert report["daily"][1]["passed"] is False

    def test_empty_period_summary(self):
        report = self._report([], [])
        summary = report["summary"]
        assert summary["sessions_validated"] == 0
        assert summary["error_pct"] is None
        assert summary["passed"] is True  # 0 erro absoluto

    def test_invalid_threshold(self):
        with pytest.raises(ValidationError, match="threshold"):
            self.service.get_validation_report(
                self.tenant_id, self.start, self.end, threshold_pct=-1,
            )

    def test_invalid_period(self):
        with pytest.raises(ValidationError, match="Período"):
            self.service.get_validation_report(
                self.tenant_id, self.end, self.start,
            )

    def test_repo_receives_filters(self):
        bay_id = uuid4()
        self.repo.get_validation_sessions.return_value = []
        self.repo.get_validation_daily.return_value = []
        report = self.service.get_validation_report(
            self.tenant_id, self.start, self.end,
            bay_id=bay_id, threshold_pct=3.0,
        )
        self.repo.get_validation_sessions.assert_called_once_with(
            self.tenant_id, self.start, self.end, bay_id,
        )
        assert report["bay_id"] == str(bay_id)
        assert report["threshold_pct"] == 3.0


class TestRepositoryUpdateWhitelist:
    """update_session_fields só aceita colunas da whitelist fixa."""

    def setup_method(self) -> None:
        self.repo = CountingRepository(MagicMock())
        self.repo._execute_mutation = MagicMock(return_value={"id": "x"})

    def test_whitelist_contains_loading_fields(self):
        for col in (
            "bay_id", "truck_plate", "direction", "expected_count",
            "divergence", "video_clip_url", "manual_count", "acceptance_status",
        ):
            assert col in UPDATABLE_SESSION_FIELDS

    def test_non_whitelisted_fields_ignored(self):
        result = self.repo.update_session_fields(
            uuid4(), uuid4(),
            {"truck_plate": "AAA-1111", "status": "stopped", "id": "hack"},
        )
        assert result == {"id": "x"}
        query = self.repo._execute_mutation.call_args[0][0]
        assert "truck_plate = %s" in query
        assert "status" not in query
        assert "id = %s AND tenant_id = %s" in query

    def test_only_invalid_fields_returns_none_without_query(self):
        result = self.repo.update_session_fields(
            uuid4(), uuid4(), {"status": "stopped"},
        )
        assert result is None
        self.repo._execute_mutation.assert_not_called()
