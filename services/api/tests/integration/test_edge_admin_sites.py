"""
Tests for task-003: admin edge sites + enrollment tokens.

Eval cases (spec):
  1. criar site → 201, tenant_id = do JWT (não do body, mesmo se body mandar outro) — C-01
  2. listar sites → só os do tenant do JWT (tenant_b não vê sites do tenant_a) — C-01
  3. gerar enrollment token → 201, retorna plaintext, banco fica só hash, used_at NULL
  4. gerar token para site de outro tenant → 404 (não vaza existência cross-tenant)
  5. sem JWT / role insuficiente → 401/403
"""
import hashlib
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jwt(app, tenant_id, role="admin", user_id=None):
    """Cria JWT de usuário com tenant_id e role nos claims adicionais."""
    uid = str(user_id or uuid4())
    with app.app_context():
        return create_access_token(
            identity=uid,
            additional_claims={"tenant_id": str(tenant_id), "role": role},
        )


def _mock_site(tenant_id, site_id=None):
    sid = str(site_id or uuid4())
    return {
        "id": sid,
        "tenant_id": str(tenant_id),
        "name": "Site Alfa",
        "description": None,
        "location": "Galpão 1",
        "deployment_mode": "edge",
        "status": "active",
        "created_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "created_by": None,
    }


def _mock_token_record(site_id, tenant_id):
    return {
        "id": str(uuid4()),
        "tenant_id": str(tenant_id),
        "site_id": str(site_id),
        "expires_at": datetime(2026, 6, 4, tzinfo=timezone.utc),
        "used_at": None,
        "created_at": datetime(2026, 6, 3, tzinfo=timezone.utc),
    }


# ---------------------------------------------------------------------------
# POST /api/v1/edge/sites
# ---------------------------------------------------------------------------

