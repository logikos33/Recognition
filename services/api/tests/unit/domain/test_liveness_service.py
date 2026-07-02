"""
Tests: liveness_service — per-camera liveness monitoring via heartbeat.

Coverage:
  - gap detected → alert created
  - no gap → no alert, existing alerts acknowledged
  - recovery → gap alerts acknowledged
  - tenant isolation → each tenant scoped independently
  - best-effort → exception inside service never propagates
  - idempotency → duplicate alerts are not created when one is already open
  - skip → cameras_total=0 means nothing to monitor
  - no anchor camera → alert creation is skipped gracefully
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.domain.services.liveness_service import check_camera_liveness

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

TENANT_A = str(uuid4())
TENANT_B = str(uuid4())
SITE_A = "schema_a"
SITE_B = "schema_b"
CAMERA_A = str(uuid4())


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
) -> None:
    """Run check_camera_liveness with a patched LivenessAlertRepository."""
    pool = MagicMock()
    patch_target = "app.domain.services.liveness_service.LivenessAlertRepository"
    with patch(patch_target, return_value=repo):
        check_camera_liveness(tenant_id, site_id, cameras_online, cameras_total, pool)


# ---------------------------------------------------------------------------
# Core behaviour
# ---------------------------------------------------------------------------


class TestLivenessGap:
    """Behaviour when cameras_online < cameras_total."""

    def test_liveness_gap_creates_alert(self) -> None:
        """cameras_online=1, cameras_total=3 → new gap alert created."""
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
            check_camera_liveness(TENANT_A, SITE_A, 1, 3, pool)

        # TENANT_B call — separate repo instance
        with patch(patch_target, return_value=repo_b):
            check_camera_liveness(TENANT_B, SITE_B, 2, 4, pool)

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
            check_camera_liveness(TENANT_A, SITE_A, 1, 3, pool)

    def test_liveness_best_effort_no_crash_on_create_error(self) -> None:
        """Exception during alert creation does not propagate."""
        repo = _make_repo(open_alert=None)
        repo.create_gap_alert.side_effect = ConnectionError("timeout")
        pool = MagicMock()

        patch_target = "app.domain.services.liveness_service.LivenessAlertRepository"
        with patch(patch_target, return_value=repo):
            check_camera_liveness(TENANT_A, SITE_A, 0, 5, pool)

    def test_liveness_best_effort_no_crash_on_ack_error(self) -> None:
        """Exception during acknowledgement does not propagate."""
        repo = _make_repo()
        repo.acknowledge_gap_alerts.side_effect = OSError("socket error")
        pool = MagicMock()

        patch_target = "app.domain.services.liveness_service.LivenessAlertRepository"
        with patch(patch_target, return_value=repo):
            check_camera_liveness(TENANT_A, SITE_A, 3, 3, pool)


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
