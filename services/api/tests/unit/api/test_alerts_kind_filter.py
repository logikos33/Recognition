"""Tests: ?kind= no /api/alerts + GET /api/alerts/usage-rate (ADR-0063).

Fronteira HTTP: um valor que a tela manda tem de CHEGAR ao repositório, e a
rota nova tem de existir de verdade — não basta o método do repositório estar
certo (o RFC 822 do jsonify já passou por review e CI uma vez justamente
porque o teste parou antes da rota).

FALHA antes do fix:
  · `list_with_filters` não aceitava `kind` → TypeError → 500;
  · `/api/alerts/usage-rate` não existia → 404 (ou era engolido pela rota
    dinâmica `/<alert_id>`, que responde 404 para id malformado — por isso o
    teste exige 200 e checa a CHAMADA ao repositório, não só o status).
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
_GET_REPO = "app.api.v1.alerts.routes._get_repo"


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


def _mock_repo(items=None, total=0, areas=None):
    repo = MagicMock()
    repo.list_with_filters.return_value = {"items": items or [], "total": total}
    repo.usage_rate_by_area.return_value = areas or []
    return repo


class TestKindFilterReachesRepository:

    @pytest.mark.parametrize("kind", ["violation", "compliance"])
    def test_valid_kind_forwarded(self, client, auth_headers, kind):
        repo = _mock_repo()
        with patch(_GET_REPO, return_value=repo):
            resp = client.get(f"/api/alerts?kind={kind}", headers=auth_headers)
        assert resp.status_code == 200
        assert repo.list_with_filters.call_args[1]["kind"] == kind

    def test_invalid_kind_falls_back_to_all(self, client, auth_headers):
        """Querystring inválida não pode virar 500 nem filtro silencioso."""
        repo = _mock_repo()
        with patch(_GET_REPO, return_value=repo):
            resp = client.get("/api/alerts?kind=lixo", headers=auth_headers)
        assert resp.status_code == 200
        assert repo.list_with_filters.call_args[1]["kind"] is None

    def test_default_is_all_on_the_backend(self, client, auth_headers):
        """Sem `kind`, nenhum consumidor existente muda de comportamento."""
        repo = _mock_repo()
        with patch(_GET_REPO, return_value=repo):
            client.get("/api/alerts", headers=auth_headers)
        assert repo.list_with_filters.call_args[1]["kind"] is None

    def test_export_exports_the_same_slice(self, client, auth_headers):
        repo = _mock_repo()
        with patch(_GET_REPO, return_value=repo):
            resp = client.get("/api/alerts/export?kind=violation", headers=auth_headers)
        assert resp.status_code == 200
        assert repo.list_with_filters.call_args[1]["kind"] == "violation"

    def test_event_kind_survives_the_envelope(self, client, auth_headers):
        """A tela lê `event_kind` de cada item — não pode ser filtrado fora."""
        items = [{"id": str(uuid4()), "event_kind": "compliance", "acknowledged": False}]
        with patch(_GET_REPO, return_value=_mock_repo(items=items, total=1)):
            resp = client.get("/api/alerts", headers=auth_headers)
        assert resp.get_json()["data"]["alerts"][0]["event_kind"] == "compliance"


class TestUsageRate:

    def test_without_token_returns_401(self, client):
        assert client.get("/api/alerts/usage-rate").status_code == 401

    def test_returns_areas(self, client, auth_headers):
        areas = [{"area": "Expedição", "compliance": 3, "violation": 1}]
        repo = _mock_repo(areas=areas)
        with patch(_GET_REPO, return_value=repo):
            resp = client.get("/api/alerts/usage-rate", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["areas"] == areas
        # Prova que caiu NESTA rota e não na dinâmica /<alert_id>.
        repo.usage_rate_by_area.assert_called_once()
        assert repo.usage_rate_by_area.call_args[1]["tenant_id"] == TENANT_ID

    def test_dates_and_module_forwarded(self, client, auth_headers):
        repo = _mock_repo()
        with patch(_GET_REPO, return_value=repo):
            client.get(
                "/api/alerts/usage-rate"
                "?start_date=2026-08-01T00:00:00Z&end_date=2026-08-02T00:00:00Z"
                "&module_code=epi",
                headers=auth_headers,
            )
        kw = repo.usage_rate_by_area.call_args[1]
        assert kw["module_code"] == "epi"
        assert kw["from_ts"] < kw["to_ts"]

    def test_repository_exception_returns_500(self, client, auth_headers):
        repo = MagicMock()
        repo.usage_rate_by_area.side_effect = Exception("DB error")
        with patch(_GET_REPO, return_value=repo):
            resp = client.get("/api/alerts/usage-rate", headers=auth_headers)
        assert resp.status_code == 500


class TestParseKind:

    def test_only_the_two_known_values_pass(self):
        from app.api.v1.alerts.routes import _parse_kind
        assert _parse_kind("violation") == "violation"
        assert _parse_kind("compliance") == "compliance"
        for bad in (None, "", "all", "VIOLATION", "1; DROP TABLE alerts"):
            assert _parse_kind(bad) is None
