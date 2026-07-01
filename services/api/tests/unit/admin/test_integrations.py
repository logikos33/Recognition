"""Tests: IntegrationService + IntegrationRepository (unit, sem banco real).

Cobertura obrigatória (task-058):
  test_save_integration_encrypts_secret      — DB tem Fernet, não plaintext
  test_get_integration_masks_secret          — resposta tem last4, não plaintext
  test_list_integrations_no_secrets          — lista não vaza secret_encrypted
  test_superadmin_required                   — 403 para não-superadmin
  test_tenant_isolation                      — tenant A não vê integração de B
  test_test_connection_r2                    — mock boto3, retorna ok/error
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from cryptography.fernet import Fernet
from flask_jwt_extended import create_access_token

from app.domain.services.integration_service import IntegrationService, _mask_row

# ──────────────────────────── fixtures ───────────────────────────────────────

FERNET_KEY = Fernet.generate_key().decode()
TENANT = "11111111-1111-1111-1111-111111111111"


def _make_repo() -> MagicMock:
    return MagicMock()


def _make_service(repo: MagicMock | None = None) -> IntegrationService:
    return IntegrationService(repo or _make_repo())


def _auth_header(app, role: str = "operator") -> dict[str, str]:
    """Gera JWT header para testes de endpoint."""
    with app.app_context():
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT,
                "tenant_schema": "tenant_test",
                "role": role,
            },
        )
    return {"Authorization": f"Bearer {token}"}


# ──────────────────────────── encryption ─────────────────────────────────────

class TestSaveIntegrationEncryptsSecret:
    """secret_encrypted no banco nunca é o plaintext."""

    def test_upsert_called_with_fernet_not_plaintext(self) -> None:
        repo = _make_repo()
        repo.upsert_integration.return_value = {
            "id": str(uuid4()),
            "tenant_id": str(uuid4()),
            "integration_type": "r2",
            "label": "r2",
            "config": {},
            "last4": "1234",
            "status": "unconfigured",
            "last_tested_at": None,
            "last_error": None,
            "created_at": None,
            "updated_at": None,
        }
        svc = _make_service(repo)
        tenant_id = uuid4()

        with patch.dict("os.environ", {"CAMERA_SECRET_KEY": FERNET_KEY}):
            svc.save_integration(tenant_id, "r2", "r2", {}, "super-secret-key-1234")

        call_kwargs = repo.upsert_integration.call_args
        encrypted = call_kwargs.kwargs.get("secret_encrypted") or call_kwargs[1].get("secret_encrypted")

        assert encrypted is not None
        assert encrypted != "super-secret-key-1234"

        # Deve ser descriptografável com a mesma chave Fernet
        fernet = Fernet(FERNET_KEY.encode())
        decrypted = fernet.decrypt(encrypted.encode()).decode()
        assert decrypted == "super-secret-key-1234"

    def test_last4_saved_correctly(self) -> None:
        repo = _make_repo()
        repo.upsert_integration.return_value = {
            "id": str(uuid4()), "tenant_id": str(uuid4()),
            "integration_type": "r2", "label": "r2", "config": {},
            "last4": "1234", "status": "unconfigured",
            "last_tested_at": None, "last_error": None,
            "created_at": None, "updated_at": None,
        }
        svc = _make_service(repo)

        with patch.dict("os.environ", {"CAMERA_SECRET_KEY": FERNET_KEY}):
            result = svc.save_integration(uuid4(), "r2", "r2", {}, "abcd1234")

        # last4 deve ser os últimos 4 chars
        call_kw = repo.upsert_integration.call_args
        last4 = call_kw.kwargs.get("last4") or call_kw[1].get("last4")
        assert last4 == "1234"

        # resposta mascarada
        assert result.get("secret_display") == "••••1234"
        assert "secret_encrypted" not in result


# ──────────────────────────── masking ────────────────────────────────────────

class TestGetIntegrationMasksSecret:
    """API nunca retorna secret_encrypted — apenas ••••last4."""

    def test_mask_row_removes_secret_encrypted(self) -> None:
        row = {
            "id": str(uuid4()),
            "integration_type": "vast_ai",
            "label": "vast_ai",
            "config": {},
            "secret_encrypted": "gAAAAAB_super_sensitive_cipher",
            "last4": "zxcv",
            "status": "ok",
            "last_tested_at": None,
            "last_error": None,
            "created_at": None,
            "updated_at": None,
        }
        masked = _mask_row(row)
        assert "secret_encrypted" not in masked
        assert masked["secret_display"] == "••••zxcv"

    def test_mask_row_none_last4(self) -> None:
        row = {
            "id": str(uuid4()), "integration_type": "r2", "label": "r2",
            "config": {}, "secret_encrypted": None, "last4": None,
            "status": "unconfigured", "last_tested_at": None, "last_error": None,
            "created_at": None, "updated_at": None,
        }
        masked = _mask_row(row)
        assert masked["secret_display"] is None

    def test_get_integration_masks(self) -> None:
        repo = _make_repo()
        repo.get_integration.return_value = {
            "id": str(uuid4()), "integration_type": "r2", "label": "r2",
            "config": {}, "last4": "4321", "status": "ok",
            "last_tested_at": None, "last_error": None,
            "created_at": None, "updated_at": None,
        }
        svc = _make_service(repo)
        result = svc.get_integration(uuid4(), "r2")
        assert result is not None
        assert "secret_encrypted" not in result
        assert result["secret_display"] == "••••4321"


# ──────────────────────────── list no leakage ────────────────────────────────

class TestListIntegrationsNoSecrets:
    """list_integrations nunca vaza secret_encrypted."""

    def test_list_strips_secrets(self) -> None:
        repo = _make_repo()
        repo.list_integrations.return_value = [
            {
                "id": str(uuid4()), "integration_type": "r2", "label": "r2",
                "config": {}, "last4": "aaaa", "status": "ok",
                "last_tested_at": None, "last_error": None,
                "created_at": None, "updated_at": None,
            },
            {
                "id": str(uuid4()), "integration_type": "vast_ai", "label": "vast_ai",
                "config": {}, "last4": "bbbb", "status": "unconfigured",
                "last_tested_at": None, "last_error": None,
                "created_at": None, "updated_at": None,
            },
        ]
        svc = _make_service(repo)
        items = svc.list_integrations(uuid4())
        assert len(items) == 2
        for item in items:
            assert "secret_encrypted" not in item
            assert "secret_display" in item

    def test_list_empty(self) -> None:
        repo = _make_repo()
        repo.list_integrations.return_value = []
        svc = _make_service(repo)
        assert svc.list_integrations(uuid4()) == []


# ──────────────────────────── superadmin guard ───────────────────────────────

class TestSuperadminRequired:
    """Endpoints retornam 403 para não-superadmin (operator role)."""

    def test_list_returns_403_for_operator(self, app, client, monkeypatch) -> None:
        import app.api.v1.admin.integration_routes as ir
        monkeypatch.setattr(ir, "_get_service", lambda: _make_service())
        resp = client.get(
            "/api/v1/admin/integrations/",
            headers=_auth_header(app, role="operator"),
        )
        assert resp.status_code == 403

    def test_upsert_returns_403_for_operator(self, app, client, monkeypatch) -> None:
        import app.api.v1.admin.integration_routes as ir
        monkeypatch.setattr(ir, "_get_service", lambda: _make_service())
        resp = client.put(
            "/api/v1/admin/integrations/r2",
            json={"label": "r2", "config": {}},
            headers=_auth_header(app, role="operator"),
        )
        assert resp.status_code == 403

    def test_test_returns_403_for_operator(self, app, client, monkeypatch) -> None:
        import app.api.v1.admin.integration_routes as ir
        monkeypatch.setattr(ir, "_get_service", lambda: _make_service())
        resp = client.post(
            "/api/v1/admin/integrations/r2/test",
            headers=_auth_header(app, role="operator"),
        )
        assert resp.status_code == 403

    def test_delete_returns_403_for_operator(self, app, client, monkeypatch) -> None:
        import app.api.v1.admin.integration_routes as ir
        monkeypatch.setattr(ir, "_get_service", lambda: _make_service())
        resp = client.delete(
            "/api/v1/admin/integrations/r2",
            headers=_auth_header(app, role="operator"),
        )
        assert resp.status_code == 403


# ──────────────────────────── tenant isolation ───────────────────────────────

class TestTenantIsolation:
    """Tenant A não pode ver integrações do Tenant B."""

    def test_list_filters_by_tenant(self) -> None:
        tenant_a = uuid4()
        tenant_b = uuid4()

        row_a = {
            "id": str(uuid4()), "tenant_id": str(tenant_a),
            "integration_type": "r2", "label": "r2-A", "config": {},
            "last4": "aaaa", "status": "ok",
            "last_tested_at": None, "last_error": None,
            "created_at": None, "updated_at": None,
        }
        row_b = {
            "id": str(uuid4()), "tenant_id": str(tenant_b),
            "integration_type": "r2", "label": "r2-B", "config": {},
            "last4": "bbbb", "status": "ok",
            "last_tested_at": None, "last_error": None,
            "created_at": None, "updated_at": None,
        }

        repo_a = _make_repo()
        repo_a.list_integrations.return_value = [row_a]
        svc_a = _make_service(repo_a)
        items_a = svc_a.list_integrations(tenant_a)

        repo_b = _make_repo()
        repo_b.list_integrations.return_value = [row_b]
        svc_b = _make_service(repo_b)
        items_b = svc_b.list_integrations(tenant_b)

        # Cada repo foi chamado com o próprio tenant_id
        repo_a.list_integrations.assert_called_once_with(tenant_a)
        repo_b.list_integrations.assert_called_once_with(tenant_b)

        assert all(i["label"] == "r2-A" for i in items_a)
        assert all(i["label"] == "r2-B" for i in items_b)

    def test_get_secret_filters_by_tenant(self) -> None:
        """get_secret_encrypted passa tenant_id ao repo — isolamento garantido."""
        repo = _make_repo()
        repo.get_secret_encrypted.return_value = None
        svc = _make_service(repo)

        tenant_a = uuid4()
        svc.get_integration_secret(tenant_a, "r2")

        repo.get_secret_encrypted.assert_called_once_with(tenant_a, "r2")


# ──────────────────────────── R2 connection test ─────────────────────────────

class TestTestConnectionR2:
    """test_r2_connection usa boto3 mockado."""

    def _make_repo_with_r2(self) -> MagicMock:
        repo = _make_repo()
        repo.get_integration.return_value = {
            "id": str(uuid4()),
            "integration_type": "r2",
            "label": "r2",
            "config": {
                "endpoint": "https://account.r2.cloudflarestorage.com",
                "bucket": "test-bucket",
            },
            "last4": "1234",
            "status": "unconfigured",
            "last_tested_at": None,
            "last_error": None,
            "created_at": None,
            "updated_at": None,
        }
        repo.get_secret_encrypted.return_value = None
        return repo

    def test_r2_ok(self) -> None:
        tenant_id = uuid4()
        repo = self._make_repo_with_r2()
        svc = _make_service(repo)

        with patch.dict("os.environ", {
            "CAMERA_SECRET_KEY": FERNET_KEY,
            "R2_ACCESS_KEY_ID": "access-key",
            "R2_SECRET_ACCESS_KEY": "secret-key",
        }):
            with patch(
                "app.domain.services.integration_service.boto3"
            ) as mock_boto3:
                mock_s3 = MagicMock()
                mock_boto3.client.return_value = mock_s3
                mock_s3.head_bucket.return_value = {}

                result = svc.test_r2_connection(tenant_id)

        assert result["ok"] is True
        assert result["error"] is None
        repo.update_status.assert_called_once()
        call_args = repo.update_status.call_args[0]
        assert call_args[1] == "ok"

    def test_r2_error(self) -> None:
        from botocore.exceptions import ClientError

        tenant_id = uuid4()
        repo = self._make_repo_with_r2()
        svc = _make_service(repo)

        with patch.dict("os.environ", {
            "CAMERA_SECRET_KEY": FERNET_KEY,
            "R2_ACCESS_KEY_ID": "access-key",
            "R2_SECRET_ACCESS_KEY": "secret-key",
        }):
            with patch(
                "app.domain.services.integration_service.boto3"
            ) as mock_boto3:
                mock_s3 = MagicMock()
                mock_boto3.client.return_value = mock_s3
                error_response = {"Error": {"Code": "403", "Message": "Forbidden"}}
                mock_s3.head_bucket.side_effect = ClientError(error_response, "HeadBucket")

                result = svc.test_r2_connection(tenant_id)

        assert result["ok"] is False
        assert result["error"] is not None
        call_args = repo.update_status.call_args[0]
        assert call_args[1] == "error"

    def test_r2_not_configured(self) -> None:
        tenant_id = uuid4()
        repo = _make_repo()
        repo.get_integration.return_value = None
        svc = _make_service(repo)

        with patch.dict("os.environ", {"CAMERA_SECRET_KEY": FERNET_KEY}):
            result = svc.test_r2_connection(tenant_id)

        assert result["ok"] is False
        assert "não configurada" in (result["error"] or "")
