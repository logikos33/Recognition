"""
Tests for task-040: liveness time-gate enforcement (real Postgres + real Redis).

Eval cases (spec):
  1. Sustained gap (elapsed > LIVENESS_GAP_THRESHOLD_MINUTES) → real `camera_gap`
     alert row created in `alerts` (Postgres real — NOT a mocked repository).
  2. Momentary gap (elapsed < threshold) → NO alert row is ever created.
  3. Recovery after a sustained gap → alert acknowledged in the DB AND the
     Redis gap timer is cleared, so a subsequent gap restarts the clock from
     zero instead of re-alerting immediately off a stale timestamp.

Uses pg_pool/pg_raw/tenant_id fixtures from tests/integration/conftest.py
(Postgres real, C-04, PR #25 pattern — see test_edge_fleet_overview.py
(task-016) for the seed/cleanup style this file follows).

Time is controlled by monkeypatching `liveness_service.time.time` (no real
sleeping needed) — the Redis gap-timer key stores whatever `time.time()`
returned at the moment it was created, so moving the fake clock forward
deterministically simulates elapsed time.

A REAL Redis client (REDIS_URL) is used — this is exactly the cross-process
gap timer task-040 requires (heartbeats from the on-prem worker land on
different gunicorn worker processes, so the timer cannot live in local
process memory; see liveness_service.py module docstring).

NOTE: these tests are skipped automatically when INTEGRATION_DATABASE_URL /
HARNESS_DATABASE_URL is not set (repo-wide integration test convention — see
conftest.py `integration_dsn` fixture). This is expected/by-design, not a
failure: the regular CI job does not set that variable today, so this file
shows up as "skipped" there. Run locally against a real, migrated Postgres
with:

    export INTEGRATION_DATABASE_URL=postgresql://test:test@127.0.0.1:5432/recognition_test_040
    export REDIS_URL=redis://127.0.0.1:6379
    pytest services/api/tests/integration/ -v -k liveness
"""
from __future__ import annotations

import os
from uuid import uuid4

import redis as redis_lib

from app.domain.services import liveness_service
from app.domain.services.liveness_service import _gap_timer_key, check_camera_liveness

_REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379")


# ---------------------------------------------------------------------------
# Helpers de seed / cleanup
# ---------------------------------------------------------------------------

def _redis_client():
    return redis_lib.from_url(_REDIS_URL, socket_timeout=2, decode_responses=True)


def _insert_user(cur, tenant_id: str) -> str:
    user_id = str(uuid4())
    cur.execute(
        "INSERT INTO users (id, email, password_hash, name, tenant_id) "
        "VALUES (%s, %s, 'x', 'Liveness Test User', %s)",
        (user_id, f"liveness-{user_id[:8]}@inttest.dev", tenant_id),
    )
    return user_id


def _insert_camera(cur, tenant_id: str, user_id: str) -> str:
    camera_id = str(uuid4())
    cur.execute(
        "INSERT INTO cameras (id, tenant_id, user_id, name, host, port, is_active) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (camera_id, tenant_id, user_id, "Cam Liveness Gate", "192.168.50.10", 554, True),
    )
    return camera_id


def _count_gap_alerts(pg_raw, tenant_id: str, evidence_key: str, *, open_only: bool) -> int:
    with pg_raw.cursor() as cur:
        if open_only:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM alerts "
                "WHERE tenant_id = %s AND evidence_key = %s "
                "AND acknowledged = FALSE AND violations::text LIKE %s",
                (tenant_id, evidence_key, "%camera_gap%"),
            )
        else:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM alerts "
                "WHERE tenant_id = %s AND evidence_key = %s AND violations::text LIKE %s",
                (tenant_id, evidence_key, "%camera_gap%"),
            )
        return int(cur.fetchone()["cnt"])


def _cleanup(pg_raw, tenant_id: str, user_id: str | None, redis_client, gap_key: str) -> None:
    """Explicit cleanup — does not rely on ON DELETE CASCADE assumptions.

    Must run BEFORE the `tenant_id` fixture's own teardown (`DELETE FROM
    tenants`), or that DELETE fails with a FK violation (alerts/cameras/users
    still referencing the tenant).
    """
    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM alerts WHERE tenant_id = %s", (tenant_id,))
        cur.execute("DELETE FROM cameras WHERE tenant_id = %s", (tenant_id,))
        if user_id:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    redis_client.delete(gap_key)
    redis_client.close()


# ---------------------------------------------------------------------------
# Integration tests: Postgres REAL + Redis REAL — NÃO mockar
# ---------------------------------------------------------------------------

