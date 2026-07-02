"""
Segurança — PATCH /api/cameras/<id>/config escopado pelo tenant do JWT (WS10).

Bug corrigido (mesma classe do commit f6df666): camera_service.patch_config
comparava camera.tenant_id com o user_id do JWT e usava user_id como filtro
de tenant no UPDATE. Para operator/viewer cujo user_id != tenant_id, o PATCH
falhava com 403/404 mesmo sendo do tenant dono da câmera.

Protocolo do mutirão de segurança — testes falha-antes/passa-depois:
  (a) operator do tenant da câmera consegue PATCH → 200 e persiste
      (ANTES do fix: 403, pois user_id != tenant_id);
  (b) usuário de outro tenant → 403/404 (nunca 200);
  (c) admin/superadmin mantêm override cross-tenant.
"""
import uuid
from unittest.mock import MagicMock

import pytest
from flask_jwt_extended import create_access_token

import app.api.v1.cameras.config_handler as config_handler
from app.domain.services.camera_service import CameraService

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"
CAMERA_ID = "44444444-4444-4444-4444-444444444444"


def _auth(app, role: str, tenant_id: str) -> dict[str, str]:
    """JWT com user_id aleatório — user_id NUNCA é igual ao tenant_id."""
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": tenant_id,
                "tenant_schema": "tenant_test",
                "role": role,
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _camera_row(tenant_id: str = TENANT_A, site_id: str | None = None) -> dict:
    return {
        "id": CAMERA_ID,
        "tenant_id": tenant_id,
        "name": "Cam Portaria",
        "site_id": site_id,
        "fps_target": 5,
        "quality_preset": "medium",
    }


@pytest.fixture()
def mocked_service(monkeypatch):
    """CameraService REAL com repositório mockado — testa a lógica de permissão."""
    camera_repo = MagicMock()
    camera_repo.get_by_id.return_value = _camera_row()
    camera_repo.update_config.return_value = {
        **_camera_row(),
        "fps_target": 10,
    }
    service = CameraService(camera_repo, fernet_key="")
    monkeypatch.setattr(config_handler, "_get_camera_service", lambda: service)
    # Propagação não é o foco aqui — câmera sem site_id => no_site (sem repo).
    # raising=False: permite rodar o teste contra o código PRÉ-fix (falha-antes),
    # onde _get_edge_command_repo ainda não existia.
    monkeypatch.setattr(
        config_handler, "_get_edge_command_repo", lambda: MagicMock(), raising=False
    )
    return camera_repo


class TestPatchConfigTenantScope:
    """Isolamento multi-tenant do PATCH /config (C-01)."""

    def test_operator_of_camera_tenant_can_patch(self, app, client, mocked_service):
        """FALHA-ANTES/PASSA-DEPOIS: operator do tenant (user_id != tenant_id) → 200."""
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"fps_target": 10, "quality_preset": "medium"},
            headers=_auth(app, "operator", TENANT_A),
        )
        assert resp.status_code == 200, (
            f"Operator do próprio tenant deve conseguir PATCH (got {resp.status_code}) "
            "— regressão do bug tenant_id vs user_id (f6df666)"
        )
        # UPDATE escopado pelo tenant da câmera, nunca pelo user_id do JWT
        _, tenant_filter, _, _ = mocked_service.update_config.call_args[0]
        assert tenant_filter == TENANT_A

    def test_user_of_other_tenant_cannot_patch(self, app, client, mocked_service):
        """Usuário de outro tenant → 403/404, nunca 200 (C-01)."""
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"fps_target": 10, "quality_preset": "medium"},
            headers=_auth(app, "operator", TENANT_B),
        )
        assert resp.status_code in (403, 404)
        mocked_service.update_config.assert_not_called()

    def test_viewer_of_other_tenant_cannot_patch(self, app, client, mocked_service):
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"fps_target": 10, "quality_preset": "medium"},
            headers=_auth(app, "viewer", TENANT_B),
        )
        assert resp.status_code in (403, 404)

    def test_admin_override_cross_tenant(self, app, client, mocked_service):
        """Admin de outro tenant mantém override (role do JWT, não consulta DB)."""
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"fps_target": 10, "quality_preset": "medium"},
            headers=_auth(app, "admin", TENANT_B),
        )
        assert resp.status_code == 200
        # Mesmo no override, o UPDATE filtra pelo tenant REAL da câmera
        _, tenant_filter, _, _ = mocked_service.update_config.call_args[0]
        assert tenant_filter == TENANT_A

    def test_superadmin_override_cross_tenant(self, app, client, mocked_service):
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"fps_target": 10, "quality_preset": "medium"},
            headers=_auth(app, "superadmin", TENANT_B),
        )
        assert resp.status_code == 200

    def test_no_auth_returns_401(self, client, mocked_service):
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/config",
            json={"fps_target": 10, "quality_preset": "medium"},
        )
        assert resp.status_code == 401

    def test_v1_alias_also_tenant_scoped(self, app, client, mocked_service):
        """Alias /api/v1/cameras/<id>/config aplica o mesmo escopo."""
        resp = client.patch(
            f"/api/v1/cameras/{CAMERA_ID}/config",
            json={"fps_target": 10, "quality_preset": "medium"},
            headers=_auth(app, "operator", TENANT_B),
        )
        assert resp.status_code in (403, 404)
