"""
Tests: liveness_service — per-camera liveness monitoring via heartbeat.

Coverage:
  - gap detected (past the time gate) → alert created
  - no gap → no alert, existing alerts acknowledged
  - recovery → gap alerts acknowledged
  - tenant isolation → each tenant scoped independently
  - best-effort → exception inside service never propagates
  - idempotency → duplicate alerts are not created when one is already open
  - skip → cameras_total=0 means nothing to monitor
  - no anchor camera → alert creation is skipped gracefully
  - time gate → gap alert only created once the Redis-tracked "first seen"
    timestamp is older than LIVENESS_GAP_THRESHOLD_MINUTES; a momentary gap
    (timer just started) never reaches the repository; recovery clears the
    timer; Redis errors are swallowed (best-effort) on both paths.

All tests below inject a fake in-memory Redis double via the redis_client
DI parameter — no real Redis/Postgres involved (see tests/integration/
test_liveness_time_gate.py for the real-infra coverage, per repo convention
that unit tests mock all infra and integration tests hit it for real).
"""
import time
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.domain.services.liveness_service import _gap_timer_key, check_camera_liveness

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

TENANT_A = str(uuid4())
TENANT_B = str(uuid4())
SITE_A = "schema_a"
SITE_B = "schema_b"
CAMERA_A = str(uuid4())


class _FakeRedis:
    """Minimal in-memory double for the SET NX / GET / DELETE gap-timer flow."""

    def __init__(self, seed: dict | None = None) -> None:
        self.store: dict[str, str] = dict(seed or {})
        self.closed = False

    def set(self, key, value, nx=False, ex=None):  # noqa: ARG002 (ex unused in fake)
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def delete(self, key):
        self.store.pop(key, None)

    def exists(self, key):
        return 1 if key in self.store else 0

    def close(self):
        self.closed = True


def _elapsed_redis(tenant_id: str, site_id: str, minutes_ago: float = 10.0) -> _FakeRedis:
    """FakeRedis pre-seeded so the gap timer already exceeds the default threshold.

    Used as the default for tests that exercise alert-creation/idempotency/
    tenant-scoping logic — orthogonal to the time-gate itself (covered
    separately in TestLivenessTimeGate below).
    """
    key = _gap_timer_key(tenant_id, site_id)
    seeded_ts = time.time() - (minutes_ago * 60)
    return _FakeRedis(seed={key: str(seeded_ts)})


def _make_repo(
    *,
    open_alert: dict | None = None,
    camera_id: str | None = CAMERA_A,
    created_alert: dict | None = None,
    ack_count: int = 0,
) -> MagicMock:
    """Build a mock LivenessAlertRepository with sensible defaults."""
    repo = MagicMock()
    repo.get_open_gap_alert.return_value = open_alert
    repo.find_camera_for_tenant.return_value = camera_id
    repo.create_gap_alert.return_value = created_alert or {"id": str(uuid4())}
    repo.acknowledge_gap_alerts.return_value = ack_count
    return repo


def _run(
    tenant_id: str,
    site_id: str,
    cameras_online: int,
    cameras_total: int,
    repo: MagicMock,
    redis_client: _FakeRedis | MagicMock | None = None,
) -> None:
    """Run check_camera_liveness with a patched LivenessAlertRepository.

    Defaults to a FakeRedis whose gap timer already exceeds the threshold,
    so callers not testing the time gate itself keep the pre-existing
    "immediate alert" semantics.
    """
    pool = MagicMock()
    if redis_client is None:
        redis_client = _elapsed_redis(tenant_id, site_id)
    patch_target = "app.domain.services.liveness_service.LivenessAlertRepository"
    with patch(patch_target, return_value=repo):
        check_camera_liveness(
            tenant_id, site_id, cameras_online, cameras_total, pool, redis_client=redis_client
        )


# ---------------------------------------------------------------------------
# Core behaviour
# ---------------------------------------------------------------------------


