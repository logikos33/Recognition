"""
Tests: domain/services/search_cloud_guard.py — guard fail-closed de datas
pra busca por conteúdo (SEARCH_CLOUD_ALLOWED_DATES).

Cobre:
- parse_allowed_dates: data única, intervalo, combinação, malformado
  (None fail-closed — nunca "ignora e libera o resto").
- cloud_search_allowed_dates: env ausente/vazia/malformada → None
  (busca em nuvem desabilitada); env válida → intervalos parseados.
- classify_frame_eligibility / classify_selected_frames: frame não
  encontrado (ou de outro tenant — C-01, indistinguível), sem r2_key, sem
  captured_at, data fora da janela — cada motivo isolado; frame elegível
  não aparece na lista.
"""
from __future__ import annotations

from datetime import date, datetime

from app.domain.services.search_cloud_guard import (
    classify_frame_eligibility,
    classify_selected_frames,
    cloud_search_allowed_dates,
    is_date_allowed,
    parse_allowed_dates,
)


class TestParseAllowedDates:
    def test_single_date(self) -> None:
        assert parse_allowed_dates("2026-07-31") == [(date(2026, 7, 31), date(2026, 7, 31))]

    def test_range(self) -> None:
        assert parse_allowed_dates("2026-08-01..2026-08-05") == [
            (date(2026, 8, 1), date(2026, 8, 5)),
        ]

    def test_combination_of_single_and_range(self) -> None:
        result = parse_allowed_dates("2026-07-31,2026-08-01..2026-08-05")
        assert result == [
            (date(2026, 7, 31), date(2026, 7, 31)),
            (date(2026, 8, 1), date(2026, 8, 5)),
        ]

    def test_whitespace_around_entries_is_tolerated(self) -> None:
        result = parse_allowed_dates(" 2026-07-31 , 2026-08-01 .. 2026-08-05 ")
        assert result == [
            (date(2026, 7, 31), date(2026, 7, 31)),
            (date(2026, 8, 1), date(2026, 8, 5)),
        ]

    def test_none_returns_none(self) -> None:
        assert parse_allowed_dates(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_allowed_dates("") is None
        assert parse_allowed_dates("   ") is None

    def test_malformed_single_date_returns_none_fail_closed(self) -> None:
        """Uma entrada ruim invalida a env INTEIRA — nunca ignora a ruim e
        libera as boas (fail-closed)."""
        assert parse_allowed_dates("2026-07-31,not-a-date") is None

    def test_malformed_range_returns_none(self) -> None:
        assert parse_allowed_dates("2026-08-05..not-a-date") is None

    def test_inverted_range_returns_none(self) -> None:
        assert parse_allowed_dates("2026-08-05..2026-08-01") is None

    def test_only_commas_returns_none(self) -> None:
        assert parse_allowed_dates(",,,") is None


class TestCloudSearchAllowedDates:
    def test_env_absent_returns_none(self, monkeypatch) -> None:
        monkeypatch.delenv("SEARCH_CLOUD_ALLOWED_DATES", raising=False)
        assert cloud_search_allowed_dates() is None

    def test_env_empty_returns_none(self, monkeypatch) -> None:
        monkeypatch.setenv("SEARCH_CLOUD_ALLOWED_DATES", "")
        assert cloud_search_allowed_dates() is None

    def test_env_malformed_returns_none(self, monkeypatch) -> None:
        monkeypatch.setenv("SEARCH_CLOUD_ALLOWED_DATES", "garbage")
        assert cloud_search_allowed_dates() is None

    def test_env_valid_returns_ranges(self, monkeypatch) -> None:
        monkeypatch.setenv("SEARCH_CLOUD_ALLOWED_DATES", "2026-07-31")
        assert cloud_search_allowed_dates() == [(date(2026, 7, 31), date(2026, 7, 31))]


class TestIsDateAllowed:
    def test_inside_range(self) -> None:
        ranges = [(date(2026, 8, 1), date(2026, 8, 5))]
        assert is_date_allowed(date(2026, 8, 3), ranges) is True

    def test_outside_range(self) -> None:
        ranges = [(date(2026, 8, 1), date(2026, 8, 5))]
        assert is_date_allowed(date(2026, 8, 6), ranges) is False

    def test_boundary_dates_are_inclusive(self) -> None:
        ranges = [(date(2026, 8, 1), date(2026, 8, 5))]
        assert is_date_allowed(date(2026, 8, 1), ranges) is True
        assert is_date_allowed(date(2026, 8, 5), ranges) is True


_ALLOWED = [(date(2026, 7, 31), date(2026, 7, 31))]


class TestClassifyFrameEligibility:
    def test_none_frame_is_not_found(self) -> None:
        assert classify_frame_eligibility(None, _ALLOWED) == "frame_not_found"

    def test_missing_r2_key(self) -> None:
        frame = {"r2_key": None, "captured_at": datetime(2026, 7, 31, 10, 0)}
        assert classify_frame_eligibility(frame, _ALLOWED) == "missing_r2_key"

    def test_missing_captured_at(self) -> None:
        frame = {"r2_key": "frames/f1.jpg", "captured_at": None}
        assert classify_frame_eligibility(frame, _ALLOWED) == "missing_captured_at"

    def test_date_not_allowed(self) -> None:
        frame = {"r2_key": "frames/f1.jpg", "captured_at": datetime(2026, 8, 1, 10, 0)}
        assert classify_frame_eligibility(frame, _ALLOWED) == "date_not_allowed"

    def test_eligible_frame_returns_none(self) -> None:
        frame = {"r2_key": "frames/f1.jpg", "captured_at": datetime(2026, 7, 31, 23, 59)}
        assert classify_frame_eligibility(frame, _ALLOWED) is None

    def test_date_type_captured_at_also_accepted(self) -> None:
        frame = {"r2_key": "frames/f1.jpg", "captured_at": date(2026, 7, 31)}
        assert classify_frame_eligibility(frame, _ALLOWED) is None


class TestClassifySelectedFrames:
    def test_mixed_selection_returns_only_ineligible(self) -> None:
        frames_by_id = {
            "f1": {"r2_key": "frames/f1.jpg", "captured_at": datetime(2026, 7, 31, 10, 0)},
            "f2": {"r2_key": None, "captured_at": datetime(2026, 7, 31, 10, 0)},
        }
        ineligible = classify_selected_frames(["f1", "f2", "f3"], frames_by_id, _ALLOWED)
        reasons = {item.frame_id: item.reason for item in ineligible}
        assert reasons == {"f2": "missing_r2_key", "f3": "frame_not_found"}

    def test_cross_tenant_frame_indistinguishable_from_missing(self) -> None:
        """C-01: um frame_id que existe mas pertence a outro tenant nunca
        aparece em `frames_by_id` (o caller já filtrou por tenant na query
        SQL) — chega aqui como `frame_not_found`, idêntico a um id
        inexistente. Nunca vaza a diferença."""
        ineligible = classify_selected_frames(["outro-tenant-frame"], {}, _ALLOWED)
        assert len(ineligible) == 1
        assert ineligible[0].reason == "frame_not_found"

    def test_all_eligible_returns_empty_list(self) -> None:
        frames_by_id = {
            "f1": {"r2_key": "frames/f1.jpg", "captured_at": datetime(2026, 7, 31, 10, 0)},
        }
        assert classify_selected_frames(["f1"], frames_by_id, _ALLOWED) == []
