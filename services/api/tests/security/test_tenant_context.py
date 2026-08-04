"""Security tests: "assumir contexto de tenant" (superadmin).

Distinto de test_impersonation.py (WS6, "ver como um usuário"): aqui o
superadmin troca de TENANT mantendo a PRÓPRIA identidade (sub inalterado).

Cobertura:
  1. Sem contexto assumido, superadmin (tenant_id do placeholder 'admin')
     não enxerga recurso de OUTRO tenant → 404 (C-01, prova que nada vazou).
  2. Não-superadmin não lista tenants nem assume contexto → 404 (não 403).
  3. Token de contexto assumido acessa recursos do tenant ALVO normalmente
     — mesmo endpoint (GET /api/cameras/<id>/module/current) usado no teste
     de isolamento cross-tenant (test_camera_module_handler_tenant.py).
  4. Token emitido por /assume carrega identity do PRÓPRIO superadmin +
     claims do tenant alvo + tenant_ctx/impersonated_by + TTL curto (30min).
  5. Toda requisição feita com token de contexto assumido gera registro em
     public.tenant_context_audit (after_request hook, migration 108).
  6. Aninhamento: assumir contexto durante 'ver como' (imp) ou durante outro
     contexto já assumido → 409 (nunca emite um segundo token elevado).
"""
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from flask_jwt_extended import create_access_token, decode_token

import app.api.v1.cameras.module_handler as module_handler

SUPERADMIN_ID = str(uuid.uuid4())
ADMIN_TENANT_ID = str(uuid.uuid4())  # tenant placeholder do superadmin (025_superadmin_viewer_role)
TARGET_TENANT_ID = str(uuid.uuid4())  # tenant alvo (ex.: RVB)
CAMERA_ID = str(uuid.uuid4())

_ROUTES_POOL = "app.api.v1.admin.tenant_context_routes.DatabasePool"
_GLOBAL_POOL_GET_INSTANCE = "app.infrastructure.database.connection.DatabasePool.get_instance"


# --------------------------------------------------------------------------- helpers


def _auth_header(
    app,
    role: str = "superadmin",
    tenant_id: str = ADMIN_TENANT_ID,
    extra_claims: dict | None = None,
    identity: str | None = None,
) -> dict[str, str]:
    claims = {
        "tenant_id": tenant_id,
        "tenant_schema": "admin_schema",
        "email": "vitor@logikosvision.com.br",
        "role": role,
    }
    if extra_claims:
        claims.update(extra_claims)
    with app.app_context():
        token = create_access_token(
            identity=identity or SUPERADMIN_ID, additional_claims=claims
        )
    return {"Authorization": f"Bearer {token}"}


def _target_tenant_row() -> dict:
    return {
        "id": TARGET_TENANT_ID,
        "name": "RVB Isolantes",
        "slug": "rvb",
        "schema_name": "tenant_rvb",
        "is_active": True,
        "modules_enabled": ["epi"],
    }


def _make_pool(fetchone_row=None, fetchall_rows=None, executed: list | None = None):
    """Pool mockado — cada get_connection() abre um cursor novo, mas todos
    compartilham (via closure) os mesmos fetchone/fetchall/executed —
    suficiente para requisições que abrem mais de uma conexão (rota +
    hook de auditoria)."""

    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = fetchone_row
        mock_cur.fetchall.return_value = fetchall_rows or []
        if executed is not None:
            def _record(query, params=None):  # noqa: ARG001
                executed.append((str(query), params))
            mock_cur.execute.side_effect = _record
        mock_conn.cursor.return_value = mock_cur
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


def _mock_user_repo_get_by_id(monkeypatch) -> None:
    """UserRepository.get_by_id — usado só p/ compor o `user` da resposta
    do /assume; mockado direto (não via DB) para não colidir com o mock do
    pool usado pela query de tenants."""
    from app.infrastructure.database.repositories.user_repository import UserRepository

    monkeypatch.setattr(
        UserRepository,
        "get_by_id",
        lambda self, user_id: {
            "id": str(user_id),
            "email": "vitor@logikosvision.com.br",
            "name": "Vitor Emanuel",
        },
    )