class TestLivenessGap:
    """Behaviour when cameras_online < cameras_total (gate already elapsed)."""

    def test_liveness_gap_creates_alert(self) -> None:
        """cameras_online=1, cameras_total=3, gap past threshold → alert created."""
        repo = _make_repo(open_alert=None)
        _run(TENANT_A, SITE_A, cameras_online=1, cameras_total=3, repo=repo)

        repo.get_open_gap_alert.assert_called_once_with(TENANT_A, f"heartbeat/{SITE_A}")
        repo.find_camera_for_tenant.assert_called_once_with(TENANT_A)
        repo.create_gap_alert.assert_called_once()

        call = repo.create_gap_alert.call_args
        assert call.kwargs["cameras_online"] == 1
        assert call.kwargs["cameras_total"] == 3
        assert call.kwargs["tenant_id"] == TENANT_A
        assert call.kwargs["evidence_key"] == f"heartbeat/{SITE_A}"

    def test_liveness_gap_idempotent_no_duplicate_alerts(self) -> None:
        """If an open gap alert already exists, no new alert is created."""
        existing_alert = {"id": str(uuid4()), "acknowledged": False}
        repo = _make_repo(open_alert=existing_alert)
        _run(TENANT_A, SITE_A, cameras_online=2, cameras_total=4, repo=repo)

        repo.create_gap_alert.assert_not_called()
        repo.acknowledge_gap_alerts.assert_not_called()

    def test_liveness_gap_no_anchor_camera_skips_create(self) -> None:
        """If tenant has no active camera, alert creation is skipped gracefully."""
        repo = _make_repo(open_alert=None, camera_id=None)
        _run(TENANT_A, SITE_A, cameras_online=0, cameras_total=3, repo=repo)

        repo.create_gap_alert.assert_not_called()


class TestLivenessRecovery:
    """Behaviour when cameras_online >= cameras_total (full recovery)."""

    def test_liveness_no_gap_no_alert_created(self) -> None:
        """All cameras online → no gap alert is created."""
        repo = _make_repo()
        _run(TENANT_A, SITE_A, cameras_online=3, cameras_total=3, repo=repo)

        repo.create_gap_alert.assert_not_called()

    def test_liveness_recovery_acknowledges_open_alerts(self) -> None:
        """Recovery (full cameras back) → acknowledge open camera_gap alerts."""
        repo = _make_repo(ack_count=1)
        _run(TENANT_A, SITE_A, cameras_online=3, cameras_total=3, repo=repo)

        repo.acknowledge_gap_alerts.assert_called_once_with(
            TENANT_A, f"heartbeat/{SITE_A}"
        )

    def test_liveness_recovery_with_no_open_alerts_is_noop(self) -> None:
        """Recovery when no alerts are open → acknowledge_gap_alerts still called."""
        repo = _make_repo(ack_count=0)
        _run(TENANT_A, SITE_A, cameras_online=5, cameras_total=5, repo=repo)

        repo.acknowledge_gap_alerts.assert_called_once()
        repo.create_gap_alert.assert_not_called()


class TestLivenessTenantScoped:
    """Tenant isolation: tenant A's liveness check must not affect tenant B."""

    def test_liveness_tenant_scoped_gap_uses_correct_tenant_id(self) -> None:
        """Gap alert for TENANT_A passes TENANT_A's ID, not TENANT_B's."""
        repo_a = _make_repo(open_alert=None)
        _run(TENANT_A, SITE_A, cameras_online=1, cameras_total=3, repo=repo_a)

        call_a = repo_a.create_gap_alert.call_args
        assert call_a.kwargs["tenant_id"] == TENANT_A

    def test_liveness_tenant_b_independent_from_tenant_a(self) -> None:
        """Two separate calls for different tenants produce independent alerts."""
        repo_a = _make_repo(open_alert=None)
        repo_b = _make_repo(open_alert=None)

        pool = MagicMock()
        patch_target = "app.domain.services.liveness_service.LivenessAlertRepository"

        # TENANT_A call
        with patch(patch_target, return_value=repo_a):
            check_camera_liveness(
                TENANT_A, SITE_A, 1, 3, pool,
                redis_client=_elapsed_redis(TENANT_A, SITE_A),
            )

        # TENANT_B call — separate repo instance and separate timer
        with patch(patch_target, return_value=repo_b):
            check_camera_liveness(
                TENANT_B, SITE_B, 2, 4, pool,
                redis_client=_elapsed_redis(TENANT_B, SITE_B),
            )

        call_a = repo_a.create_gap_alert.call_args
        call_b = repo_b.create_gap_alert.call_args

        assert call_a.kwargs["tenant_id"] == TENANT_A
        assert call_b.kwargs["tenant_id"] == TENANT_B
        assert call_a.kwargs["tenant_id"] != call_b.kwargs["tenant_id"]

        # evidence_keys are also separate
        assert call_a.kwargs["evidence_key"] == f"heartbeat/{SITE_A}"
        assert call_b.kwargs["evidence_key"] == f"heartbeat/{SITE_B}"