class TestLivenessTimeGateRealInfra:
    """Validates the actual N-minute enforcement end-to-end, no mocks."""

    def test_momentary_gap_does_not_create_alert(self, pg_pool, pg_raw, tenant_id, monkeypatch):
        """A gap that never persists past the threshold must NEVER create an
        `alerts` row — this is the noise-suppression task-040 requires."""
        monkeypatch.setattr(liveness_service, "LIVENESS_GAP_THRESHOLD_MINUTES", 5)
        site_id = f"site-momentary-{uuid4().hex[:8]}"
        evidence_key = f"heartbeat/{site_id}"
        r = _redis_client()
        gap_key = _gap_timer_key(tenant_id, site_id)
        user_id = None

        fake_now = [1_800_000_000.0]
        monkeypatch.setattr(liveness_service.time, "time", lambda: fake_now[0])

        try:
            with pg_raw.cursor() as cur:
                user_id = _insert_user(cur, tenant_id)
                _insert_camera(cur, tenant_id, user_id)

            # First heartbeat observing a gap — starts the timer, no alert yet.
            check_camera_liveness(tenant_id, site_id, 1, 2, pg_pool, redis_client=r)
            assert _count_gap_alerts(pg_raw, tenant_id, evidence_key, open_only=False) == 0

            # +10s later — still far below the 5-minute (300s) threshold.
            fake_now[0] += 10
            check_camera_liveness(tenant_id, site_id, 1, 2, pg_pool, redis_client=r)
            assert _count_gap_alerts(pg_raw, tenant_id, evidence_key, open_only=False) == 0

            # Recovers before the threshold elapses — still no alert, ever.
            check_camera_liveness(tenant_id, site_id, 2, 2, pg_pool, redis_client=r)
            assert _count_gap_alerts(pg_raw, tenant_id, evidence_key, open_only=False) == 0
        finally:
            _cleanup(pg_raw, tenant_id, user_id, r, gap_key)

    def test_sustained_gap_creates_alert_recovery_acknowledges_and_resets_timer(
        self, pg_pool, pg_raw, tenant_id, monkeypatch
    ):
        """Sustained gap (> threshold) → real `alerts` row created. Recovery →
        row acknowledged AND Redis timer cleared (proven by a fresh gap right
        after recovery, at the SAME instant, which must NOT re-alert off a
        stale timestamp)."""
        monkeypatch.setattr(liveness_service, "LIVENESS_GAP_THRESHOLD_MINUTES", 1)  # 60s
        site_id = f"site-sustained-{uuid4().hex[:8]}"
        evidence_key = f"heartbeat/{site_id}"
        r = _redis_client()
        gap_key = _gap_timer_key(tenant_id, site_id)
        user_id = None

        fake_now = [1_800_000_000.0]
        monkeypatch.setattr(liveness_service.time, "time", lambda: fake_now[0])

        try:
            with pg_raw.cursor() as cur:
                user_id = _insert_user(cur, tenant_id)
                _insert_camera(cur, tenant_id, user_id)

            # t=0: gap observed for the first time — timer starts, no alert yet.
            check_camera_liveness(tenant_id, site_id, 1, 2, pg_pool, redis_client=r)
            assert _count_gap_alerts(pg_raw, tenant_id, evidence_key, open_only=False) == 0

            # t=+30s: still gapped, still under the 60s threshold.
            fake_now[0] += 30
            check_camera_liveness(tenant_id, site_id, 1, 2, pg_pool, redis_client=r)
            assert _count_gap_alerts(pg_raw, tenant_id, evidence_key, open_only=False) == 0

            # t=+71s total: gap has now persisted past the threshold → real row.
            fake_now[0] += 41
            check_camera_liveness(tenant_id, site_id, 1, 2, pg_pool, redis_client=r)
            assert _count_gap_alerts(pg_raw, tenant_id, evidence_key, open_only=True) == 1

            # Idempotency: another gapped heartbeat does not duplicate the alert.
            fake_now[0] += 10
            check_camera_liveness(tenant_id, site_id, 1, 2, pg_pool, redis_client=r)
            assert _count_gap_alerts(pg_raw, tenant_id, evidence_key, open_only=False) == 1

            # Recovery: cameras back to full count → alert acknowledged, timer cleared.
            check_camera_liveness(tenant_id, site_id, 2, 2, pg_pool, redis_client=r)
            assert _count_gap_alerts(pg_raw, tenant_id, evidence_key, open_only=True) == 0
            assert r.get(gap_key) is None, "gap timer must be cleared from Redis on recovery"

            # A brand-new gap right after recovery, at the SAME fake instant (no
            # time advance). If the reset above hadn't really happened, the old
            # gap_since timestamp would still be > threshold and this would
            # immediately re-alert. It must not — the clock must restart at zero.
            check_camera_liveness(tenant_id, site_id, 1, 2, pg_pool, redis_client=r)
            assert _count_gap_alerts(pg_raw, tenant_id, evidence_key, open_only=True) == 0
        finally:
            _cleanup(pg_raw, tenant_id, user_id, r, gap_key)
