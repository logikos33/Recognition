"""
Segurança — PATCH /api/modules/<module_code>/classes/<class_id> restrito a
superadmin (catálogo GLOBAL de plataforma).

Achado (c), grupo MÓDULOS (P0): a rota escrevia em public.module_classes
(catálogo global, SEM tenant_id — module_repository.toggle_class_active) com
gate has_permission('modules:write') = admin/superadmin. Um admin de um
tenant desativava a classe para TODOS os tenants.

Fix: só superadmin. Não-superadmin recebe 404 — mesma convenção do blueprint
quando o módulo não está habilitado para o tenant (nunca 403, C-01) — e o
repositório não é chamado. Classes custom por tenant continuam em /api/classes.

Protocolo falha-antes/passa-depois: admin → 404 e repo não chamado (antes 200
mutando o catálogo global); superadmin → 200.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

_REPO_PATH = "app.domain.services.module_service._get_module_repo"


def _auth(app, role: str) -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "role": role,
                "tenant_id": str(uuid4()),
                "tenant_schema": "tenant_test",
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def module_repo():
    repo = MagicMock()
    repo.get_tenant_module.return_value = {"enabled": True}
    repo.toggle_class_active.return_value = {
        "id": "cls-1", "module_code": "epi", "is_active": False,
    }
    with patch(_REPO_PATH, return_value=repo):
        yield repo


class TestToggleModuleClassSuperadminOnly:
    @pytest.mark.parametrize("role", ["admin", "operator", "viewer", "trainer"])
    def test_non_superadmin_gets_404_and_catalog_untouched(
        self, app, client, module_repo, role
    ):
        """FALHA-ANTES (admin): 200 e UPDATE no catálogo global de TODOS os
        tenants. PASSA-DEPOIS: 404 (convenção do blueprint, C-01) e o
        repositório não é chamado."""
        resp = client.patch(
            "/api/modules/epi/classes/cls-1",
            json={"is_active": False},
            headers=_auth(app, role),
        )
        assert resp.status_code == 404, resp.get_json()
        assert resp.get_json()["success"] is False
        module_repo.toggle_class_active.assert_not_called()

    def test_superadmin_toggles_catalog_class(self, app, client, module_repo):
        resp = client.patch(
            "/api/modules/epi/classes/cls-1",
            json={"is_active": False},
            headers=_auth(app, "superadmin"),
        )
        assert resp.status_code == 200, resp.get_json()
        assert resp.get_json()["data"]["class"]["is_active"] is False
        module_repo.toggle_class_active.assert_called_once_with("epi", "cls-1", False)