class TestLivenessBestEffort:
    """check_camera_liveness() must never propagate exceptions to callers."""

    def test_liveness_best_effort_no_crash_on_repo_error(self) -> None:
        """Exception raised inside repo does not propagate."""
        repo = MagicMock()
        repo.get_open_gap_alert.side_effect = RuntimeError("DB is down")
        pool = MagicMock()

        # Must not raise
        patch_target = "app.domain.services.liveness_service.LivenessAlertRepository"
        with patch(patch_target, return_value=repo):
            check_camera_liveness(
                TENANT_A, SITE_A, 1, 3, pool,
                redis_client=_elapsed_redis(TENANT_A, SITE_A),
            )

    def test_liveness_best_effort_no_crash_on_create_error(self) -> None:
        """Exception during alert creation does not propagate."""
        repo = _make_repo(open_alert=None)
        repo.create_gap_alert.side_effect = ConnectionError("timeout")
        pool = MagicMock()

        patch_target = "app.domain.services.liveness_service.LivenessAlertRepository"
        with patch(patch_target, return_value=repo):
            check_camera_liveness(
                TENANT_A, SITE_A, 0, 5, pool,
                redis_client=_elapsed_redis(TENANT_A, SITE_A),
            )

    def test_liveness_best_effort_no_crash_on_ack_error(self) -> None:
        """Exception during acknowledgement does not propagate."""
        repo = _make_repo()
        repo.acknowledge_gap_alerts.side_effect = OSError("socket error")
        pool = MagicMock()

        patch_target = "app.domain.services.liveness_service.LivenessAlertRepository"
        with patch(patch_target, return_value=repo):
            check_camera_liveness(TENANT_A, SITE_A, 3, 3, pool, redis_client=_FakeRedis())


class TestLivenessEdgeCases:
    """Edge cases and guard clauses."""

    def test_liveness_cameras_total_zero_skips(self) -> None:
        """cameras_total=0 → nothing to monitor, no DB calls at all."""
        repo = _make_repo()
        _run(TENANT_A, SITE_A, cameras_online=0, cameras_total=0, repo=repo)

        repo.get_open_gap_alert.assert_not_called()
        repo.create_gap_alert.assert_not_called()
        repo.acknowledge_gap_alerts.assert_not_called()

    def test_liveness_cameras_total_negative_skips(self) -> None:
        """cameras_total<0 → guard clause skips all processing."""
        repo = _make_repo()
        _run(TENANT_A, SITE_A, cameras_online=0, cameras_total=-1, repo=repo)

        repo.create_gap_alert.assert_not_called()

    def test_liveness_evidence_key_format(self) -> None:
        """evidence_key is always 'heartbeat/{site_id}'."""
        repo = _make_repo(open_alert=None)
        _run(TENANT_A, "my-schema", cameras_online=1, cameras_total=3, repo=repo)

        repo.get_open_gap_alert.assert_called_once_with(TENANT_A, "heartbeat/my-schema")
        call = repo.create_gap_alert.call_args
        assert call.kwargs["evidence_key"] == "heartbeat/my-schema"


