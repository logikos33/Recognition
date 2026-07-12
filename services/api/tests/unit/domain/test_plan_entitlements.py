"""
Testes — Entitlements do plano (WS8).

Cobertura:
  - get_seat_policy herda plans.max_users via COALESCE (falha-antes/passa-depois)
  - check_seat_available lança ConflictError quando o limite herdado é atingido
  - tenant_has_module com flag enforce_plan_limits ON nega módulo fora de
    plans.modules_allowed; flag OFF preserva comportamento atual
  - fail-open: sem entitlements / modules_allowed vazio = sem restrição
  - create_camera: cap de câmeras do plano → 409 com flag ON, passa com flag OFF
"""
import uuid
from unittest.mock import MagicMock

import pytest
from flask_jwt_extended import create_access_token

from app.core.exceptions import ConflictError
from app.domain.services.seat_service import check_seat_available
from app.infrastructure.database.repositories.tenant_policy_repository import (
    TenantPolicyRepository,
)

TENANT_ID = str(uuid.uuid4())


# ── Seat policy: herança plano → tenant ──────────────────────────────────────

class TestSeatPolicyInheritance:
    def test_get_seat_policy_uses_coalesce_with_plan_max_users(self, monkeypatch):
        """Falha-antes/passa-depois: query antiga não fazia join com plans."""
        repo = TenantPolicyRepository(MagicMock())
        captured: dict = {}

        def fake_execute_one(query, params):
            captured["query"] = query
            # Simula t.max_seats NULL e p.max_users=3 → COALESCE devolve 3
            return {"max_seats": 3, "single_session": False}

        monkeypatch.setattr(repo, "_execute_one", fake_execute_one)
        policy = repo.get_seat_policy(TENANT_ID)

        assert policy["max_seats"] == 3
        assert "COALESCE(t.max_seats, p.max_users)" in captured["query"]
        assert "LEFT JOIN plans p ON p.slug = t.plan" in captured["query"]

    def test_check_seat_available_raises_on_inherited_limit(self):
        policy_repo = MagicMock()
        policy_repo.get_seat_policy.return_value = {"max_seats": 3, "single_session": False}
        policy_repo.count_active_users.return_value = 3

        with pytest.raises(ConflictError):
            check_seat_available(policy_repo, TENANT_ID)

    def test_check_seat_available_allows_below_limit(self):
        policy_repo = MagicMock()
        policy_repo.get_seat_policy.return_value = {"max_seats": 3, "single_session": False}
        policy_repo.count_active_users.return_value = 2

        result = check_seat_available(policy_repo, TENANT_ID)
        assert result == {"used": 2, "max": 3}

    def test_null_everywhere_means_unlimited(self):
        policy_repo = MagicMock()
        policy_repo.get_seat_policy.return_value = {"max_seats": None, "single_session": False}
        policy_repo.count_active_users.return_value = 999

        result = check_seat_available(policy_repo, TENANT_ID)
        assert result["max"] is None

    def test_get_plan_entitlements_query_shape(self, monkeypatch):
        repo = TenantPolicyRepository(MagicMock())
        captured: dict = {}

        def fake_execute_one(query, params):
            captured["query"] = query
            return {
                "modules_allowed": ["basic"],
                "module_features": {},
                "max_cameras_plan": 5,
                "tenant_max_cameras": None,
            }

        monkeypatch.setattr(repo, "_execute_one", fake_execute_one)
        ent = repo.get_plan_entitlements(TENANT_ID)

        assert ent["max_cameras_plan"] == 5
        assert "modules_allowed" in captured["query"]
        assert "module_features" in captured["query"]
        assert "contract_cameras" in captured["query"]


# ── Module gating atrás da flag enforce_plan_limits ──────────────────────────

def _setup_module_service(monkeypatch, *, flag_on, modules_allowed, enabled=True):
    import app.domain.services.module_service as ms

    monkeypatch.setattr(ms, "platform_flag_enabled", lambda key: flag_on)

    module_repo = MagicMock()
    module_repo.get_tenant_module.return_value = (
        {"module_code": "epi", "enabled": enabled} if enabled is not None else None
    )
    module_repo.get_by_tenant.return_value = [
        {"module_code": "epi", "enabled": True},
        {"module_code": "basic", "enabled": True},
    ]
    monkeypatch.setattr(ms, "_get_module_repo", lambda: module_repo)

    policy_repo = MagicMock()
    policy_repo.get_plan_entitlements.return_value = (
        None if modules_allowed == "no-tenant" else {
            "modules_allowed": modules_allowed,
            "module_features": {},
            "max_cameras_plan": 5,
            "tenant_max_cameras": None,
        }
    )
    monkeypatch.setattr(ms, "_get_policy_repo", lambda: policy_repo)
    return ms


