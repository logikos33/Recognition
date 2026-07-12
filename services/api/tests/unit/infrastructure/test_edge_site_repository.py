"""
Tests: EdgeSiteRepository — sites, enrollment tokens, devices, fleet counts.

All DB calls go through a mocked DatabasePool (contextmanager pattern).
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.infrastructure.database.repositories.edge_site_repository import (
    EdgeSiteRepository,
)


def _pool_with_cursor(mock_cursor):
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


def _repo(mock_cursor=None):
    cur = mock_cursor or MagicMock()
    return EdgeSiteRepository(_pool_with_cursor(cur)), cur


# ---------------------------------------------------------------------------
# create_site
# ---------------------------------------------------------------------------

class TestCreateSite:

    def test_returns_created_row(self):
        row = {"id": "site-1", "name": "Main", "tenant_id": "t-1"}
        cur = MagicMock()
        cur.fetchone.return_value = row
        repo, _ = _repo(cur)
        result = repo.create_site("t-1", "Main", "Location A", "cloud")
        assert result["name"] == "Main"

    def test_tenant_and_name_in_params(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create_site("tenant-7", "My Site", None, "edge", "user-1")
        params = cur.execute.call_args[0][1]
        assert "tenant-7" in params
        assert "My Site" in params
        assert "user-1" in params


# ---------------------------------------------------------------------------
# list_sites
# ---------------------------------------------------------------------------

class TestListSites:

    def test_returns_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "s1"}, {"id": "s2"}]
        repo, _ = _repo(cur)
        result = repo.list_sites("t-1")
        assert len(result) == 2

    def test_tenant_id_in_params(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_sites("tenant-abc")
        assert "tenant-abc" in cur.execute.call_args[0][1]


# ---------------------------------------------------------------------------
# get_site_by_id
# ---------------------------------------------------------------------------

class TestGetSiteById:

    def test_returns_row_when_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "s1", "tenant_id": "t-1"}
        repo, _ = _repo(cur)
        result = repo.get_site_by_id("s1", "t-1")
        assert result["id"] == "s1"

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.get_site_by_id("bad", "t-1") is None

    def test_both_ids_in_params(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.get_site_by_id("site-99", "tenant-99")
        params = cur.execute.call_args[0][1]
        assert "site-99" in params
        assert "tenant-99" in params


# ---------------------------------------------------------------------------
# get_site_detail
# ---------------------------------------------------------------------------

class TestGetSiteDetail:

    def test_returns_row_with_device_count(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "s1", "device_count": 3}
        repo, _ = _repo(cur)
        result = repo.get_site_detail("s1", "t-1")
        assert result["device_count"] == 3

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.get_site_detail("bad", "t-1") is None


# ---------------------------------------------------------------------------
# update_site
# ---------------------------------------------------------------------------

class TestUpdateSite:

    def test_empty_updates_calls_get_site_by_id(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "s1", "name": "Old"}
        repo, _ = _repo(cur)
        result = repo.update_site("s1", "t-1", {})
        assert result is not None

    def test_ignores_non_updatable_fields(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "s1"}
        repo, cur = _repo(cur)
        repo.update_site("s1", "t-1", {"tenant_id": "evil", "name": "Safe"})
        query = cur.execute.call_args[0][0]
        # tenant_id must NOT appear in the SET clause (only allowed in WHERE/RETURNING)
        set_part = query.split("WHERE")[0]
        assert "tenant_id" not in set_part
        assert "name" in set_part

    def test_valid_fields_produce_set_clause(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "s1"}
        repo, cur = _repo(cur)
        repo.update_site("s1", "t-1", {"name": "New Name", "status": "active"})
        query = cur.execute.call_args[0][0]
        assert "SET" in query.upper()
        assert "name" in query
        assert "status" in query

    def test_site_id_and_tenant_in_params(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "s1"}
        repo, cur = _repo(cur)
        repo.update_site("site-7", "tenant-7", {"name": "X"})
        params = cur.execute.call_args[0][1]
        assert "site-7" in params
        assert "tenant-7" in params


# ---------------------------------------------------------------------------
# create_enrollment_token
# ---------------------------------------------------------------------------

class TestCreateEnrollmentToken:

    def test_returns_token_row(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "tok-1", "expires_at": datetime.now()}
        repo, _ = _repo(cur)
        result = repo.create_enrollment_token(
            "s-1", "t-1", "hash123", datetime.now(tz=timezone.utc)
        )
        assert result["id"] == "tok-1"

    def test_token_hash_in_params(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "x"}
        repo, cur = _repo(cur)
        repo.create_enrollment_token("s", "t", "myhash", datetime.now(tz=timezone.utc))
        params = cur.execute.call_args[0][1]
        assert "myhash" in params


# ---------------------------------------------------------------------------
# list_enrollment_tokens / get_enrollment_token_by_id
# ---------------------------------------------------------------------------

class TestListEnrollmentTokens:

    def test_returns_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": "t1"}]
        repo, _ = _repo(cur)
        result = repo.list_enrollment_tokens("tenant-1", "site-1")
        assert len(result) == 1

    def test_no_token_hash_in_query(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_enrollment_tokens("t", "s")
        query = cur.execute.call_args[0][0]
        assert "token_hash" not in query


class TestGetEnrollmentTokenById:

    def test_returns_row(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "tok-99"}
        repo, _ = _repo(cur)
        assert repo.get_enrollment_token_by_id("tok-99", "t-1")["id"] == "tok-99"

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.get_enrollment_token_by_id("bad", "t-1") is None


# ---------------------------------------------------------------------------
# revoke_enrollment_token_if_unused
# ---------------------------------------------------------------------------

class TestRevokeEnrollmentToken:

    def test_returns_row_when_revoked(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "tok-1", "used_at": None}
        repo, _ = _repo(cur)
        result = repo.revoke_enrollment_token_if_unused("tok-1", "t-1")
        assert result is not None

    def test_returns_none_when_already_used(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.revoke_enrollment_token_if_unused("tok-1", "t-1") is None


# ---------------------------------------------------------------------------
# enroll_device (transaction)
# ---------------------------------------------------------------------------

class TestEnrollDevice:

    def _build_txn_repo(self, token_row, device_row):
        """Repo whose _execute_in_transaction calls fn with mocked conn/cur."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [token_row, device_row]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        pool = MagicMock()
        @contextmanager
        def _ctx():
            mock_conn.autocommit = True
            yield mock_conn
        pool.get_connection.side_effect = _ctx
        return EdgeSiteRepository(pool), mock_cursor

    def test_raises_value_error_when_token_invalid(self):
        repo, _ = self._build_txn_repo(None, None)
        with pytest.raises(ValueError, match="enrollment_token_invalid"):
            repo.enroll_device("bad-hash", "dev-1", "Dev", "pem", "fp")

    def test_success_returns_device_row(self):
        token_row = {"tenant_id": "t-1", "site_id": "s-1"}
        device_row = {"id": "dev-pk", "device_id": "dev-1", "enrolled_at": None}
        repo, _ = self._build_txn_repo(token_row, device_row)
        result = repo.enroll_device("valid-hash", "dev-1", "My Device", "pem", "fp")
        assert result["device_id"] == "dev-1"


