"""Tests: /api/v1/admin/observability/* — WS11/E2-7.

Cobre: whitelist de window no /timeseries, require_superadmin (403 para
admin comum), summary degradando sem 500 com Redis/DB indisponíveis,
e POST /collect retornando points_recorded.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

SUPER_TENANT = "00000000-0000-0000-0000-000000000001"
_SVC = "app.domain.services.observability_service"


def _auth_header(app, role: str = "superadmin") -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": SUPER_TENANT,
                "tenant_schema": "public",
                "role": role,
            },
        )
    return {"Authorization": f"Bearer {token}"}


class TestAuthorization:
    def test_summary_403_for_admin(self, app, client):
        resp = client.get(
            "/api/v1/admin/observability/summary",
            headers=_auth_header(app, role="admin"),
        )
        assert resp.status_code == 403

    def test_timeseries_403_for_operator(self, app, client):
        resp = client.get(
            "/api/v1/admin/observability/timeseries?scope=api&metric=http_count",
            headers=_auth_header(app, role="operator"),
        )
        assert resp.status_code == 403

    def test_edge_fleet_403_for_admin(self, app, client):
        resp = client.get(
            "/api/v1/admin/observability/edge-fleet",
            headers=_auth_header(app, role="admin"),
        )
        assert resp.status_code == 403

    def test_collect_401_without_token(self, client):
        resp = client.post("/api/v1/admin/observability/collect")
        assert resp.status_code == 401


class TestTimeseriesValidation:
    def test_invalid_window_returns_400(self, app, client):
        resp = client.get(
            "/api/v1/admin/observability/timeseries"
            "?scope=celery&metric=queue_depth&window=99d",
            headers=_auth_header(app),
        )
        assert resp.status_code == 400
        assert "Janela inválida" in resp.get_json()["error"]

    def test_missing_scope_returns_400(self, app, client):
        resp = client.get(
            "/api/v1/admin/observability/timeseries?metric=queue_depth",
            headers=_auth_header(app),
        )
        assert resp.status_code == 400

    def test_valid_window_calls_service(self, app, client):
        with patch(
            f"{_SVC}.get_timeseries",
            return_value={"points": [], "window": "1h", "bucket_seconds": 60},
        ) as mock_ts:
            resp = client.get(
                "/api/v1/admin/observability/timeseries"
                "?scope=celery&metric=queue_depth&window=1h&queue=inference",
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        mock_ts.assert_called_once_with(
            scope="celery", metric="queue_depth", window="1h",
            tenant_id=None, queue="inference",
        )
        body = resp.get_json()
        assert body["data"]["bucket_seconds"] == 60


class TestSummaryDegradation:
    def test_summary_with_redis_and_db_down_returns_200(self, app, client):
        """Redis indisponível + pool None → degrada, nunca 500."""
        with patch(f"{_SVC}._get_redis", side_effect=Exception("redis down")), \
             patch(f"{_SVC}._pool", return_value=None), \
             patch(f"{_SVC}._r2_section",
                   return_value={"status": "degraded", "details": "sem storage"}):
            resp = client.get(
                "/api/v1/admin/observability/summary",
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["status"] == "critical"
        assert data["services"]["redis"]["status"] == "critical"
        assert data["api"]["req_1h"] == 0

    def test_summary_shape_with_mocked_sections(self, app, client):
        r = MagicMock()
        r.ping.return_value = True
        r.info.return_value = {"used_memory": 2_097_152, "connected_clients": 3}
        r.scan.return_value = (0, [])
        r.llen.return_value = 0
        r.hgetall.return_value = {}
        r.lindex.return_value = None
        with patch(f"{_SVC}._get_redis", return_value=r), \
             patch(f"{_SVC}._pool", return_value=None), \
             patch(f"{_SVC}._r2_section",
                   return_value={"status": "healthy", "latency_ms": 5.0}):
            resp = client.get(
                "/api/v1/admin/observability/summary",
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        # DB critical (pool None) domina o status geral
        assert data["status"] == "critical"
        assert data["services"]["redis"]["mem_mb"] == 2.0
        assert isinstance(data["celery"]["queues"], list)
        assert {q["name"] for q in data["celery"]["queues"]} >= {"inference", "training"}
        assert "migrations" in data
        assert "workers" in data


class TestCollect:
    def test_collect_returns_points_recorded(self, app, client):
        with patch(
            "app.infrastructure.queue.tasks.observability.collect_platform_metrics",
            return_value=17,
        ):
            resp = client.post(
                "/api/v1/admin/observability/collect",
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["points_recorded"] == 17


class TestEdgeFleet:
    def test_edge_fleet_returns_sites(self, app, client):
        site = {
            "site_id": "s1", "name": "Unidade Alpha", "tenant_id": "t1",
            "tenant_name": "Tenant A", "derived_status": "healthy",
            "gpu_temp_c": 61.5, "decode_fps": 24.0,
        }
        with patch(f"{_SVC}.get_edge_fleet", return_value=[site]):
            resp = client.get(
                "/api/v1/admin/observability/edge-fleet",
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        sites = resp.get_json()["data"]["sites"]
        assert sites[0]["tenant_name"] == "Tenant A"
        assert sites[0]["gpu_temp_c"] == 61.5


class TestStreams:
    def test_streams_aggregate_shape(self, app, client):
        agg = {
            "gateway_online": True,
            "cameras": [{"id": "c1", "name": "Cam 1", "streaming": True,
                         "ttl_seconds": 120, "tenant_name": "Tenant A",
                         "tenant_id": "t1", "location": None}],
            "cameras_total": 1,
            "cameras_streaming": 1,
            "celery_workers": [{"worker_id": "w@host", "status": "online",
                                "active_tasks": 2, "pool": "prefork"}],
        }
        with patch(f"{_SVC}.get_streams_aggregate", return_value=agg):
            resp = client.get(
                "/api/v1/admin/observability/streams",
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["cameras_total"] == 1
        assert data["celery_workers"][0]["status"] == "online"
