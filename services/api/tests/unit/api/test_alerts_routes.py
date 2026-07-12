"""Tests: alerts/routes.py — list, export, acknowledge, snapshot, stats."""
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest


TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
ALERT_ID = str(uuid4())
_GET_REPO = "app.api.v1.alerts.routes._get_repo"
_TRAINING_INFERENCE = "app.api.v1.training.job_handlers.get_inference_service"
_GET_STORAGE = "app.infrastructure.storage.local_storage.get_storage"


@pytest.fixture
def auth_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=USER_ID,
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "public",
                "email": "test@test.com",
                "role": "admin",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _mock_repo(items=None, total=0):
    repo = MagicMock()
    repo.list_with_filters.return_value = {"items": items or [], "total": total}
    return repo


# ---------------------------------------------------------------------------
# GET /api/alerts
# ---------------------------------------------------------------------------

class TestListAlerts:

    def test_without_token_returns_401(self, client):
        resp = client.get("/api/alerts")
        assert resp.status_code == 401

    def test_empty_result(self, client, auth_headers):
        with patch(_GET_REPO, return_value=_mock_repo()):
            resp = client.get("/api/alerts", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["alerts"] == []
        assert data["data"]["total"] == 0

    def test_with_items(self, client, auth_headers):
        items = [{"id": ALERT_ID, "camera_name": "Cam-1", "acknowledged": False}]
        with patch(_GET_REPO, return_value=_mock_repo(items=items, total=1)):
            resp = client.get("/api/alerts", headers=auth_headers)
        data = resp.get_json()
        assert data["data"]["count"] == 1
        assert data["data"]["total"] == 1

    def test_pagination_params_forwarded(self, client, auth_headers):
        repo = _mock_repo(total=50)
        with patch(_GET_REPO, return_value=repo):
            client.get("/api/alerts?page=2&per_page=10", headers=auth_headers)
        call_kwargs = repo.list_with_filters.call_args[1]
        assert call_kwargs["limit"] == 10
        assert call_kwargs["offset"] == 10

    def test_per_page_capped_at_100(self, client, auth_headers):
        repo = _mock_repo()
        with patch(_GET_REPO, return_value=repo):
            client.get("/api/alerts?per_page=9999", headers=auth_headers)
        call_kwargs = repo.list_with_filters.call_args[1]
        assert call_kwargs["limit"] == 100

    def test_service_exception_returns_500(self, client, auth_headers):
        repo = MagicMock()
        repo.list_with_filters.side_effect = Exception("DB error")
        with patch(_GET_REPO, return_value=repo):
            resp = client.get("/api/alerts", headers=auth_headers)
        assert resp.status_code == 500

    def test_pages_calculated_correctly(self, client, auth_headers):
        with patch(_GET_REPO, return_value=_mock_repo(total=25)):
            resp = client.get("/api/alerts?per_page=10", headers=auth_headers)
        data = resp.get_json()
        assert data["data"]["pages"] == 3


# ---------------------------------------------------------------------------
# GET /api/alerts/export
# ---------------------------------------------------------------------------

class TestExportAlerts:

    def test_without_token_returns_401(self, client):
        resp = client.get("/api/alerts/export")
        assert resp.status_code == 401

    def test_returns_csv_content_type(self, client, auth_headers):
        items = [{"created_at": "2024-01-01", "camera_name": "C1",
                  "acknowledged": True, "violations": [{"class": "no_helmet", "confidence": 0.9}]}]
        with patch(_GET_REPO, return_value=_mock_repo(items=items)):
            resp = client.get("/api/alerts/export", headers=auth_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.content_type

    def test_csv_has_header_row(self, client, auth_headers):
        with patch(_GET_REPO, return_value=_mock_repo()):
            resp = client.get("/api/alerts/export", headers=auth_headers)
        assert b"Data" in resp.data

    def test_alert_without_violations_exports_one_row(self, client, auth_headers):
        items = [{"created_at": "2024-01-01", "camera_name": "C1",
                  "acknowledged": False, "violations": []}]
        with patch(_GET_REPO, return_value=_mock_repo(items=items)):
            resp = client.get("/api/alerts/export", headers=auth_headers)
        assert resp.status_code == 200

    def test_service_exception_returns_500(self, client, auth_headers):
        repo = MagicMock()
        repo.list_with_filters.side_effect = Exception("DB error")
        with patch(_GET_REPO, return_value=repo):
            resp = client.get("/api/alerts/export", headers=auth_headers)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/alerts/<alert_id>/acknowledge
# ---------------------------------------------------------------------------

class TestAcknowledgeAlert:
    # NOTE: the /api/alerts/<id>/acknowledge URL is handled by the training blueprint
    # (registered first). Tests patch app.api.v1.training.job_handlers.get_inference_service.

    def test_without_token_returns_401(self, client):
        resp = client.post(f"/api/alerts/{ALERT_ID}/acknowledge")
        assert resp.status_code == 401

    def test_alert_found_returns_200(self, client, auth_headers):
        mock_inf = MagicMock()
        mock_inf.acknowledge_alert.return_value = {"id": ALERT_ID, "acknowledged": True}
        with patch(_TRAINING_INFERENCE, return_value=mock_inf):
            resp = client.post(f"/api/alerts/{ALERT_ID}/acknowledge", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_exception_returns_500(self, client, auth_headers):
        mock_inf = MagicMock()
        mock_inf.acknowledge_alert.side_effect = Exception("DB error")
        with patch(_TRAINING_INFERENCE, return_value=mock_inf):
            resp = client.post(f"/api/alerts/{ALERT_ID}/acknowledge", headers=auth_headers)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/alerts/<alert_id>/snapshot — task-074 (achado #7)
# ---------------------------------------------------------------------------

class TestAlertSnapshot:
    """Isolamento de tenant no snapshot de alerta (task-074 / achado #7).

    FALHA antes do fix: a rota buscava o alerta com
    `SELECT evidence_key FROM alerts WHERE id = %s` — sem `tenant_id` — então
    qualquer tenant autenticado podia ler o snapshot (imagem de evidência) de
    um alerta de OUTRO tenant, bastando adivinhar/enumerar o `alert_id`.
    PASSA após o fix: a rota chama `repo.get_evidence_key(alert_id, tenant_id=...)`,
    que filtra por `tenant_id` no SQL — alerta de outro tenant nunca é
    encontrado e a rota responde 404 (idêntico ao caso "alerta inexistente",
    para não permitir enumeração cross-tenant).
    """

    def test_without_token_returns_401(self, client):
        resp = client.get(f"/api/alerts/{ALERT_ID}/snapshot")
        assert resp.status_code == 401

    def test_cross_tenant_alert_returns_404(self, client, auth_headers):
        """Alerta existe mas pertence a outro tenant — repo (tenant-scoped) não acha a linha."""
        repo = MagicMock()
        repo.get_evidence_key.return_value = None
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts/{ALERT_ID}/snapshot", headers=auth_headers)
        assert resp.status_code == 404
        # Prova que a busca já nasce tenant-scoped — nunca busca só por id.
        repo.get_evidence_key.assert_called_once_with(UUID(ALERT_ID), tenant_id=TENANT_ID)

    def test_nonexistent_alert_returns_404(self, client, auth_headers):
        repo = MagicMock()
        repo.get_evidence_key.return_value = None
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts/{ALERT_ID}/snapshot", headers=auth_headers)
        assert resp.status_code == 404

    def test_alert_without_evidence_key_returns_404(self, client, auth_headers):
        repo = MagicMock()
        repo.get_evidence_key.return_value = {"evidence_key": None}
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts/{ALERT_ID}/snapshot", headers=auth_headers)
        assert resp.status_code == 404

    def test_same_tenant_alert_returns_snapshot_url(self, client, auth_headers):
        """Regressão: alerta do PRÓPRIO tenant continua funcionando normalmente."""
        from app.infrastructure.storage.r2_storage import R2Storage

        repo = MagicMock()
        repo.get_evidence_key.return_value = {"evidence_key": "evidence/cam-1/123.jpg"}
        mock_storage = MagicMock(spec=R2Storage)
        mock_storage.generate_presigned_download_url.return_value = "https://r2.example.com/signed"
        with patch(_GET_REPO, return_value=repo), patch(_GET_STORAGE, return_value=mock_storage):
            resp = client.get(f"/api/alerts/{ALERT_ID}/snapshot", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["snapshot_url"] == "https://r2.example.com/signed"
        repo.get_evidence_key.assert_called_once_with(UUID(ALERT_ID), tenant_id=TENANT_ID)
        mock_storage.generate_presigned_download_url.assert_called_once_with(
            "evidence/cam-1/123.jpg", ttl=3600, response_content_type="image/jpeg"
        )

    def test_local_storage_returns_400(self, client, auth_headers):
        from app.infrastructure.storage.local_storage import LocalStorage

        repo = MagicMock()
        repo.get_evidence_key.return_value = {"evidence_key": "evidence/cam-1/123.jpg"}
        mock_storage = MagicMock(spec=LocalStorage)
        with patch(_GET_REPO, return_value=repo), patch(_GET_STORAGE, return_value=mock_storage):
            resp = client.get(f"/api/alerts/{ALERT_ID}/snapshot", headers=auth_headers)
        assert resp.status_code == 400

    def test_service_exception_returns_500(self, client, auth_headers):
        repo = MagicMock()
        repo.get_evidence_key.side_effect = Exception("DB error")
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts/{ALERT_ID}/snapshot", headers=auth_headers)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /api/alerts/stats
# ---------------------------------------------------------------------------

class TestAlertStats:

    def test_without_token_returns_401(self, client):
        resp = client.get("/api/alerts/stats")
        assert resp.status_code == 401

    def test_returns_total_and_unacknowledged(self, client, auth_headers):
        repo = MagicMock()
        repo.count_by_camera.return_value = 10
        repo.get_unacknowledged.return_value = [{"id": ALERT_ID}] * 3
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts/stats?camera_id={ALERT_ID}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["total"] == 10
        assert data["data"]["unacknowledged"] == 3

    def test_no_camera_id_returns_zero_total(self, client, auth_headers):
        repo = MagicMock()
        repo.get_unacknowledged.return_value = []
        with patch(_GET_REPO, return_value=repo):
            resp = client.get("/api/alerts/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["total"] == 0

    def test_exception_returns_500(self, client, auth_headers):
        repo = MagicMock()
        repo.count_by_camera.side_effect = Exception("DB error")
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts/stats?camera_id={ALERT_ID}", headers=auth_headers)
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:

    def test_parse_date_valid_iso(self):
        from app.api.v1.alerts.routes import _parse_date
        result = _parse_date("2024-01-15T10:30:00Z")
        assert result is not None

    def test_parse_date_none_returns_none(self):
        from app.api.v1.alerts.routes import _parse_date
        assert _parse_date(None) is None

    def test_parse_date_invalid_returns_none(self):
        from app.api.v1.alerts.routes import _parse_date
        assert _parse_date("not-a-date") is None

    def test_parse_bool_true_strings(self):
        from app.api.v1.alerts.routes import _parse_bool
        for s in ("true", "True", "1", "yes"):
            assert _parse_bool(s) is True

    def test_parse_bool_false_strings(self):
        from app.api.v1.alerts.routes import _parse_bool
        for s in ("false", "False", "0", "no"):
            assert _parse_bool(s) is False

    def test_parse_bool_none_returns_none(self):
        from app.api.v1.alerts.routes import _parse_bool
        assert _parse_bool(None) is None
