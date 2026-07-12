"""
Tests for task-022: Scenario API (read-only).

GET /api/v1/cameras/<camera_id>/scenario
GET /api/v1/scenarios/operation-types?module=<code>

Eval cases (spec):
  1. seed (câmera + módulo + operação + regra + agenda) → cenário composto corretamente
  2. isolamento: câmera de outro tenant → 404 (C-01)
  3. resposta nunca inclui dado de outro tenant (cross-tenant)
  4. operation-types: lista tipos do módulo com config_schema
  5. módulo inválido → lista vazia/coerente (sem 5xx)
  6. sem JWT → 401

Mocked tests (classes TestGetCameraScenarioMocked, TestListOperationTypesMocked) — sempre rodam.
Real-DB tests (class TestScenarioIntegration) — pulados se INTEGRATION_DATABASE_URL não definida.
"""
import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jwt(app, tenant_id, role: str = "admin") -> str:
    with app.app_context():
        return create_access_token(
            identity=str(uuid4()),
            additional_claims={"tenant_id": str(tenant_id), "role": role},
        )


def _mock_camera(tenant_id, camera_id=None):
    cid = str(camera_id or uuid4())
    return {
        "id": cid,
        "tenant_id": str(tenant_id),
        "name": "Camera Test",
        "site_id": None,
        "active_module": "epi",
        "schedule_rules": [],
    }


# ---------------------------------------------------------------------------
# Route tests — mocked repos (always run)
# ---------------------------------------------------------------------------