def _mock_camera_repo(monkeypatch, owner_tenant_id: str = TARGET_TENANT_ID) -> MagicMock:
    """CameraRepository mockado — só acha a câmera para owner_tenant_id
    (mesmo padrão de test_camera_module_handler_tenant.py)."""
    repo = MagicMock()

    def _get_by_id_and_tenant(camera_id, tenant_id):  # noqa: ARG001
        if str(tenant_id) == owner_tenant_id:
            return {
                "id": CAMERA_ID,
                "tenant_id": owner_tenant_id,
                "active_module": "epi",
                "schedule_rules": [],
            }
        return None

    repo.get_by_id_and_tenant.side_effect = _get_by_id_and_tenant
    monkeypatch.setattr(module_handler, "_get_camera_repo", lambda: repo)
    return repo


# ── 1. Cross-tenant sem contexto assumido ──────────────────────────────────


class TestSuperadminWithoutAssumedContext:
    def test_own_placeholder_tenant_cannot_read_target_resource(
        self, app, client, monkeypatch
    ):
        """Superadmin com o próprio tenant_id (placeholder 'admin') no token
        não enxerga recurso do tenant alvo — 404, nada vazou (C-01)."""
        _mock_camera_repo(monkeypatch, owner_tenant_id=TARGET_TENANT_ID)

        resp = client.get(
            f"/api/cameras/{CAMERA_ID}/module/current",
            headers=_auth_header(app, role="superadmin", tenant_id=ADMIN_TENANT_ID),
        )
        assert resp.status_code == 404


# ── 2. Gate: só superadmin, e 404 (não 403) ─────────────────────────────────


class TestGateNonSuperadmin:
    @pytest.mark.parametrize("role", ["admin", "operator", "analyst", "viewer"])
    def test_list_tenants_404(self, client, app, role):
        resp = client.get(
            "/api/v1/admin/tenant-context/tenants",
            headers=_auth_header(app, role=role),
        )
        assert resp.status_code == 404

    @pytest.mark.parametrize("role", ["admin", "operator", "analyst", "viewer"])
    def test_assume_context_404(self, client, app, role):
        resp = client.post(
            f"/api/v1/admin/tenant-context/tenants/{TARGET_TENANT_ID}/assume",
            headers=_auth_header(app, role=role),
        )
        assert resp.status_code == 404

    def test_list_no_token_401(self, client):
        resp = client.get("/api/v1/admin/tenant-context/tenants")
        assert resp.status_code == 401

    def test_assume_no_token_401(self, client):
        resp = client.post(
            f"/api/v1/admin/tenant-context/tenants/{TARGET_TENANT_ID}/assume"
        )
        assert resp.status_code == 401


# ── 3. Token assumido acessa o tenant alvo normalmente ──────────────────────


