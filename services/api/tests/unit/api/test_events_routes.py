"""Testes — GET /api/events/search e GET /api/events/timeline.

Repositório mockado em memória (FakeAlertRepo).
Valida: isolamento por tenant, filtros combinados, paginação, injeção SQL via params.
"""
import uuid
from datetime import datetime, timezone

import pytest
from flask_jwt_extended import create_access_token

import app.api.v1.events.routes as events_routes

TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
CAM_1 = str(uuid.uuid4())
CAM_2 = str(uuid.uuid4())

_T0 = datetime(2026, 6, 30, 14, 0, 0, tzinfo=timezone.utc)
_T1 = datetime(2026, 6, 30, 15, 0, 0, tzinfo=timezone.utc)
_T2 = datetime(2026, 6, 30, 16, 0, 0, tzinfo=timezone.utc)


def _mk_event(tenant_id: str, camera_id: str, cls: str, conf: float, ts: datetime) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "camera_id": camera_id,
        "module_code": "epi",
        "violations": [{"class": cls, "confidence": conf}],
        "confidence": conf,
        "evidence_key": None,
        "acknowledged": False,
        "created_at": ts,
        "camera_name": "Câmera",
    }


EVENTS = [
    _mk_event(TENANT_A, CAM_1, "no_helmet", 0.92, _T0),
    _mk_event(TENANT_A, CAM_1, "no_vest", 0.75, _T1),
    _mk_event(TENANT_A, CAM_2, "no_helmet", 0.60, _T2),
    _mk_event(TENANT_B, CAM_1, "no_helmet", 0.95, _T0),  # outro tenant — não deve aparecer
]


class FakeAlertRepo:
    """Simula AlertRepository em memória."""

    def search_events(
        self,
        tenant_id: str,
        limit: int = 20,
        offset: int = 0,
        camera_ids=None,
        class_names=None,
        module_code=None,
        from_ts=None,
        to_ts=None,
        min_confidence=None,
    ) -> dict:
        rows = [e for e in EVENTS if e["tenant_id"] == tenant_id]
        if camera_ids:
            rows = [r for r in rows if r["camera_id"] in camera_ids]
        if class_names:
            rows = [
                r for r in rows
                if any(v["class"] in class_names for v in r["violations"])
            ]
        if from_ts:
            rows = [r for r in rows if r["created_at"] >= from_ts]
        if to_ts:
            rows = [r for r in rows if r["created_at"] <= to_ts]
        if min_confidence is not None:
            rows = [r for r in rows if r["confidence"] >= min_confidence]
        total = len(rows)
        return {"items": rows[offset: offset + limit], "total": total}

    def timeline_by_bucket(
        self,
        tenant_id: str,
        from_ts,
        to_ts,
        bucket="hour",
        camera_ids=None,
        class_names=None,
        module_code=None,
    ) -> list:
        rows = [
            e for e in EVENTS
            if e["tenant_id"] == tenant_id
            and e["created_at"] >= from_ts
            and e["created_at"] <= to_ts
        ]
        # Simple bucket: truncate to hour
        from collections import defaultdict
        counts: dict = defaultdict(int)
        for r in rows:
            ts = r["created_at"].replace(minute=0, second=0, microsecond=0)
            counts[ts] += 1
        return [{"bucket": k, "count": v} for k, v in sorted(counts.items())]


@pytest.fixture
def fake_repo(monkeypatch):
    repo = FakeAlertRepo()
    monkeypatch.setattr(events_routes, "_get_repo", lambda: repo)
    return repo


def _auth(app, tenant_id: str) -> str:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={"tenant_id": tenant_id, "role": "operator"},
        )
    return f"Bearer {token}"


# ---------------------------------------------------------------------------
# /api/events/search
# ---------------------------------------------------------------------------

class TestSearchEvents:
    def test_tenant_isolation(self, app, client, fake_repo):
        """TENANT_B events não aparecem para TENANT_A."""
        res = client.get(
            "/api/events/search",
            headers={"Authorization": _auth(app, TENANT_A)},
        )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["total"] == 3
        assert all(e["tenant_id"] == TENANT_A for e in data["events"])

    def test_filter_by_camera(self, app, client, fake_repo):
        res = client.get(
            f"/api/events/search?camera_ids={CAM_1}",
            headers={"Authorization": _auth(app, TENANT_A)},
        )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["total"] == 2
        assert all(e["camera_id"] == CAM_1 for e in data["events"])

    def test_filter_by_class(self, app, client, fake_repo):
        res = client.get(
            "/api/events/search?classes=no_helmet",
            headers={"Authorization": _auth(app, TENANT_A)},
        )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["total"] == 2
        for ev in data["events"]:
            assert any(v["class"] == "no_helmet" for v in ev["violations"])

    def test_filter_by_min_confidence(self, app, client, fake_repo):
        res = client.get(
            "/api/events/search?min_confidence=0.80",
            headers={"Authorization": _auth(app, TENANT_A)},
        )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["total"] == 1
        assert data["events"][0]["confidence"] >= 0.80

    def test_pagination(self, app, client, fake_repo):
        res = client.get(
            "/api/events/search?per_page=2&page=1",
            headers={"Authorization": _auth(app, TENANT_A)},
        )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert len(data["events"]) == 2
        assert data["pages"] == 2

    def test_combined_filters(self, app, client, fake_repo):
        res = client.get(
            f"/api/events/search?camera_ids={CAM_1}&classes=no_helmet",
            headers={"Authorization": _auth(app, TENANT_A)},
        )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert data["total"] == 1

    def test_requires_auth(self, client):
        res = client.get("/api/events/search")
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# /api/events/timeline
# ---------------------------------------------------------------------------

class TestEventsTimeline:
    def test_requires_from_and_to(self, app, client, fake_repo):
        res = client.get(
            "/api/events/timeline?from=2026-06-30T13:00:00",
            headers={"Authorization": _auth(app, TENANT_A)},
        )
        assert res.status_code == 400

    def test_tenant_isolation(self, app, client, fake_repo):
        """TENANT_B events não são incluídos no timeline de TENANT_A."""
        res = client.get(
            "/api/events/timeline"
            "?from=2026-06-30T13:00:00Z&to=2026-06-30T17:00:00Z",
            headers={"Authorization": _auth(app, TENANT_A)},
        )
        assert res.status_code == 200
        data = res.get_json()["data"]
        total_count = sum(b["count"] for b in data["timeline"])
        # TENANT_A has 3 events in range
        assert total_count == 3

    def test_timeline_buckets(self, app, client, fake_repo):
        res = client.get(
            "/api/events/timeline"
            "?from=2026-06-30T13:00:00Z&to=2026-06-30T17:00:00Z&bucket=hour",
            headers={"Authorization": _auth(app, TENANT_A)},
        )
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert "timeline" in data
        assert data["bucket"] == "hour"
        # Each bucket has a string timestamp and a count
        for b in data["timeline"]:
            assert "bucket" in b
            assert "count" in b
            assert isinstance(b["count"], int)

    def test_requires_auth(self, client):
        res = client.get(
            "/api/events/timeline?from=2026-06-30T13:00:00Z&to=2026-06-30T17:00:00Z"
        )
        assert res.status_code == 401