class TestGetCameraScenarioMocked:

    def test_no_jwt_returns_401(self, client):
        res = client.get(f"/api/v1/cameras/{uuid4()}/scenario")
        assert res.status_code == 401

    def test_camera_not_found_returns_404(self, client, app):
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_cam_repo = MagicMock()
        mock_cam_repo.get_by_id_and_tenant.return_value = None

        with patch("app.api.v1.scenarios.routes._get_camera_repo", return_value=mock_cam_repo):
            res = client.get(
                f"/api/v1/cameras/{uuid4()}/scenario",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 404

    def test_cross_tenant_camera_returns_404(self, client, app):
        """C-01: câmera de outro tenant → 404 (repo não retorna nada cross-tenant)."""
        tenant_a = uuid4()
        token = _make_jwt(app, tenant_a)

        mock_cam_repo = MagicMock()
        mock_cam_repo.get_by_id_and_tenant.return_value = None  # tenant mismatch

        with patch("app.api.v1.scenarios.routes._get_camera_repo", return_value=mock_cam_repo):
            res = client.get(
                f"/api/v1/cameras/{uuid4()}/scenario",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 404

    def test_tenant_id_from_jwt_passed_to_repo(self, client, app):
        """C-01: tenant_id extraído do JWT, nunca do path/body."""
        tenant_id = uuid4()
        camera_id = str(uuid4())
        token = _make_jwt(app, tenant_id)

        mock_cam_repo = MagicMock()
        mock_cam_repo.get_by_id_and_tenant.return_value = None

        with patch("app.api.v1.scenarios.routes._get_camera_repo", return_value=mock_cam_repo):
            client.get(
                f"/api/v1/cameras/{camera_id}/scenario",
                headers={"Authorization": f"Bearer {token}"},
            )

        call_args = mock_cam_repo.get_by_id_and_tenant.call_args
        assert call_args.args[0] == camera_id
        assert call_args.args[1] == str(tenant_id)

    def test_composes_all_scenario_parts(self, client, app):
        tenant_id = uuid4()
        camera_id = str(uuid4())
        token = _make_jwt(app, tenant_id)

        camera = _mock_camera(tenant_id, camera_id)
        camera["schedule_rules"] = [
            {"days": [1, 2, 3], "start": "08:00", "end": "18:00", "module": "epi"}
        ]

        mock_cam_repo = MagicMock()
        mock_cam_repo.get_by_id_and_tenant.return_value = camera

        mock_mod_repo = MagicMock()
        mock_mod_repo.get_by_tenant.return_value = [
            {
                "module_code": "epi",
                "enabled": True,
                "config": {},
                "activated_at": None,
                "expires_at": None,
            }
        ]
        mock_mod_repo.get_classes.return_value = [
            {
                "id": str(uuid4()),
                "module_code": "epi",
                "class_id": 0,
                "class_name": "helmet",
                "is_active": True,
            }
        ]

        mock_op_repo = MagicMock()
        mock_op_repo.list_by_camera.return_value = [
            {"id": 1, "type_id": "position", "name": "Zona EPI", "config": {}, "status": "active"}
        ]

        mock_alert_repo = MagicMock()
        mock_alert_repo.list_for_camera_scenario.return_value = [
            {
                "id": str(uuid4()),
                "tenant_id": str(tenant_id),
                "violation_type": "no_helmet",
                "camera_id": camera_id,
                "enabled": True,
            }
        ]

        with (
            patch("app.api.v1.scenarios.routes._get_camera_repo", return_value=mock_cam_repo),
            patch("app.api.v1.scenarios.routes._get_module_repo", return_value=mock_mod_repo),
            patch("app.api.v1.scenarios.routes._get_operation_repo", return_value=mock_op_repo),
            patch("app.api.v1.scenarios.routes._get_alert_repo", return_value=mock_alert_repo),
        ):
            res = client.get(
                f"/api/v1/cameras/{camera_id}/scenario",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True

        scenario = body["data"]["scenario"]
        assert scenario["camera"]["id"] == camera_id
        assert scenario["camera"]["name"] == "Camera Test"

        assert len(scenario["modules"]) == 1
        assert scenario["modules"][0]["module_code"] == "epi"
        assert len(scenario["modules"][0]["classes"]) == 1

        assert len(scenario["operations"]) == 1
        assert scenario["operations"][0]["type_id"] == "position"

        assert len(scenario["alert_rules"]) == 1
        assert scenario["alert_rules"][0]["violation_type"] == "no_helmet"

        assert len(scenario["schedule"]) == 1
        assert scenario["schedule"][0]["module"] == "epi"

    def test_disabled_module_excluded_from_scenario(self, client, app):
        tenant_id = uuid4()
        camera_id = str(uuid4())
        token = _make_jwt(app, tenant_id)

        mock_cam_repo = MagicMock()
        mock_cam_repo.get_by_id_and_tenant.return_value = _mock_camera(tenant_id, camera_id)

        mock_mod_repo = MagicMock()
        mock_mod_repo.get_by_tenant.return_value = [
            {"module_code": "epi", "enabled": False, "config": {}, "activated_at": None, "expires_at": None}
        ]

        mock_op_repo = MagicMock()
        mock_op_repo.list_by_camera.return_value = []

        mock_alert_repo = MagicMock()
        mock_alert_repo.list_for_camera_scenario.return_value = []

        with (
            patch("app.api.v1.scenarios.routes._get_camera_repo", return_value=mock_cam_repo),
            patch("app.api.v1.scenarios.routes._get_module_repo", return_value=mock_mod_repo),
            patch("app.api.v1.scenarios.routes._get_operation_repo", return_value=mock_op_repo),
            patch("app.api.v1.scenarios.routes._get_alert_repo", return_value=mock_alert_repo),
        ):
            res = client.get(
                f"/api/v1/cameras/{camera_id}/scenario",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        assert res.get_json()["data"]["scenario"]["modules"] == []


# ---------------------------------------------------------------------------
# Operation-types tests — mocked (always run)
# ---------------------------------------------------------------------------

class TestListOperationTypesMocked:

    def test_no_jwt_returns_401(self, client):
        res = client.get("/api/v1/scenarios/operation-types?module=epi")
        assert res.status_code == 401

    def test_valid_module_returns_200_with_types(self, client, app):
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id)

        res = client.get(
            "/api/v1/scenarios/operation-types?module=epi",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert res.status_code == 200
        body = res.get_json()
        assert body["success"] is True
        assert "types" in body["data"]
        assert body["data"]["module"] == "epi"
        assert isinstance(body["data"]["types"], list)

    def test_unknown_module_returns_200_not_error(self, client, app):
        """Módulo inválido → lista vazia ou só canônicos, sem 4xx/5xx."""
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id)

        res = client.get(
            "/api/v1/scenarios/operation-types?module=nonexistent_xyz_999",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert res.status_code == 200
        assert "types" in res.get_json()["data"]

    def test_missing_module_param_returns_200(self, client, app):
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id)

        res = client.get(
            "/api/v1/scenarios/operation-types",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert res.status_code == 200

    def test_each_type_has_config_schema(self, client, app):
        """Tipos retornados devem conter config_schema para o frontend."""
        tenant_id = uuid4()
        token = _make_jwt(app, tenant_id)

        res = client.get(
            "/api/v1/scenarios/operation-types?module=epi",
            headers={"Authorization": f"Bearer {token}"},
        )

        data = res.get_json()["data"]
        for op_type in data["types"]:
            assert "type_id" in op_type, f"type_id ausente em {op_type}"
            assert "config_schema" in op_type, f"config_schema ausente em {op_type}"


# ---------------------------------------------------------------------------
# Real-DB integration tests (skip if INTEGRATION_DATABASE_URL not set)
# ---------------------------------------------------------------------------

class TestScenarioIntegration:
    """Testes contra Postgres real — pulados automaticamente sem DB configurado."""

    def test_seed_and_compose_scenario(self, client, app, pg_pool, pg_raw, tenant_id):
        """Seed completo → GET scenario compõe todas as partes corretamente."""
        camera_id = str(uuid4())

        with pg_raw.cursor() as cur:
            cur.execute(
                "INSERT INTO cameras (id, tenant_id, name, host, port, is_active) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (camera_id, tenant_id, "Cam Integração", "192.168.1.1", 554, True),
            )
            cur.execute(
                "UPDATE cameras SET schedule_rules = %s::jsonb WHERE id = %s",
                (
                    json.dumps([{"days": [1, 2], "start": "08:00", "end": "18:00", "module": "epi"}]),
                    camera_id,
                ),
            )
            cur.execute(
                "INSERT INTO tenant_modules (tenant_id, module_code, enabled) "
                "VALUES (%s, %s, true) "
                "ON CONFLICT (tenant_id, module_code) DO UPDATE SET enabled = true",
                (tenant_id, "epi"),
            )
            cur.execute(
                "INSERT INTO operations (tenant_id, camera_id, module_id, type_id, name, config) "
                "VALUES (%s, %s, %s, %s, %s, %s::jsonb)",
                (tenant_id, camera_id, "epi", "position", "Zona EPI Test", json.dumps({})),
            )
            # Regra específica da câmera
            cur.execute(
                "INSERT INTO alert_rules (tenant_id, camera_id, violation_type, enabled) "
                "VALUES (%s, %s, %s, true)",
                (tenant_id, camera_id, "no_helmet"),
            )
            # Regra global do tenant (camera_id IS NULL)
            cur.execute(
                "INSERT INTO alert_rules (tenant_id, camera_id, violation_type, enabled) "
                "VALUES (%s, NULL, %s, true)",
                (tenant_id, "no_vest"),
            )

        token = _make_jwt(app, tenant_id)
        res = client.get(
            f"/api/v1/cameras/{camera_id}/scenario",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert res.status_code == 200
        scenario = res.get_json()["data"]["scenario"]

        assert scenario["camera"]["id"] == camera_id
        assert scenario["camera"]["name"] == "Cam Integração"

        assert len(scenario["schedule"]) == 1
        assert scenario["schedule"][0]["module"] == "epi"

        module_codes = [m["module_code"] for m in scenario["modules"]]
        assert "epi" in module_codes

        assert len(scenario["operations"]) == 1
        assert scenario["operations"][0]["type_id"] == "position"

        # Específica (no_helmet) + global (no_vest) = 2
        assert len(scenario["alert_rules"]) == 2
        violation_types = {r["violation_type"] for r in scenario["alert_rules"]}
        assert "no_helmet" in violation_types
        assert "no_vest" in violation_types

    def test_cross_tenant_camera_returns_404(self, client, app, pg_pool, pg_raw, tenant_id):
        """C-01: câmera de outro tenant → 404 (não vaza existência)."""
        other_tenant_id = str(uuid4())
        camera_id = str(uuid4())

        with pg_raw.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
                (other_tenant_id, f"Other {other_tenant_id[:8]}", f"ot-{other_tenant_id[:8]}"),
            )
            cur.execute(
                "INSERT INTO cameras (id, tenant_id, name, host, port) "
                "VALUES (%s, %s, %s, %s, %s)",
                (camera_id, other_tenant_id, "Cam Outro", "10.0.0.1", 554),
            )

        try:
            token = _make_jwt(app, tenant_id)
            res = client.get(
                f"/api/v1/cameras/{camera_id}/scenario",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 404, "Cross-tenant camera deve retornar 404"
        finally:
            with pg_raw.cursor() as cur:
                cur.execute("DELETE FROM cameras WHERE id = %s", (camera_id,))
                cur.execute("DELETE FROM public.tenants WHERE id = %s", (other_tenant_id,))

    def test_scenario_alert_rules_never_leak_other_tenant(self, client, app, pg_pool, pg_raw, tenant_id):
        """Regras de outro tenant nunca aparecem no cenário (C-01)."""
        other_tenant_id = str(uuid4())
        camera_id = str(uuid4())

        with pg_raw.cursor() as cur:
            cur.execute(
                "INSERT INTO cameras (id, tenant_id, name, host, port) "
                "VALUES (%s, %s, %s, %s, %s)",
                (camera_id, tenant_id, "Cam Rules Test", "192.168.0.1", 554),
            )
            cur.execute(
                "INSERT INTO alert_rules (tenant_id, camera_id, violation_type, enabled) "
                "VALUES (%s, %s, %s, true)",
                (tenant_id, camera_id, "no_helmet"),
            )
            cur.execute(
                "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
                (other_tenant_id, f"OtherT {other_tenant_id[:8]}", f"ot2-{other_tenant_id[:8]}"),
            )
            # Regra global de outro tenant — NÃO deve aparecer
            cur.execute(
                "INSERT INTO alert_rules (tenant_id, camera_id, violation_type, enabled) "
                "VALUES (%s, NULL, %s, true)",
                (other_tenant_id, "no_vest"),
            )

        try:
            token = _make_jwt(app, tenant_id)
            res = client.get(
                f"/api/v1/cameras/{camera_id}/scenario",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert res.status_code == 200
            rules = res.get_json()["data"]["scenario"]["alert_rules"]
            tenant_ids_in_rules = {str(r.get("tenant_id", "")) for r in rules}
            assert other_tenant_id not in tenant_ids_in_rules, "Cross-tenant leak em alert_rules"
            assert len(rules) == 1
            assert rules[0]["violation_type"] == "no_helmet"
        finally:
            with pg_raw.cursor() as cur:
                cur.execute("DELETE FROM alert_rules WHERE tenant_id = %s", (other_tenant_id,))
                cur.execute("DELETE FROM public.tenants WHERE id = %s", (other_tenant_id,))