class TestLivenessTimeGate:
    """The N-minute time gate itself: enforcement, momentary-gap noise
    suppression, timer reset on recovery, and Redis-failure best-effort.
    """

    def test_liveness_gap_within_grace_period_does_not_create_alert(self) -> None:
        """First-ever gap observation starts the timer but never touches the
        repository — a momentary blip must not create noise."""
        repo = _make_repo(open_alert=None)
        fresh_redis = _FakeRedis()  # no prior timer
        _run(TENANT_A, SITE_A, cameras_online=1, cameras_total=3, repo=repo, redis_client=fresh_redis)

        repo.get_open_gap_alert.assert_not_called()
        repo.create_gap_alert.assert_not_called()

    def test_liveness_gap_timer_starts_on_first_observation(self) -> None:
        """The first gap observation writes a gap_since timestamp to Redis."""
        repo = _make_repo(open_alert=None)
        fresh_redis = _FakeRedis()
        key = _gap_timer_key(TENANT_A, SITE_A)
        assert key not in fresh_redis.store

        _run(TENANT_A, SITE_A, cameras_online=1, cameras_total=3, repo=repo, redis_client=fresh_redis)

        assert key in fresh_redis.store
        assert float(fresh_redis.store[key]) <= time.time()

    def test_liveness_gap_persists_past_threshold_creates_alert(self) -> None:
        """A gap timer older than the threshold → alert is created."""
        repo = _make_repo(open_alert=None)
        old_redis = _elapsed_redis(TENANT_A, SITE_A, minutes_ago=999)

        _run(TENANT_A, SITE_A, cameras_online=1, cameras_total=3, repo=repo, redis_client=old_redis)

        repo.create_gap_alert.assert_called_once()

    def test_liveness_repeated_gap_within_grace_period_never_alerts(self) -> None:
        """A gap observed twice, both times inside the grace period, never alerts."""
        repo = _make_repo(open_alert=None)
        redis_client = _FakeRedis()

        _run(TENANT_A, SITE_A, cameras_online=1, cameras_total=3, repo=repo, redis_client=redis_client)
        _run(TENANT_A, SITE_A, cameras_online=1, cameras_total=3, repo=repo, redis_client=redis_client)

        repo.create_gap_alert.assert_not_called()

    def test_liveness_recovery_clears_gap_timer(self) -> None:
        """Recovery removes the Redis gap_since key so the next gap restarts the clock."""
        repo = _make_repo(ack_count=1)
        key = _gap_timer_key(TENANT_A, SITE_A)
        redis_client = _FakeRedis(seed={key: str(time.time() - 999 * 60)})

        _run(TENANT_A, SITE_A, cameras_online=3, cameras_total=3, repo=repo, redis_client=redis_client)

        assert key not in redis_client.store

    def test_liveness_redis_error_on_gap_is_swallowed(self) -> None:
        """Redis failure while starting/reading the timer must not propagate."""
        repo = _make_repo(open_alert=None)
        broken_redis = MagicMock()
        broken_redis.set.side_effect = ConnectionError("redis down")
        pool = MagicMock()

        patch_target = "app.domain.services.liveness_service.LivenessAlertRepository"
        with patch(patch_target, return_value=repo):
            # Must not raise
            check_camera_liveness(TENANT_A, SITE_A, 1, 3, pool, redis_client=broken_redis)

        repo.create_gap_alert.assert_not_called()

    def test_liveness_redis_error_on_recovery_still_acknowledges_db(self) -> None:
        """Redis failure while clearing the timer must not block the DB-side
        acknowledgement of open alerts — the two are decoupled by design."""
        repo = _make_repo(ack_count=1)
        broken_redis = MagicMock()
        broken_redis.delete.side_effect = ConnectionError("redis down")
        pool = MagicMock()

        patch_target = "app.domain.services.liveness_service.LivenessAlertRepository"
        with patch(patch_target, return_value=repo):
            check_camera_liveness(TENANT_A, SITE_A, 3, 3, pool, redis_client=broken_redis)

        repo.acknowledge_gap_alerts.assert_called_once_with(TENANT_A, f"heartbeat/{SITE_A}")
