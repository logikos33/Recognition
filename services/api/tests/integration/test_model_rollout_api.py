"""
Integration tests — task-025: Model Rollout API.

Eval cases (spec):
  1. GET /api/v1/models/active retorna manifesto do modelo ativo
  2. GET retorna 404 quando não há modelo ativo
  3. POST /pin ativa modelo, desativa anterior, registra em model_activation_log
  4. POST /pin com canary=true marca canário sem ativar
  5. Canário promovido a ativo no pin subsequente (sem canary)
  6. Isolamento: pin de modelo de outro tenant → 404 (C-01)
  7. Sem JWT → 401; non-admin → 403; module ausente → 400

Requer INTEGRATION_DATABASE_URL ou HARNESS_DATABASE_URL.
Usa pg_pool (session) para inicializar o DatabasePool singleton antes das requests HTTP.
"""
from __future__ import annotations

import json
import os
from uuid import uuid4

import psycopg2
import psycopg2.extras
import pytest
from flask_jwt_extended import create_access_token

from app.infrastructure.database.connection import DatabasePool

# ---------------------------------------------------------------------------
# DSN helper (reusa padrão do harness)
# ---------------------------------------------------------------------------


def _integration_dsn() -> str:
    return (
        os.environ.get("INTEGRATION_DATABASE_URL")
        or os.environ.get("HARNESS_DATABASE_URL")
        or ""
    )


# ---------------------------------------------------------------------------
# Fixtures de banco real
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_pool_rollout():
    """DatabasePool real para testes de rollout (session-scoped).

    Inicializa o singleton para que os handlers usem o banco real nas requests.
    """
    dsn = _integration_dsn()
    if not dsn:
        pytest.skip("INTEGRATION_DATABASE_URL não definida — pulando integração rollout")
    DatabasePool.reset()
    pool = DatabasePool.initialize(dsn, min_conn=1, max_conn=3)
    yield pool
    DatabasePool.reset()


