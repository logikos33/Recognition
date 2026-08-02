"""
Integration tests: monofatura inbound/outbound (task-108, ADR-0053).

Cobertura (pool mockado, padrão dos testes de plate/branding):
  POST /api/v1/monofatura/pieces/<id>/scan               — abre sessão (400 sem stage; 401 sem JWT)
  POST /api/v1/monofatura/pieces/<id>/stages/<s>/complete — fecha + outbound (404 se não existe)
  GET  /api/v1/monofatura/sessions                        — lista tenant-scoped

Idempotência REAL (2× scan → mesma sessão) roda contra Postgres real quando
INTEGRATION_DATABASE_URL está definida (CI) — skip local sem DB.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TENANT_SCHEMA = "public"


@pytest.fixture
def operator_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token

        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": str(uuid4()),
                "role": "operator",
                "tenant_schema": TENANT_SCHEMA,
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _session_row(status="open", result=None):
    return {
        "id": str(uuid4()),
        "piece_id": "PC-123",
        "stage": "v1",
        "status": status,
        "camera_id": None,
        "started_at": "2026-07-17T14:00:00+00:00",
        "finished_at": None,
        "result": result,
        "evidence_r2_key": None,
        "created_at": "2026-07-17T14:00:00+00:00",
    }


def _mock_pool(row):
    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()
    pool.get_connection.return_value.__enter__.return_value = conn
    conn.cursor.return_value = cur
    cur.fetchone.return_value = row
    cur.fetchall.return_value = [row] if row else []
    return pool, cur


def test_scan_requires_jwt(client):
    resp = client.post("/api/v1/monofatura/pieces/PC-123/scan", json={"stage": "v1"})
    assert resp.status_code == 401


def test_scan_requires_stage(client, operator_headers):
    resp = client.post(
        "/api/v1/monofatura/pieces/PC-123/scan", json={}, headers=operator_headers
    )
    assert resp.status_code == 400


def test_scan_opens_session(client, operator_headers):
    pool, cur = _mock_pool(_session_row())
    with patch(
        "app.api.v1.monofatura.routes.DatabasePool"
    ) as mock_dp:
        mock_dp.get_instance.return_value = pool
        resp = client.post(
            "/api/v1/monofatura/pieces/PC-123/scan",
            json={"stage": "v1"},
            headers=operator_headers,
        )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["session"]["piece_id"] == "PC-123"
    # search_path parametrizado (nunca f-string)
    cur.execute.assert_any_call("SET search_path TO %s, public", (TENANT_SCHEMA,))
    # idempotência: INSERT com ON CONFLICT na SQL
    sqls = " ".join(str(c.args[0]) for c in cur.execute.call_args_list)
    assert "ON CONFLICT (piece_id, stage)" in sqls


def test_complete_unknown_session_404(client, operator_headers):
    pool, _ = _mock_pool(None)
    with patch("app.api.v1.monofatura.routes.DatabasePool") as mock_dp:
        mock_dp.get_instance.return_value = pool
        resp = client.post(
            "/api/v1/monofatura/pieces/PC-999/stages/v1/complete",
            json={"result": {"ok": True, "attributes": []}},
            headers=operator_headers,
        )
    assert resp.status_code == 404


def test_complete_closes_and_returns_session(client, operator_headers):
    row = _session_row(status="completed", result={"ok": False})
    pool, cur = _mock_pool(row)
    with patch("app.api.v1.monofatura.routes.DatabasePool") as mock_dp:
        mock_dp.get_instance.return_value = pool
        resp = client.post(
            "/api/v1/monofatura/pieces/PC-123/stages/v1/complete",
            json={
                "result": {
                    "ok": False,
                    "attributes": [{"name": "solda", "ok": False}],
                },
                "evidence_r2_key": "evidence/pc-123-v1.jpg",
                "elapsed_s": 42.5,
            },
            headers=operator_headers,
        )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["session"]["status"] == "completed"


def test_complete_requires_result_object(client, operator_headers):
    resp = client.post(
        "/api/v1/monofatura/pieces/PC-123/stages/v1/complete",
        json={"result": "nope"},
        headers=operator_headers,
    )
    assert resp.status_code == 400


def test_list_sessions(client, operator_headers):
    pool, _ = _mock_pool(_session_row())
    with patch("app.api.v1.monofatura.routes.DatabasePool") as mock_dp:
        mock_dp.get_instance.return_value = pool
        resp = client.get(
            "/api/v1/monofatura/sessions?piece_id=PC-123", headers=operator_headers
        )
    assert resp.status_code == 200
    assert len(resp.get_json()["data"]["sessions"]) == 1


# ---------------------------------------------------------------------------
# Idempotência real (Postgres) — roda no CI; skip local sem DB
# ---------------------------------------------------------------------------

def test_scan_idempotent_real_db(pg_pool, pg_raw):
    """Usa pg_pool/pg_raw (session/conftest.py) em vez de
    DatabasePool.reset()/initialize() manual. O singleton global é
    compartilhado pela sessão inteira do pytest (tests/integration/conftest.py
    o inicializa uma única vez via pg_pool, escopo "session"); chamar
    DatabasePool.reset() aqui fechava o pool real e trocava a instância sem
    nunca restaurar o objeto original — quebrando qualquer teste de
    integração que rodasse depois nesta mesma sessão. InspectionSessionRepository
    recebe qualquer DatabasePool via DI (BaseRepository.__init__), então basta
    passar o pg_pool da sessão direto pro repo."""
    from app.infrastructure.database.repositories.inspection_session_repository import (
        InspectionSessionRepository,
    )

    schema = f"t_mono_{uuid4().hex[:8]}"
    with pg_raw.cursor() as cur:
        cur.execute(f'CREATE SCHEMA "{schema}"')
        cur.execute(
            f'''
            CREATE TABLE "{schema}".inspection_sessions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                piece_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                camera_id UUID,
                started_at TIMESTAMPTZ DEFAULT NOW(),
                finished_at TIMESTAMPTZ,
                result JSONB,
                evidence_r2_key TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (piece_id, stage)
            )
            '''
        )
    try:
        repo = InspectionSessionRepository(pg_pool)
        s1 = repo.open_session(schema, "PC-777", "v1")
        s2 = repo.open_session(schema, "PC-777", "v1")
        assert s1["id"] == s2["id"], "bipagem repetida duplicou a sessão"
        done = repo.complete_session(schema, "PC-777", "v1", '{"ok": true}')
        assert done is not None and done["status"] == "completed"
        s3 = repo.open_session(schema, "PC-777", "v1")
        assert s3["id"] == s1["id"] and s3["status"] == "completed", (
            "re-bipagem reabriu/duplicou sessão concluída"
        )
    finally:
        with pg_raw.cursor() as cur:
            cur.execute(f'DROP SCHEMA "{schema}" CASCADE')
