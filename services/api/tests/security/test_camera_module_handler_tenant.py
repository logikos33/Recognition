"""
Segurança — isolamento multi-tenant (C-01) em cameras/module_handler.py (achado P1).

Bug: os 3 handlers (patch_camera_module, put_camera_schedule,
get_camera_module_current) buscavam a câmera via `repo.get_by_id(camera_id)` —
sem filtro de tenant — e nunca comparavam `camera["tenant_id"]` com o tenant do
JWT. Qualquer usuário autenticado podia ler/escrever módulo e agendamento de
câmeras de OUTRO tenant, bastando saber o UUID.

Fix: troca para `repo.get_by_id_and_tenant(camera_id, tenant_id)` — mesmo
método já usado por retention_handler/health_context_handler/
model_config_handlers/scenarios routes.py. Câmera de outro tenant não é
encontrada → NotFoundError → 404 (não vaza existência, C-01).

Testes falha-antes/passa-depois: dono do tenant → 200; outro tenant → 404.
"""
import uuid
from unittest.mock import MagicMock

import pytest
from flask_jwt_extended import create_access_token

import app.api.v1.cameras.module_handler as module_handler

TENANT_A = str(uuid.uuid4())
TENANT_B = str(uuid.uuid4())
CAMERA_ID = str(uuid.uuid4())


def _auth(app, tenant_id: str) -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": tenant_id,
                "tenant_schema": "tenant_test",
                # admin: PATCH /module e PUT /schedule passaram a exigir
                # cameras:configure (superadmin, admin) — mesma chave que
                # o irmão em lote PUT /api/cameras/modules já usava. Só o
                # papel do token muda; as asserções de escopo por tenant
                # (404 cross-tenant, C-01) são as mesmas.
                "role": "admin",
                "modules": ["epi", "quality", "counting"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _camera_row(tenant_id: str = TENANT_A) -> dict:
    return {
        "id": CAMERA_ID,
        "tenant_id": tenant_id,
        "active_module": "epi",
        "schedule_rules": [],
    }


@pytest.fixture()
def mocked_repo(monkeypatch):
    """CameraRepository mockado — get_by_id_and_tenant só acha câmeras do TENANT_A."""
    repo = MagicMock()

    def _get_by_id_and_tenant(camera_id, tenant_id):
        if str(tenant_id) == TENANT_A:
            return _camera_row(TENANT_A)
        return None

    repo.get_by_id_and_tenant.side_effect = _get_by_id_and_tenant
    monkeypatch.setattr(module_handler, "_get_camera_repo", lambda: repo)
    monkeypatch.setattr(module_handler, "_is_module_allowed", lambda module: True)
    monkeypatch.setattr(module_handler, "_notify_module_changed", lambda *a, **k: None)
    return repo


class TestPatchModuleTenantScope:
    def test_same_tenant_can_patch(self, app, client, mocked_repo):
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/module",
            json={"module": "quality"},
            headers=_auth(app, TENANT_A),
        )
        assert resp.status_code == 200
        mocked_repo.update_module.assert_called_once_with(CAMERA_ID, "quality")

    def test_other_tenant_cannot_patch(self, app, client, mocked_repo):
        resp = client.patch(
            f"/api/cameras/{CAMERA_ID}/module",
            json={"module": "quality"},
            headers=_auth(app, TENANT_B),
        )
        assert resp.status_code == 404, (
            f"IDOR cross-tenant: outro tenant conseguiu alterar module (got {resp.status_code})"
        )
        mocked_repo.update_module.assert_not_called()


class TestPutScheduleTenantScope:
    def test_same_tenant_can_put_schedule(self, app, client, mocked_repo):
        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/schedule",
            json={"rules": []},
            headers=_auth(app, TENANT_A),
        )
        assert resp.status_code == 200
        mocked_repo.update_schedule.assert_called_once()

    def test_other_tenant_cannot_put_schedule(self, app, client, mocked_repo):
        resp = client.put(
            f"/api/cameras/{CAMERA_ID}/schedule",
            json={"rules": []},
            headers=_auth(app, TENANT_B),
        )
        assert resp.status_code == 404, (
            f"IDOR cross-tenant: outro tenant conseguiu escrever schedule (got {resp.status_code})"
        )
        mocked_repo.update_schedule.assert_not_called()


class TestGetModuleCurrentTenantScope:
    def test_same_tenant_can_read(self, app, client, mocked_repo):
        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/module/current",
            headers=_auth(app, TENANT_A),
        )
        assert resp.status_code == 200

    def test_other_tenant_cannot_read(self, app, client, mocked_repo):
        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/module/current",
            headers=_auth(app, TENANT_B),
        )
        assert resp.status_code == 404, (
            f"IDOR cross-tenant: outro tenant leu module/schedule alheio (got {resp.status_code})"
        )