class TestCreateSite:

    def test_create_site_returns_201(self, client, app):
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id)
        site = _mock_site(tenant_id)

        mock_repo = MagicMock()
        mock_repo.create_site.return_value = site

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                "/api/v1/edge/sites",
                json={"name": "Site Alfa", "deployment_mode": "edge", "location": "Galpão 1"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["site"]["name"] == "Site Alfa"

    def test_create_site_tenant_id_always_from_jwt_not_body(self, client, app):
        """C-01: tenant_id do body é ignorado; usa o do JWT."""
        tenant_a = uuid4()
        tenant_b = uuid4()
        token = _make_jwt(app, tenant_a)
        site = _mock_site(tenant_a)

        mock_repo = MagicMock()
        mock_repo.create_site.return_value = site

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                "/api/v1/edge/sites",
                json={
                    "name": "Site X",
                    "deployment_mode": "cloud",
                    "tenant_id": str(tenant_b),  # deve ser ignorado
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 201
        call_args = mock_repo.create_site.call_args
        used_tenant = call_args.args[0]
        assert used_tenant == str(tenant_a), "tenant_id deve vir do JWT, não do body"
        assert used_tenant != str(tenant_b)

    def test_create_site_invalid_deployment_mode_returns_400(self, client, app):
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_repo = MagicMock()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                "/api/v1/edge/sites",
                json={"name": "X", "deployment_mode": "invalid_mode"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        mock_repo.create_site.assert_not_called()

    def test_create_site_missing_name_returns_400(self, client, app):
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_repo = MagicMock()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                "/api/v1/edge/sites",
                json={"deployment_mode": "edge"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 400
        mock_repo.create_site.assert_not_called()

    def test_create_site_superadmin_role_allowed(self, client, app):
        """superadmin também é aceito (além de admin)."""
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id, role="superadmin")
        site = _mock_site(tenant_id)

        mock_repo = MagicMock()
        mock_repo.create_site.return_value = site

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                "/api/v1/edge/sites",
                json={"name": "Site X", "deployment_mode": "hybrid"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/v1/edge/sites
# ---------------------------------------------------------------------------

class TestListSites:

    def test_list_sites_returns_own_sites(self, client, app):
        tenant_a = uuid4()
        site_a = _mock_site(tenant_a)
        token = _make_jwt(app, tenant_a)

        mock_repo = MagicMock()
        mock_repo.list_sites.return_value = [site_a]

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                "/api/v1/edge/sites",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        data = res.get_json()
        assert len(data["data"]["sites"]) == 1
        mock_repo.list_sites.assert_called_once_with(str(tenant_a))

    def test_list_sites_tenant_b_cannot_see_tenant_a_sites(self, client, app):
        """C-01: tenant_b não vê sites do tenant_a."""
        tenant_a = uuid4()
        tenant_b = uuid4()
        site_a = _mock_site(tenant_a)

        mock_repo = MagicMock()

        def _list(tid):
            return [site_a] if tid == str(tenant_a) else []

        mock_repo.list_sites.side_effect = _list

        token_b = _make_jwt(app, tenant_b)

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                "/api/v1/edge/sites",
                headers={"Authorization": f"Bearer {token_b}"},
            )

        assert res.status_code == 200
        data = res.get_json()
        assert data["data"]["sites"] == [], "tenant_b NÃO deve ver sites do tenant_a"


# ---------------------------------------------------------------------------
# POST /api/v1/edge/sites/<site_id>/enrollment-tokens
# ---------------------------------------------------------------------------

class TestEnrollmentTokens:

    def test_create_token_returns_201_with_plaintext(self, client, app):
        tenant_id = uuid4()
        site_id = uuid4()
        jwt_token = _make_jwt(app, tenant_id)

        site = _mock_site(tenant_id, site_id)
        record = _mock_token_record(site_id, tenant_id)

        mock_repo = MagicMock()
        mock_repo.get_site_by_id.return_value = site
        mock_repo.create_enrollment_token.return_value = record

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                f"/api/v1/edge/sites/{site_id}/enrollment-tokens",
                headers={"Authorization": f"Bearer {jwt_token}"},
            )

        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True
        plaintext = data["data"]["token"]
        assert len(plaintext) > 0

    def test_bank_stores_hash_not_plaintext(self, client, app):
        """Spec eval: assert token_hash != plaintext; hash é SHA-256 do plaintext."""
        tenant_id = uuid4()
        site_id = uuid4()
        jwt_token = _make_jwt(app, tenant_id)

        site = _mock_site(tenant_id, site_id)
        record = _mock_token_record(site_id, tenant_id)

        mock_repo = MagicMock()
        mock_repo.get_site_by_id.return_value = site
        mock_repo.create_enrollment_token.return_value = record

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                f"/api/v1/edge/sites/{site_id}/enrollment-tokens",
                headers={"Authorization": f"Bearer {jwt_token}"},
            )

        assert res.status_code == 201
        plaintext = res.get_json()["data"]["token"]

        call_args = mock_repo.create_enrollment_token.call_args
        stored_hash = call_args.args[2]  # terceiro posicional: token_hash

        assert stored_hash != plaintext, "Banco NÃO deve armazenar o plaintext"
        assert stored_hash == hashlib.sha256(plaintext.encode()).hexdigest()

    def test_token_expires_at_set_used_at_null(self, client, app):
        """expires_at setado na resposta, used_at NULL."""
        tenant_id = uuid4()
        site_id = uuid4()
        jwt_token = _make_jwt(app, tenant_id)

        site = _mock_site(tenant_id, site_id)
        record = _mock_token_record(site_id, tenant_id)

        mock_repo = MagicMock()
        mock_repo.get_site_by_id.return_value = site
        mock_repo.create_enrollment_token.return_value = record

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                f"/api/v1/edge/sites/{site_id}/enrollment-tokens",
                headers={"Authorization": f"Bearer {jwt_token}"},
            )

        data = res.get_json()["data"]
        assert data["used_at"] is None
        assert data["expires_at"] is not None

    def test_cross_tenant_site_returns_404(self, client, app):
        """C-01: site de outro tenant → 404 (não vaza existência)."""
        tenant_a = uuid4()
        site_id_b = uuid4()
        jwt_token = _make_jwt(app, tenant_a)

        mock_repo = MagicMock()
        mock_repo.get_site_by_id.return_value = None  # não pertence ao tenant_a

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                f"/api/v1/edge/sites/{site_id_b}/enrollment-tokens",
                headers={"Authorization": f"Bearer {jwt_token}"},
            )

        assert res.status_code == 404
        mock_repo.create_enrollment_token.assert_not_called()

    def test_get_site_by_id_called_with_jwt_tenant(self, client, app):
        """Validação cross-tenant usa tenant_id do JWT, não do path."""
        tenant_id = uuid4()
        site_id = uuid4()
        jwt_token = _make_jwt(app, tenant_id)

        site = _mock_site(tenant_id, site_id)
        record = _mock_token_record(site_id, tenant_id)

        mock_repo = MagicMock()
        mock_repo.get_site_by_id.return_value = site
        mock_repo.create_enrollment_token.return_value = record

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            client.post(
                f"/api/v1/edge/sites/{site_id}/enrollment-tokens",
                headers={"Authorization": f"Bearer {jwt_token}"},
            )

        mock_repo.get_site_by_id.assert_called_once_with(str(site_id), str(tenant_id))


# ---------------------------------------------------------------------------
# Auth enforcement (sem JWT / role insuficiente)
# ---------------------------------------------------------------------------

class TestAuthEnforcement:

    def test_no_jwt_create_site_returns_401(self, client):
        res = client.post("/api/v1/edge/sites", json={"name": "X", "deployment_mode": "edge"})
        assert res.status_code == 401

    def test_no_jwt_list_sites_returns_401(self, client):
        res = client.get("/api/v1/edge/sites")
        assert res.status_code == 401

    def test_no_jwt_enrollment_token_returns_401(self, client):
        res = client.post(f"/api/v1/edge/sites/{uuid4()}/enrollment-tokens")
        assert res.status_code == 401

    def test_operator_role_create_site_returns_403(self, client, app):
        """Role 'operator' não tem acesso — deve retornar 403."""
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id, role="operator")

        mock_repo = MagicMock()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                "/api/v1/edge/sites",
                json={"name": "X", "deployment_mode": "edge"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 403
        mock_repo.create_site.assert_not_called()

    def test_operator_role_list_sites_returns_403(self, client, app):
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id, role="operator")

        mock_repo = MagicMock()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                "/api/v1/edge/sites",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 403
        mock_repo.list_sites.assert_not_called()

    def test_operator_role_enrollment_token_returns_403(self, client, app):
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id, role="operator")

        mock_repo = MagicMock()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                f"/api/v1/edge/sites/{uuid4()}/enrollment-tokens",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 403
        mock_repo.create_enrollment_token.assert_not_called()
