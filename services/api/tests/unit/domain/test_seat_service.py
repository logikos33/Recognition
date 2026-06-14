"""Testes unitários — seat_service (enforcement de assentos por tenant)."""
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import ConflictError
from app.domain.services.seat_service import check_seat_available

TENANT = "11111111-1111-1111-1111-111111111111"


def _make_repo(max_seats, single_session=False, active_users=0):
    repo = MagicMock()
    repo.get_seat_policy.return_value = {
        "max_seats": max_seats,
        "single_session": single_session,
    }
    repo.count_active_users.return_value = active_users
    return repo


class TestCheckSeatAvailable:
    def test_unlimited_when_max_seats_null(self):
        repo = _make_repo(max_seats=None, active_users=999)
        result = check_seat_available(repo, TENANT)
        assert result == {"used": 999, "max": None}

    def test_allows_when_under_limit(self):
        repo = _make_repo(max_seats=5, active_users=4)
        result = check_seat_available(repo, TENANT)
        assert result == {"used": 4, "max": 5}

    def test_blocks_when_at_limit(self):
        repo = _make_repo(max_seats=5, active_users=5)
        with pytest.raises(ConflictError) as exc:
            check_seat_available(repo, TENANT)
        assert "5/5" in exc.value.message
        assert exc.value.status_code == 409

    def test_blocks_when_over_limit(self):
        repo = _make_repo(max_seats=3, active_users=7)
        with pytest.raises(ConflictError):
            check_seat_available(repo, TENANT)

    def test_zero_seats_blocks_first_user(self):
        repo = _make_repo(max_seats=0, active_users=0)
        with pytest.raises(ConflictError):
            check_seat_available(repo, TENANT)

    def test_queries_repo_with_tenant_id(self):
        repo = _make_repo(max_seats=10, active_users=1)
        check_seat_available(repo, TENANT)
        repo.get_seat_policy.assert_called_once_with(TENANT)
        repo.count_active_users.assert_called_once_with(TENANT)
