"""
Testes de round-trip, validação de enum e from_attributes para recognition_shared.
"""
import pytest
from decimal import Decimal
from uuid import UUID, uuid4
from datetime import datetime, timezone

from pydantic import ValidationError

from recognition_shared import (
    DeploymentMode,
    SiteStatus,
    HeartbeatStatus,
    DeviceTokenScope,
    EdgeSite,
    EdgeSiteCreate,
    DeviceToken,
    DeviceClaims,
    EnrollmentRequest,
    EnrollmentResponse,
    Heartbeat,
    HeartbeatRecord,
)


TENANT_ID = uuid4()
SITE_ID = uuid4()
DEVICE_ID = uuid4()
NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_deployment_mode_values(self):
        assert DeploymentMode.cloud == "cloud"
        assert DeploymentMode.edge == "edge"
        assert DeploymentMode.hybrid == "hybrid"

    def test_site_status_values(self):
        assert SiteStatus.active == "active"
        assert SiteStatus.provisioning == "provisioning"

    def test_heartbeat_status_values(self):
        assert HeartbeatStatus.healthy == "healthy"
        assert HeartbeatStatus.offline == "offline"

    def test_device_token_scope_values(self):
        assert DeviceTokenScope.heartbeat_write == "heartbeat:write"
        assert DeviceTokenScope.events_write == "events:write"

    def test_invalid_deployment_mode_rejected(self):
        with pytest.raises(ValidationError):
            EdgeSiteCreate(name="x", deployment_mode="on_premise")

    def test_invalid_site_status_rejected(self):
        with pytest.raises(ValidationError):
            EdgeSite(
                id=SITE_ID,
                tenant_id=TENANT_ID,
                name="x",
                description=None,
                location=None,
                deployment_mode=DeploymentMode.cloud,
                status="broken",
                created_at=NOW,
                updated_at=NOW,
                created_by=None,
            )

    def test_invalid_heartbeat_status_rejected(self):
        with pytest.raises(ValidationError):
            Heartbeat(device_id="dev-1", status="unknown")


# ---------------------------------------------------------------------------
# EdgeSite
# ---------------------------------------------------------------------------

class TestEdgeSite:
    def _site_dict(self):
        return {
            "id": str(SITE_ID),
            "tenant_id": str(TENANT_ID),
            "name": "Planta Norte",
            "description": "Galpão principal",
            "location": "São Paulo, SP",
            "deployment_mode": "edge",
            "status": "active",
            "created_at": NOW,
            "updated_at": NOW,
            "created_by": None,
        }

    def test_round_trip_from_dict(self):
        site = EdgeSite(**self._site_dict())
        assert site.name == "Planta Norte"
        assert site.deployment_mode == DeploymentMode.edge
        assert site.status == SiteStatus.active
        assert isinstance(site.id, UUID)

    def test_serializes_to_dict(self):
        site = EdgeSite(**self._site_dict())
        d = site.model_dump()
        assert d["deployment_mode"] == "edge"
        assert d["status"] == "active"

    def test_from_attributes(self):
        """Simula RealDictRow retornado pelo psycopg2."""
        class FakeRow:
            id = SITE_ID
            tenant_id = TENANT_ID
            name = "Test Site"
            description = None
            location = None
            deployment_mode = "cloud"
            status = "provisioning"
            created_at = NOW
            updated_at = NOW
            created_by = None

        site = EdgeSite.model_validate(FakeRow())
        assert site.name == "Test Site"
        assert site.deployment_mode == DeploymentMode.cloud

    def test_create_defaults(self):
        create = EdgeSiteCreate(name="New Site", deployment_mode="hybrid")
        assert create.status == SiteStatus.provisioning


# ---------------------------------------------------------------------------
# DeviceToken / Claims / Enrollment
# ---------------------------------------------------------------------------

class TestDeviceModels:
    def test_enrollment_request_round_trip(self):
        req = EnrollmentRequest(
            enrollment_token="tok_abc123",
            device_id="device-001",
            public_key_pem="-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----",
        )
        assert req.device_name is None
        assert req.enrollment_token == "tok_abc123"

    def test_device_claims_round_trip(self):
        claims = DeviceClaims(
            tenant_id=TENANT_ID,
            site_id=SITE_ID,
            device_id="device-001",
            scopes=[DeviceTokenScope.heartbeat_write, DeviceTokenScope.events_write],
            iat=1700000000,
            exp=1700086400,
        )
        assert DeviceTokenScope.heartbeat_write in claims.scopes
        assert isinstance(claims.tenant_id, UUID)

    def test_device_claims_invalid_scope_rejected(self):
        with pytest.raises(ValidationError):
            DeviceClaims(
                tenant_id=TENANT_ID,
                site_id=SITE_ID,
                device_id="x",
                scopes=["invalid:scope"],
                iat=1,
                exp=2,
            )

    def test_device_token_from_attributes(self):
        class FakeRow:
            id = DEVICE_ID
            tenant_id = TENANT_ID
            site_id = SITE_ID
            device_id = "mini-pc-001"
            device_name = "Galpão Norte"
            fingerprint = "sha256:abc"
            revoked = False
            revoked_at = None
            revoked_by = None
            revocation_reason = None
            last_seen_at = NOW
            enrolled_at = NOW

        token = DeviceToken.model_validate(FakeRow())
        assert token.device_id == "mini-pc-001"
        assert token.revoked is False


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

class TestHeartbeat:
    def test_minimal_heartbeat(self):
        hb = Heartbeat(device_id="dev-001", status=HeartbeatStatus.healthy)
        assert hb.cpu_pct is None
        assert hb.status == HeartbeatStatus.healthy

    def test_full_heartbeat_round_trip(self):
        hb = Heartbeat(
            device_id="dev-001",
            cpu_pct=Decimal("45.50"),
            mem_pct=Decimal("70.10"),
            inference_fps=Decimal("4.97"),
            cameras_online=3,
            cameras_total=3,
            queue_depth=0,
            status="degraded",
            edge_version="1.2.0",
        )
        assert hb.status == HeartbeatStatus.degraded
        assert hb.cameras_online == 3

    def test_heartbeat_record_from_attributes(self):
        class FakeRow:
            id = 42
            tenant_id = TENANT_ID
            site_id = SITE_ID
            device_id = "dev-001"
            received_at = NOW
            cpu_pct = Decimal("50.00")
            mem_pct = None
            gpu_pct = None
            gpu_mem_pct = None
            disk_pct = None
            inference_fps = Decimal("5.00")
            inference_latency_ms = Decimal("200.00")
            cameras_online = 2
            cameras_total = 2
            queue_depth = 1
            upload_kbps = Decimal("512.00")
            download_kbps = Decimal("1024.00")
            status = "healthy"
            last_error = None
            edge_version = "1.0.0"

        record = HeartbeatRecord.model_validate(FakeRow())
        assert record.id == 42
        assert record.status == HeartbeatStatus.healthy
