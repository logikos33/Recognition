"""
Segurança — revogação de sessão por admin não bloqueava o JWT (achado P1 da
auditoria pré-produção).

Bug: `deactivate_user`, `revoke_user_sessions` e `suspend_tenant` marcavam
`active_sessions.revoked_at` no Postgres e publicavam em um canal Redis
(`session_revoked:{user_id}`) sem NENHUM subscriber em todo `services/api`
(confirmado via grep). O `token_in_blocklist_loader` do flask-jwt-extended só
consulta a blocklist Redis escrita por `blocklist_jtis` — nunca a tabela
Postgres nem aquele canal pub/sub. Resultado: um usuário/tenant
desativado/revogado pelo admin continuava com JWT válido (até ~24h) em
qualquer rota autenticada.

Fix: os 3 handlers agora capturam `RETURNING jti, expires_at` do UPDATE e
chamam `session_service.blocklist_jtis` — o mesmo mecanismo já usado (e
testado) pelo login com single_session e pelo reset de senha.

Teste falha-antes/passa-depois: após deactivate/revoke/suspend, o jti da
sessão revogada deve estar na blocklist Redis (`is_jti_revoked` → True).
"""
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from flask_jwt_extended import create_access_token

import app.api.v1.admin.routes as admin_routes
from app.domain.services.session_service import is_jti_revoked

TARGET_JTI = "target-jti-1234"


def _superadmin_auth(app) -> dict[str, str]:
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": str(uuid.uuid4()),
                "tenant_schema": "tenant_test",
                "role": "superadmin",
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


class _FakeCursor:
    """Cursor mínimo: primeira query = lookup (fetchone), segunda = UPDATE...RETURNING (fetchall)."""

    def __init__(self, lookup_row, returning_rows):
        self._lookup_row = lookup_row
        self._returning_rows = returning_rows
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append(query.strip())

    def fetchone(self):
        return self._lookup_row

    def fetchall(self):
        return self._returning_rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def commit(self):
        pass


@pytest.fixture()
def fake_redis_blocklist():
    """Redis fake em memória — só o suficiente para setex/exists usados pelo blocklist."""
    store: dict[str, str] = {}

    class _FakeRedis:
        def setex(self, key, ttl, value):
            store[key] = value

        def exists(self, key):
            return 1 if key in store else 0

        def close(self):
            pass

    return _FakeRedis(), store


def _mock_pool(monkeypatch, lookup_row, returning_rows):
    cursor = _FakeCursor(lookup_row, returning_rows)
    conn = _FakeConn(cursor)

    @contextmanager
    def _get_connection():
        yield conn

    pool = MagicMock()
    pool.get_connection = _get_connection
    monkeypatch.setattr(admin_routes, "_pool", lambda: pool)
    monkeypatch.setattr(admin_routes, "_get_redis", lambda: MagicMock())
    return cursor


def _future_expiry():
    return datetime.now(timezone.utc) + timedelta(hours=12)


class TestDeactivateUserRevokesJwt:
    def test_deactivated_user_jti_ends_up_blocklisted(self, app, client, monkeypatch, fake_redis_blocklist):
        user_id = str(uuid.uuid4())
        fake_redis, store = fake_redis_blocklist
        _mock_pool(
            monkeypatch,
            lookup_row={"tenant_id": str(uuid.uuid4())},
            returning_rows=[{"jti": TARGET_JTI, "expires_at": _future_expiry()}],
        )
        monkeypatch.setattr(
            "app.domain.services.session_service._get_redis", lambda: fake_redis
        )

        resp = client.post(
            f"/api/v1/admin/users/{user_id}/deactivate",
            headers=_superadmin_auth(app),
        )
        assert resp.status_code == 200
        assert is_jti_revoked(TARGET_JTI, redis_client=fake_redis), (
            "P1: deactivate_user rodou mas o jti da sessão não foi para a blocklist "
            "Redis — o JWT do usuário desativado continuaria válido."
        )


class TestRevokeUserSessionsBlocklists:
    def test_revoked_sessions_jti_ends_up_blocklisted(self, app, client, monkeypatch, fake_redis_blocklist):
        user_id = str(uuid.uuid4())
        fake_redis, store = fake_redis_blocklist
        _mock_pool(
            monkeypatch,
            lookup_row={"tenant_id": str(uuid.uuid4())},
            returning_rows=[{"jti": TARGET_JTI, "expires_at": _future_expiry()}],
        )
        monkeypatch.setattr(
            "app.domain.services.session_service._get_redis", lambda: fake_redis
        )

        resp = client.delete(
            f"/api/v1/admin/users/{user_id}/sessions",
            headers=_superadmin_auth(app),
        )
        assert resp.status_code == 200
        assert is_jti_revoked(TARGET_JTI, redis_client=fake_redis), (
            "P1: revoke_user_sessions rodou mas o jti não foi para a blocklist Redis."
        )


class TestSuspendTenantBlocklists:
    def test_suspended_tenant_sessions_jti_ends_up_blocklisted(self, app, client, monkeypatch, fake_redis_blocklist):
        tenant_id = str(uuid.uuid4())
        fake_redis, store = fake_redis_blocklist
        cursor = _FakeCursor(
            lookup_row={"id": tenant_id},
            returning_rows=[{"jti": TARGET_JTI, "expires_at": _future_expiry()}],
        )
        conn = _FakeConn(cursor)

        @contextmanager
        def _get_connection():
            yield conn

        pool = MagicMock()
        pool.get_connection = _get_connection
        monkeypatch.setattr(admin_routes, "_pool", lambda: pool)
        monkeypatch.setattr(
            "app.domain.services.session_service._get_redis", lambda: fake_redis
        )

        resp = client.post(
            f"/api/v1/admin/tenants/{tenant_id}/suspend",
            json={"reason": "test"},
            headers=_superadmin_auth(app),
        )
        assert resp.status_code == 200
        assert is_jti_revoked(TARGET_JTI, redis_client=fake_redis), (
            "P1: suspend_tenant rodou mas o jti das sessões do tenant não foi "
            "para a blocklist Redis."
        )