class TestAssumedTokenAccessesTargetTenant:
    def test_assumed_token_reads_target_tenant_resource(self, app, client, monkeypatch):
        _mock_camera_repo(monkeypatch, owner_tenant_id=TARGET_TENANT_ID)

        headers = _auth_header(
            app,
            role="superadmin",
            tenant_id=TARGET_TENANT_ID,
            extra_claims={
                "tenant_schema": "tenant_rvb",
                "tenant_ctx": True,
                "impersonated_by": SUPERADMIN_ID,
            },
        )
        resp = client.get(f"/api/cameras/{CAMERA_ID}/module/current", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["camera_id"] == CAMERA_ID


# ── 4. Token emitido por /assume ─────────────────────────────────────────


class TestAssumeTokenIssuance:
    def test_token_preserves_superadmin_identity_and_carries_target_claims(
        self, app, client, monkeypatch
    ):
        _mock_user_repo_get_by_id(monkeypatch)
        pool = _make_pool(fetchone_row=_target_tenant_row())
        with patch(_ROUTES_POOL) as mock_cls:
            mock_cls.get_instance.return_value = pool
            resp = client.post(
                f"/api/v1/admin/tenant-context/tenants/{TARGET_TENANT_ID}/assume",
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["expires_in_minutes"] == 30
        assert data["tenant"]["id"] == TARGET_TENANT_ID

        with app.app_context():
            payload = decode_token(data["token"])
        # Identidade do SUPERADMIN preservada — não vira o tenant/usuário alvo
        assert payload["sub"] == SUPERADMIN_ID
        assert payload["role"] == "superadmin"
        assert payload["tenant_id"] == TARGET_TENANT_ID
        assert payload["tenant_schema"] == "tenant_rvb"
        assert payload["tenant_ctx"] is True
        assert payload["impersonated_by"] == SUPERADMIN_ID
        # TTL curto — fração do normal (JWT_EXPIRY_HOURS, default 24h)
        assert payload["exp"] - payload["iat"] <= 30 * 60 + 5

    def test_target_not_found_404(self, app, client, monkeypatch):
        _mock_user_repo_get_by_id(monkeypatch)
        pool = _make_pool(fetchone_row=None)
        with patch(_ROUTES_POOL) as mock_cls:
            mock_cls.get_instance.return_value = pool
            resp = client.post(
                f"/api/v1/admin/tenant-context/tenants/{TARGET_TENANT_ID}/assume",
                headers=_auth_header(app),
            )
        assert resp.status_code == 404

    def test_target_inactive_422(self, app, client, monkeypatch):
        _mock_user_repo_get_by_id(monkeypatch)
        row = {**_target_tenant_row(), "is_active": False}
        pool = _make_pool(fetchone_row=row)
        with patch(_ROUTES_POOL) as mock_cls:
            mock_cls.get_instance.return_value = pool
            resp = client.post(
                f"/api/v1/admin/tenant-context/tenants/{TARGET_TENANT_ID}/assume",
                headers=_auth_header(app),
            )
        assert resp.status_code == 422


# ── 5. Auditoria por requisição ─────────────────────────────────────────────


class TestPerRequestAudit:
    def test_request_under_tenant_ctx_token_is_audited(self, app, client):
        executed: list = []
        pool = _make_pool(
            fetchall_rows=[],
            fetchone_row={"id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc)},
            executed=executed,
        )
        headers = _auth_header(
            app,
            role="superadmin",
            tenant_id=TARGET_TENANT_ID,
            extra_claims={
                "tenant_schema": "tenant_rvb",
                "tenant_ctx": True,
                "impersonated_by": SUPERADMIN_ID,
            },
        )
        with patch(_GLOBAL_POOL_GET_INSTANCE, return_value=pool):
            resp = client.get("/api/v1/admin/tenant-context/tenants", headers=headers)

        assert resp.status_code == 200
        insert_calls = [
            (q, p) for q, p in executed if "tenant_context_audit" in q.lower()
        ]
        assert len(insert_calls) == 1, "Requisição sob contexto assumido deve gerar exatamente 1 registro de auditoria"
        _, params = insert_calls[0]
        # Registro legível: tenant alvo, quem (superadmin), método e path
        assert TARGET_TENANT_ID in [str(p) for p in params]
        assert SUPERADMIN_ID in [str(p) for p in params]
        assert "GET" in params
        assert any("/tenant-context/tenants" in str(p) for p in params)

    def test_request_without_tenant_ctx_claim_is_not_audited(self, app, client):
        executed: list = []
        pool = _make_pool(fetchall_rows=[], executed=executed)
        headers = _auth_header(app, role="superadmin", tenant_id=ADMIN_TENANT_ID)
        with patch(_GLOBAL_POOL_GET_INSTANCE, return_value=pool):
            resp = client.get("/api/v1/admin/tenant-context/tenants", headers=headers)

        assert resp.status_code == 200
        joined = "\n".join(q.lower() for q, _ in executed)
        assert "tenant_context_audit" not in joined


# ── 6. Aninhamento ───────────────────────────────────────────────────────────


class TestAssumeNestingGuards:
    def test_assume_while_already_in_tenant_context_409(self, app, client):
        headers = _auth_header(
            app,
            role="superadmin",
            tenant_id=TARGET_TENANT_ID,
            extra_claims={"tenant_ctx": True, "impersonated_by": SUPERADMIN_ID},
        )
        resp = client.post(
            f"/api/v1/admin/tenant-context/tenants/{TARGET_TENANT_ID}/assume",
            headers=headers,
        )
        assert resp.status_code == 409

    def test_assume_while_ws6_impersonating_409(self, app, client):
        headers = _auth_header(
            app,
            role="superadmin",
            extra_claims={"imp": True, "impersonated_by": SUPERADMIN_ID},
        )
        resp = client.post(
            f"/api/v1/admin/tenant-context/tenants/{TARGET_TENANT_ID}/assume",
            headers=headers,
        )
        assert resp.status_code == 409


# ── 7. Renovação (D-48, opção C) ────────────────────────────────────────────


class TestRenewTenantContext:
    """POST /renew — renova (mesmas claims, TTL cheio de novo) um token de
    contexto já assumido, sem passar de novo por /assume."""

    def _assumed_headers(self, app, **extra) -> dict[str, str]:
        claims = {
            "tenant_schema": "tenant_rvb",
            "modules": ["epi"],
            "tenant_ctx": True,
            "impersonated_by": SUPERADMIN_ID,
        }
        claims.update(extra)
        return _auth_header(app, role="superadmin", tenant_id=TARGET_TENANT_ID, extra_claims=claims)

    def test_renews_with_same_claims_and_fresh_ttl(self, app, client):
        headers = self._assumed_headers(app)
        with patch(_GLOBAL_POOL_GET_INSTANCE, return_value=None):
            resp = client.post("/api/v1/admin/tenant-context/renew", headers=headers)

        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["expires_in_minutes"] == 30

        with app.app_context():
            payload = decode_token(data["token"])
        # Identidade do superadmin preservada, claims do tenant alvo repetidas
        assert payload["sub"] == SUPERADMIN_ID
        assert payload["role"] == "superadmin"
        assert payload["tenant_id"] == TARGET_TENANT_ID
        assert payload["tenant_schema"] == "tenant_rvb"
        assert payload["modules"] == ["epi"]
        assert payload["tenant_ctx"] is True
        assert payload["impersonated_by"] == SUPERADMIN_ID
        # TTL renovado por inteiro (não é o restante do token anterior)
        assert payload["exp"] - payload["iat"] <= 30 * 60 + 5
        assert payload["exp"] - payload["iat"] >= 30 * 60 - 5

    def test_base_token_without_tenant_ctx_is_rejected(self, app, client):
        """Token base do superadmin (sem contexto assumido) não pode renovar
        — /renew não é um segundo caminho para CRIAR contexto."""
        headers = _auth_header(app, role="superadmin", tenant_id=ADMIN_TENANT_ID)
        resp = client.post("/api/v1/admin/tenant-context/renew", headers=headers)
        assert resp.status_code == 400

    @pytest.mark.parametrize("role", ["admin", "operator", "analyst", "viewer"])
    def test_non_superadmin_404(self, app, client, role):
        headers = _auth_header(
            app,
            role=role,
            tenant_id=TARGET_TENANT_ID,
            extra_claims={
                "tenant_schema": "tenant_rvb",
                "tenant_ctx": True,
                "impersonated_by": SUPERADMIN_ID,
            },
        )
        resp = client.post("/api/v1/admin/tenant-context/renew", headers=headers)
        assert resp.status_code == 404

    def test_no_token_401(self, client):
        resp = client.post("/api/v1/admin/tenant-context/renew")
        assert resp.status_code == 401

    def test_renew_is_audited(self, app, client):
        executed: list = []
        pool = _make_pool(fetchall_rows=[], executed=executed)
        headers = self._assumed_headers(app)
        with patch(_GLOBAL_POOL_GET_INSTANCE, return_value=pool):
            resp = client.post("/api/v1/admin/tenant-context/renew", headers=headers)

        assert resp.status_code == 200
        renew_calls = [
            (q, p) for q, p in executed if "audit_log" in q.lower()
        ]
        assert len(renew_calls) == 1, "Renovação deve gravar 1 registro em public.audit_log"
        _, params = renew_calls[0]
        assert SUPERADMIN_ID in [str(p) for p in params]
        assert TARGET_TENANT_ID in [str(p) for p in params]
        assert "tenant_context.renew" in params

        # A própria requisição sob token tenant_ctx também é auditada pelo
        # after_request de sempre (register_tenant_context_audit) — mesmo
        # comportamento de qualquer outra rota sob contexto assumido.
        per_request_calls = [
            (q, p) for q, p in executed if "tenant_context_audit" in q.lower()
        ]
        assert len(per_request_calls) == 1