@pytest.fixture
def pg_direct(pg_pool_rollout):
    """Conexão psycopg2 direta com autocommit para seed e assertions."""
    dsn = _integration_dsn()
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture
def tmp_schema(pg_direct):
    """Schema temporário com tabela models. Removido após o teste (CASCADE)."""
    schema = f"rollout_{str(uuid4()).replace('-', '')[:12]}"
    with pg_direct.cursor() as cur:
        cur.execute(f'CREATE SCHEMA "{schema}"')
        cur.execute(
            f"""
            CREATE TABLE "{schema}".models (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name        VARCHAR(255) NOT NULL,
                module      VARCHAR(50) NOT NULL,
                version     VARCHAR(50),
                r2_key      TEXT,
                hub_model_id    VARCHAR(255),
                hub_project_id  VARCHAR(255),
                metrics     JSONB DEFAULT '{{}}',
                active      BOOLEAN DEFAULT false,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
    yield schema
    with pg_direct.cursor() as cur:
        cur.execute(f'DROP SCHEMA "{schema}" CASCADE')


# ---------------------------------------------------------------------------
# JWT helper
# ---------------------------------------------------------------------------


def _jwt(app, tenant_id, schema, role="admin", user_id=None):
    uid = str(user_id or uuid4())
    with app.app_context():
        return create_access_token(
            identity=uid,
            additional_claims={
                "tenant_id": str(tenant_id),
                "tenant_schema": schema,
                "role": role,
            },
        )


# ---------------------------------------------------------------------------
# Casos 1-2: GET manifesto
# ---------------------------------------------------------------------------


def test_get_active_returns_manifest(client, app, pg_pool_rollout, pg_direct, tmp_schema):
    """GET /api/v1/models/active?module=epi retorna manifesto do modelo ativo."""
    tenant_id = str(uuid4())
    model_id = str(uuid4())

    with pg_direct.cursor() as cur:
        cur.execute(
            f'INSERT INTO "{tmp_schema}".models '
            "(id, name, module, version, r2_key, active) "
            "VALUES (%s, %s, %s, %s, %s, TRUE)",
            (model_id, "EPI v1.0", "epi", "1.0.0", "models/epi/v1.pt"),
        )

    token = _jwt(app, tenant_id, tmp_schema)
    resp = client.get(
        "/api/v1/models/active?module=epi",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = resp.get_json()
    assert resp.status_code == 200, body
    assert body["data"]["id"] == model_id
    assert body["data"]["module"] == "epi"
    assert body["data"]["version"] == "1.0.0"
    assert body["data"]["checksum"] == "models/epi/v1.pt"
    assert body["data"]["active"] is True
    assert body["data"]["canary"] is False


def test_get_active_no_model_returns_404(client, app, pg_pool_rollout, tmp_schema):
    """GET retorna 404 quando não há modelo ativo para o módulo."""
    token = _jwt(app, str(uuid4()), tmp_schema)
    resp = client.get(
        "/api/v1/models/active?module=quality",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Caso 3: POST /pin — ativa, desativa anterior, registra log
# ---------------------------------------------------------------------------


def test_pin_activates_model_and_records_log(
    client, app, pg_pool_rollout, pg_direct, tmp_schema
):
    """POST /pin ativa modelo B, desativa A, registra model_activation_log."""
    tenant_id = str(uuid4())
    user_id = str(uuid4())
    model_a = str(uuid4())
    model_b = str(uuid4())

    with pg_direct.cursor() as cur:
        cur.execute(
            f'INSERT INTO "{tmp_schema}".models (id, name, module, active) VALUES '
            "(%s, %s, %s, TRUE), (%s, %s, %s, FALSE)",
            (model_a, "Model A", "epi", model_b, "Model B", "epi"),
        )

    token = _jwt(app, tenant_id, tmp_schema, role="admin", user_id=user_id)
    resp = client.post(
        f"/api/v1/models/{model_b}/pin",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    body = resp.get_json()
    assert resp.status_code == 200, body
    assert body["data"]["manifest"]["id"] == model_b
    assert body["data"]["manifest"]["active"] is True
    assert body["data"]["manifest"]["canary"] is False
    assert body["data"]["action"] == "pinned"
    assert body["data"]["previous"]["id"] == model_a

    # A desativado, B ativo no banco
    with pg_direct.cursor() as cur:
        cur.execute(
            f'SELECT active FROM "{tmp_schema}".models WHERE id = %s', (model_a,)
        )
        assert cur.fetchone()["active"] is False
        cur.execute(
            f'SELECT active FROM "{tmp_schema}".models WHERE id = %s', (model_b,)
        )
        assert cur.fetchone()["active"] is True

    # Auditoria registrada
    with pg_direct.cursor() as cur:
        cur.execute(
            "SELECT activated_by, previous_model_id "
            "FROM public.model_activation_log WHERE model_id = %s "
            "ORDER BY activated_at DESC LIMIT 1",
            (model_b,),
        )
        log = cur.fetchone()
    assert log is not None, "model_activation_log deve ter registro"
    assert str(log["activated_by"]) == user_id
    assert str(log["previous_model_id"]) == model_a


# ---------------------------------------------------------------------------
# Caso 4: canary=true não ativa
# ---------------------------------------------------------------------------


def test_pin_canary_marks_without_activating(
    client, app, pg_pool_rollout, pg_direct, tmp_schema
):
    """POST /pin com canary=true: metrics.canary=true, active permanece false."""
    tenant_id = str(uuid4())
    model_id = str(uuid4())

    with pg_direct.cursor() as cur:
        cur.execute(
            f'INSERT INTO "{tmp_schema}".models (id, name, module, active) '
            "VALUES (%s, %s, %s, FALSE)",
            (model_id, "Canary Candidate", "epi"),
        )

    token = _jwt(app, tenant_id, tmp_schema)
    resp = client.post(
        f"/api/v1/models/{model_id}/pin",
        headers={"Authorization": f"Bearer {token}"},
        json={"canary": True},
    )
    body = resp.get_json()
    assert resp.status_code == 200, body
    assert body["data"]["manifest"]["canary"] is True
    assert body["data"]["manifest"]["active"] is False
    assert body["data"]["action"] == "canary_marked"

    # Confirmar no banco
    with pg_direct.cursor() as cur:
        cur.execute(
            f'SELECT active, metrics FROM "{tmp_schema}".models WHERE id = %s',
            (model_id,),
        )
        row = cur.fetchone()
    assert row["active"] is False
    assert row["metrics"].get("canary") is True


# ---------------------------------------------------------------------------
# Caso 5: canário promovido a ativo no pin subsequente
# ---------------------------------------------------------------------------


def test_canary_promoted_to_active_on_second_pin(
    client, app, pg_pool_rollout, pg_direct, tmp_schema
):
    """Modelo canário ativado no pin sem canary (promoção)."""
    tenant_id = str(uuid4())
    model_id = str(uuid4())

    with pg_direct.cursor() as cur:
        cur.execute(
            f'INSERT INTO "{tmp_schema}".models (id, name, module, active, metrics) '
            "VALUES (%s, %s, %s, FALSE, %s)",
            (model_id, "Canary→Active", "epi", json.dumps({"canary": True})),
        )

    token = _jwt(app, tenant_id, tmp_schema)
    resp = client.post(
        f"/api/v1/models/{model_id}/pin",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    body = resp.get_json()
    assert resp.status_code == 200, body
    assert body["data"]["manifest"]["active"] is True
    assert body["data"]["manifest"]["canary"] is False
    assert body["data"]["action"] == "pinned"


# ---------------------------------------------------------------------------
# Caso 6: isolamento cross-tenant → 404 (C-01)
# ---------------------------------------------------------------------------


def test_cross_tenant_pin_returns_404(client, app, pg_pool_rollout, pg_direct, tmp_schema):
    """Tenant B não pode pinar modelo do schema de Tenant A."""
    model_id = str(uuid4())
    with pg_direct.cursor() as cur:
        cur.execute(
            f'INSERT INTO "{tmp_schema}".models (id, name, module) '
            "VALUES (%s, %s, %s)",
            (model_id, "Tenant A Model", "epi"),
        )

    # Cria schema vazio para tenant B
    schema_b = f"rollout_{str(uuid4()).replace('-', '')[:12]}"
    with pg_direct.cursor() as cur:
        cur.execute(f'CREATE SCHEMA "{schema_b}"')
        cur.execute(
            f"""
            CREATE TABLE "{schema_b}".models (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                module VARCHAR(50) NOT NULL,
                version VARCHAR(50),
                r2_key TEXT,
                hub_model_id VARCHAR(255),
                hub_project_id VARCHAR(255),
                metrics JSONB DEFAULT '{{}}',
                active BOOLEAN DEFAULT false,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )

    try:
        token_b = _jwt(app, str(uuid4()), schema_b)
        resp = client.post(
            f"/api/v1/models/{model_id}/pin",
            headers={"Authorization": f"Bearer {token_b}"},
            json={},
        )
        assert resp.status_code == 404
    finally:
        with pg_direct.cursor() as cur:
            cur.execute(f'DROP SCHEMA "{schema_b}" CASCADE')


# ---------------------------------------------------------------------------
# Caso 7: auth/param guards (sem DB real necessário)
# ---------------------------------------------------------------------------


def test_no_jwt_returns_401(client):
    """GET sem JWT → 401."""
    resp = client.get("/api/v1/models/active?module=epi")
    assert resp.status_code == 401


def test_no_jwt_pin_returns_401(client):
    """POST sem JWT → 401."""
    resp = client.post(f"/api/v1/models/{uuid4()}/pin", json={})
    assert resp.status_code == 401


def test_non_admin_pin_returns_403(client, app):
    """POST /pin com role=operator → 403."""
    token = _jwt(app, str(uuid4()), "public", role="operator")
    resp = client.post(
        f"/api/v1/models/{uuid4()}/pin",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert resp.status_code == 403


def test_missing_module_param_returns_400(client, app):
    """GET sem ?module → 400."""
    token = _jwt(app, str(uuid4()), "public")
    resp = client.get(
        "/api/v1/models/active",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