# ---------------------------------------------------------------------------
# Fleet overview
# ---------------------------------------------------------------------------

class TestGetSiteStatusCounts:

    def test_returns_list(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"status": "active", "count": 3}]
        repo, _ = _repo(cur)
        result = repo.get_site_status_counts("t-1")
        assert result[0]["count"] == 3


class TestGetDeviceFleetCounts:

    def test_returns_counts_dict(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"total": 10, "online": 7, "revoked": 1}
        repo, _ = _repo(cur)
        result = repo.get_device_fleet_counts("t-1", 60)
        assert result["total"] == 10
        assert result["online"] == 7

    def test_no_row_returns_zeros(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        result = repo.get_device_fleet_counts("t-1", 60)
        assert result == {"total": 0, "online": 0, "revoked": 0}

    def test_threshold_in_params(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"total": 0, "online": 0, "revoked": 0}
        repo, cur = _repo(cur)
        repo.get_device_fleet_counts("t-1", 300)
        params = cur.execute.call_args[0][1]
        assert 300 in params


# ---------------------------------------------------------------------------
# Device management
# ---------------------------------------------------------------------------

class TestListDevices:

    def test_returns_devices(self):
        cur = MagicMock()
        cur.fetchall.return_value = [{"device_id": "d1"}]
        repo, _ = _repo(cur)
        assert repo.list_devices("t-1", "s-1")[0]["device_id"] == "d1"

    def test_no_public_key_in_query(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_devices("t", "s")
        query = cur.execute.call_args[0][0]
        assert "public_key_pem" not in query


class TestRevokeDevice:

    def test_returns_row_on_success(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": "pk-1", "revoked": True}
        repo, _ = _repo(cur)
        result = repo.revoke_device("pk-1", "t-1", "admin-1")
        assert result["revoked"] is True

    def test_returns_none_when_not_found(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, _ = _repo(cur)
        assert repo.revoke_device("bad", "t-1", "admin") is None

    def test_tenant_id_in_params(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.revoke_device("pk", "tenant-x", "admin")
        params = cur.execute.call_args[0][1]
        assert "tenant-x" in params