class TestModuleGating:
    def test_flag_on_denies_module_outside_plan(self, monkeypatch):
        """Falha-antes/passa-depois: sem gating, tenant_modules.enabled bastava."""
        ms = _setup_module_service(monkeypatch, flag_on=True, modules_allowed=["basic"])
        assert ms.module_service.tenant_has_module(TENANT_ID, "epi") is False

    def test_flag_off_preserves_current_behavior(self, monkeypatch):
        ms = _setup_module_service(monkeypatch, flag_on=False, modules_allowed=["basic"])
        assert ms.module_service.tenant_has_module(TENANT_ID, "epi") is True

    def test_flag_on_allows_module_in_plan(self, monkeypatch):
        ms = _setup_module_service(monkeypatch, flag_on=True, modules_allowed=["epi", "basic"])
        assert ms.module_service.tenant_has_module(TENANT_ID, "epi") is True

    def test_fail_open_empty_modules_allowed(self, monkeypatch):
        ms = _setup_module_service(monkeypatch, flag_on=True, modules_allowed=[])
        assert ms.module_service.tenant_has_module(TENANT_ID, "epi") is True

    def test_fail_open_missing_tenant(self, monkeypatch):
        ms = _setup_module_service(monkeypatch, flag_on=True, modules_allowed="no-tenant")
        assert ms.module_service.tenant_has_module(TENANT_ID, "epi") is True

    def test_disabled_module_stays_disabled_regardless_of_flag(self, monkeypatch):
        ms = _setup_module_service(monkeypatch, flag_on=False, modules_allowed=["epi"], enabled=False)
        assert ms.module_service.tenant_has_module(TENANT_ID, "epi") is False

    def test_list_tenant_modules_filters_with_flag_on(self, monkeypatch):
        ms = _setup_module_service(monkeypatch, flag_on=True, modules_allowed=["basic"])
        monkeypatch.setattr(
            ms.module_service, "get_stats",
            lambda tenant_id, module_code: {},
        )
        modules = ms.module_service.list_tenant_modules(TENANT_ID)
        assert [m["module_code"] for m in modules] == ["basic"]

    def test_list_tenant_modules_unfiltered_with_flag_off(self, monkeypatch):
        ms = _setup_module_service(monkeypatch, flag_on=False, modules_allowed=["basic"])
        monkeypatch.setattr(
            ms.module_service, "get_stats",
            lambda tenant_id, module_code: {},
        )
        modules = ms.module_service.list_tenant_modules(TENANT_ID)
        assert [m["module_code"] for m in modules] == ["epi", "basic"]


# ── Cap de câmeras no POST /api/cameras ──────────────────────────────────────

def _camera_auth_header(app):
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "tenant_test",
                "role": "admin",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _setup_camera_handlers(monkeypatch, *, flag_on, current_cameras, cap):
    import app.api.v1.cameras.crud_handlers as ch

    monkeypatch.setattr(ch, "platform_flag_enabled", lambda key: flag_on)
    monkeypatch.setattr(
        ch, "DatabasePool",
        MagicMock(get_instance=MagicMock(return_value=MagicMock())),
    )

    policy_repo = MagicMock()
    policy_repo.get_plan_entitlements.return_value = {
        "modules_allowed": None,
        "module_features": None,
        "max_cameras_plan": cap,
        "tenant_max_cameras": None,
    }
    monkeypatch.setattr(ch, "TenantPolicyRepository", lambda pool: policy_repo)

    camera_repo = MagicMock()
    camera_repo.count_all.return_value = current_cameras
    monkeypatch.setattr(ch, "CameraRepository", lambda pool: camera_repo)

    service = MagicMock()
    service.create_camera.return_value = {"id": str(uuid.uuid4()), "name": "Cam"}
    monkeypatch.setattr(ch, "_get_camera_service", lambda: service)
    return service


class TestCameraCapEnforcement:
    def test_flag_on_above_cap_returns_409(self, app, client, monkeypatch):
        service = _setup_camera_handlers(monkeypatch, flag_on=True, current_cameras=5, cap=5)
        resp = client.post(
            "/api/cameras",
            json={"name": "Nova", "host": "10.0.0.1"},
            headers=_camera_auth_header(app),
        )
        assert resp.status_code == 409
        assert "Limite de câmeras do plano atingido" in resp.get_json()["error"]
        service.create_camera.assert_not_called()

    def test_flag_on_below_cap_creates(self, app, client, monkeypatch):
        service = _setup_camera_handlers(monkeypatch, flag_on=True, current_cameras=4, cap=5)
        resp = client.post(
            "/api/cameras",
            json={"name": "Nova", "host": "10.0.0.1"},
            headers=_camera_auth_header(app),
        )
        assert resp.status_code == 201
        service.create_camera.assert_called_once()

    def test_flag_off_skips_cap_check(self, app, client, monkeypatch):
        service = _setup_camera_handlers(monkeypatch, flag_on=False, current_cameras=99, cap=5)
        resp = client.post(
            "/api/cameras",
            json={"name": "Nova", "host": "10.0.0.1"},
            headers=_camera_auth_header(app),
        )
        assert resp.status_code == 201
        service.create_camera.assert_called_once()

    def test_flag_on_without_cap_is_fail_open(self, app, client, monkeypatch):
        service = _setup_camera_handlers(monkeypatch, flag_on=True, current_cameras=99, cap=None)
        resp = client.post(
            "/api/cameras",
            json={"name": "Nova", "host": "10.0.0.1"},
            headers=_camera_auth_header(app),
        )
        assert resp.status_code == 201
        service.create_camera.assert_called_once()
