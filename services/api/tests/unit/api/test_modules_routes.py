"""
Tests: PATCH /api/modules/<module_code>/classes/<class_id> (task-073/achado #6).

Vulnerabilidade original (docs/API_CONTRACT_MAP.md achado #6): o endpoint não
filtrava por tenant_id nem checava role — qualquer usuário autenticado de
qualquer tenant podia ativar/desativar qualquer classe globalmente (200).

Fix (task-073): permissão `modules:write` + isolamento por tenant via
tenant_modules (module_classes é catálogo global sem tenant_id — o isolamento
possível é "o tenant tem o módulo habilitado" + "o class_id realmente pertence
a module_code"). Qualquer falha de escopo → 404 (nunca 403 — C-01).

Endurecimento (grupo MÓDULOS, P0): como o catálogo é GLOBAL, `modules:write`
(admin) ainda deixava um admin de um tenant desativar a classe para TODOS os
tenants. Agora a rota é SÓ superadmin (require_superadmin_or_404): qualquer
outro role → 404 sem tocar no repositório (ver
tests/security/test_module_classes_catalog_gate.py).

Estes testes rodam o ModuleService real (só o repository é mockado) para
provar o comportamento fim-a-fim do gate, não apenas a chamada mockada.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

_REPO_PATH = "app.domain.services.module_service._get_module_repo"


def _make_token(app, role="admin", tenant_id=None, user_id=None):
    uid = user_id or uuid4()
    tid = tenant_id or str(uuid4())
    with app.app_context():
        token = create_access_token(
            identity=str(uid),
            additional_claims={
                "role": role,
                "tenant_id": tid,
                "tenant_schema": "public",
            },
        )
    return token, uid, tid


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestToggleModuleClassPermission:
    """Não-superadmin → 404 (catálogo global de plataforma; C-01), mesmo no
    próprio tenant e mesmo admin."""

    def test_operator_denied_404(self, client, app):
        token, _uid, _tid = _make_token(app, role="operator")
        mock_repo = MagicMock()
        with patch(_REPO_PATH, return_value=mock_repo):
            res = client.patch(
                "/api/modules/epi/classes/cls-1",
                json={"is_active": False},
                headers=_headers(token),
            )
        assert res.status_code == 404
        assert res.get_json()["success"] is False
        mock_repo.toggle_class_active.assert_not_called()

    def test_viewer_denied_404(self, client, app):
        token, _uid, _tid = _make_token(app, role="viewer")
        mock_repo = MagicMock()
        with patch(_REPO_PATH, return_value=mock_repo):
            res = client.patch(
                "/api/modules/epi/classes/cls-1",
                json={"is_active": False},
                headers=_headers(token),
            )
        assert res.status_code == 404
        mock_repo.toggle_class_active.assert_not_called()

    def test_admin_denied_404_catalog_is_global(self, client, app):
        """Admin de tenant NÃO pode mais mutar o catálogo global (afetaria
        todos os tenants) — 404 e repositório intocado."""
        token, _uid, _tid = _make_token(app, role="admin")
        mock_repo = MagicMock()
        mock_repo.get_tenant_module.return_value = {"enabled": True}
        with patch(_REPO_PATH, return_value=mock_repo):
            res = client.patch(
                "/api/modules/epi/classes/cls-1",
                json={"is_active": False},
                headers=_headers(token),
            )
        assert res.status_code == 404
        mock_repo.toggle_class_active.assert_not_called()

    def test_no_jwt_returns_401_or_422(self, client):
        res = client.patch("/api/modules/epi/classes/cls-1", json={"is_active": False})
        assert res.status_code in (401, 422)


class TestToggleModuleClassTenantIsolation:
    """task-073: classe de módulo/tenant alheio → 404 (nunca 403 — C-01)."""

    def test_cross_tenant_module_not_enabled_returns_404(self, client, app):
        """Tenant A (superadmin no contexto de A) não tem o módulo 'fueling'
        habilitado; tenta togglar uma classe que pertence ao módulo 'fueling'
        de outro tenant → 404. Antes do fix: 200 (vulnerabilidade original)."""
        token, _uid, tenant_a = _make_token(app, role="superadmin")
        mock_repo = MagicMock()
        # tenant_has_module(tenant_a, "fueling") → False: tenant A não tem o módulo
        mock_repo.get_tenant_module.return_value = None
        with patch(_REPO_PATH, return_value=mock_repo):
            res = client.patch(
                "/api/modules/fueling/classes/fueling-class-de-outro-tenant",
                json={"is_active": False},
                headers=_headers(token),
            )
        assert res.status_code == 404
        assert res.get_json()["success"] is False
        mock_repo.toggle_class_active.assert_not_called()

    def test_class_id_from_other_module_returns_404(self, client, app):
        """Tenant TEM o módulo 'epi' habilitado, mas o class_id informado
        pertence a outro module_code — UPDATE filtrado por module_code no
        repository não encontra a linha → 404."""
        token, _uid, _tid = _make_token(app, role="superadmin")
        mock_repo = MagicMock()
        mock_repo.get_tenant_module.return_value = {"enabled": True}
        mock_repo.toggle_class_active.return_value = None  # WHERE module_code não bate
        with patch(_REPO_PATH, return_value=mock_repo):
            res = client.patch(
                "/api/modules/epi/classes/classe-de-outro-modulo",
                json={"is_active": False},
                headers=_headers(token),
            )
        assert res.status_code == 404
        mock_repo.toggle_class_active.assert_called_once_with(
            "epi", "classe-de-outro-modulo", False
        )

    def test_disabled_module_for_own_tenant_returns_404(self, client, app):
        """Módulo existe para o tenant mas está desabilitado (enabled=False)
        → mesmo tratamento de 404 (tenant_has_module fail-closed)."""
        token, _uid, _tid = _make_token(app, role="superadmin")
        mock_repo = MagicMock()
        mock_repo.get_tenant_module.return_value = {"enabled": False}
        with patch(_REPO_PATH, return_value=mock_repo):
            res = client.patch(
                "/api/modules/fueling/classes/cls-1",
                json={"is_active": True},
                headers=_headers(token),
            )
        assert res.status_code == 404
        mock_repo.toggle_class_active.assert_not_called()


class TestToggleModuleClassHappyPath:
    """Superadmin, módulo habilitado no contexto, classe pertence ao módulo → 200."""

    def test_superadmin_toggles_module_class_200(self, client, app):
        token, _uid, _tid = _make_token(app, role="superadmin")
        mock_repo = MagicMock()
        mock_repo.get_tenant_module.return_value = {"enabled": True}
        mock_repo.toggle_class_active.return_value = {
            "id": "cls-1", "module_code": "epi", "is_active": False,
        }
        with patch(_REPO_PATH, return_value=mock_repo):
            res = client.patch(
                "/api/modules/epi/classes/cls-1",
                json={"is_active": False},
                headers=_headers(token),
            )
        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        assert body["data"]["class"]["is_active"] is False
        mock_repo.toggle_class_active.assert_called_once_with("epi", "cls-1", False)

    def test_superadmin_passes_gate(self, client, app):
        """Superadmin é o único role que passa no gate do catálogo global."""
        token, _uid, _tid = _make_token(app, role="superadmin")
        mock_repo = MagicMock()
        mock_repo.get_tenant_module.return_value = {"enabled": True}
        mock_repo.toggle_class_active.return_value = {"id": "cls-1", "is_active": True}
        with patch(_REPO_PATH, return_value=mock_repo):
            res = client.patch(
                "/api/modules/epi/classes/cls-1",
                json={"is_active": True},
                headers=_headers(token),
            )
        assert res.status_code == 200
