"""
Integration tests: dashboard integrado (task-112, ADR-0053).

Cobertura (pool mockado, padrão dos testes de monofatura/plate):
  POST /api/v1/dashboard/training-metrics  — upsert por época (400 sem campos; 401 sem JWT)
  POST /api/v1/dashboard/edge-telemetry    — insert + publish best-effort
  GET  /api/v1/dashboard/training-metrics  — curvas agrupadas por modelo
  GET  /api/v1/dashboard/training-metrics/models — resumo por modelo
  GET  /api/v1/dashboard/edge-telemetry    — série temporal (400 window inválido)

Isolamento de tenant REAL roda contra Postgres quando INTEGRATION_DATABASE_URL
está definida (CI) — skip local sem DB.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

TENANT_A = str(uuid4())
TENANT_SCHEMA = "public"


@pytest.fixture
def operator_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token

        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT_A,
                "role": "operator",
                "tenant_schema": TENANT_SCHEMA,
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def trainer_headers(app):
    """training:write inclui superadmin/admin/trainer (registry canônico,
    app/core/permissions.py) — 'trainer' usado aqui pra exercitar o caso
    comum (não-admin com permissão de treino), distinto de operator/analyst/
    viewer (sem training:write, ver test_ingest_training_requires_elevated_role)."""
    with app.app_context():
        from flask_jwt_extended import create_access_token

        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT_A,
                "role": "trainer",
                "tenant_schema": TENANT_SCHEMA,
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _mock_pool(fetchall=None, fetchone=None, rowcount=0):
    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()
    pool.get_connection.return_value.__enter__.return_value = conn
    conn.cursor.return_value = cur
    cur.fetchall.return_value = fetchall if fetchall is not None else []
    cur.fetchone.return_value = fetchone
    cur.rowcount = rowcount
    return pool, cur


# --------------------------------------------------------------------------- #
# Auth                                                                        #
# --------------------------------------------------------------------------- #

def test_ingest_training_requires_jwt(client):
    resp = client.post(
        "/api/v1/dashboard/training-metrics",
        json={"model_name": "m", "epochs": [{"epoch": 1, "metrics": {}}]},
    )
    assert resp.status_code == 401


def test_read_models_requires_jwt(client):
    resp = client.get("/api/v1/dashboard/training-metrics/models")
    assert resp.status_code == 401


def test_read_telemetry_requires_jwt(client):
    resp = client.get("/api/v1/dashboard/edge-telemetry")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# Ingest — training metrics                                                   #
# --------------------------------------------------------------------------- #

def test_ingest_training_requires_elevated_role(client, operator_headers):
    """Task "treino não pode mentir": operator não tem training:write —
    bloqueado ANTES de qualquer validação de campo (403, nunca chega a
    fabricar métricas)."""
    resp = client.post(
        "/api/v1/dashboard/training-metrics",
        json={"model_name": "yolox-tiny-ppe", "epochs": [{"epoch": 1, "metrics": {}}]},
        headers=operator_headers,
    )
    assert resp.status_code == 403


def test_ingest_training_requires_model_name(client, trainer_headers):
    resp = client.post(
        "/api/v1/dashboard/training-metrics",
        json={"epochs": [{"epoch": 1, "metrics": {}}]},
        headers=trainer_headers,
    )
    assert resp.status_code == 400


def test_ingest_training_requires_epochs(client, trainer_headers):
    resp = client.post(
        "/api/v1/dashboard/training-metrics",
        json={"model_name": "yolox-tiny-ppe", "epochs": []},
        headers=trainer_headers,
    )
    assert resp.status_code == 400


def test_ingest_training_unknown_model_name_404s(client, trainer_headers):
    """Task "treino não pode mentir": model_name que não corresponde a
    nenhum trained_models.name do tenant → 404 (C-01, nunca 403 — não
    revela se o nome existe fora do tenant)."""
    pool, cur = _mock_pool(fetchone=None)
    with patch("app.api.v1.dashboard_edge.routes.DatabasePool") as mock_dp:
        mock_dp.get_instance.return_value = pool
        resp = client.post(
            "/api/v1/dashboard/training-metrics",
            json={
                "model_name": "modelo-inventado-que-nao-existe",
                "epochs": [{"epoch": 1, "metrics": {}}],
            },
            headers=trainer_headers,
        )
    assert resp.status_code == 404
    cur.executemany.assert_not_called()


def test_ingest_training_upserts(client, trainer_headers):
    # fetchone (guarda model_name_exists_for_tenant) → linha real; rowcount
    # (upsert_epochs) → 2 épocas afetadas. Mesmo cursor mockado serve as duas
    # chamadas (SELECT via _execute_one, depois executemany via _execute_many).
    pool, cur = _mock_pool(fetchone={"?column?": 1}, rowcount=2)
    with patch("app.api.v1.dashboard_edge.routes.DatabasePool") as mock_dp:
        mock_dp.get_instance.return_value = pool
        resp = client.post(
            "/api/v1/dashboard/training-metrics",
            json={
                "model_name": "yolox-tiny-ppe",
                "framework": "yolox",
                "epochs": [
                    {"epoch": 1, "metrics": {"ap5095": 0.1}},
                    {"epoch": 2, "metrics": {"ap5095": 0.2}},
                ],
            },
            headers=trainer_headers,
        )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["data"]["upserted"] == 2
    # Modelo validado contra trained_models antes do upsert (guarda nova)
    guard_sql = str(cur.execute.call_args_list[0].args[0])
    assert "FROM trained_models" in guard_sql
    # Upsert idempotente: ON CONFLICT na SQL do executemany
    sql = str(cur.executemany.call_args.args[0])
    assert "ON CONFLICT (tenant_id, model_name, epoch)" in sql
    # tenant_id vem do JWT, é o primeiro parâmetro de cada linha
    params = cur.executemany.call_args.args[1]
    assert all(row[0] == TENANT_A for row in params)


# --------------------------------------------------------------------------- #
# Ingest — edge telemetry                                                     #
# --------------------------------------------------------------------------- #

def test_ingest_telemetry_requires_samples(client, operator_headers):
    resp = client.post(
        "/api/v1/dashboard/edge-telemetry",
        json={"site_id": None, "samples": []},
        headers=operator_headers,
    )
    assert resp.status_code == 400


def test_ingest_telemetry_requires_sampled_at(client, operator_headers):
    resp = client.post(
        "/api/v1/dashboard/edge-telemetry",
        json={"samples": [{"payload": {"gpu_load_pct": 10}}]},
        headers=operator_headers,
    )
    assert resp.status_code == 400


def test_ingest_telemetry_inserts(client, operator_headers, monkeypatch):
    # Sem REDIS_URL o publish ao vivo é no-op (best-effort) — não bloqueia.
    monkeypatch.delenv("REDIS_URL", raising=False)
    pool, cur = _mock_pool(rowcount=1)
    with patch("app.api.v1.dashboard_edge.routes.DatabasePool") as mock_dp:
        mock_dp.get_instance.return_value = pool
        resp = client.post(
            "/api/v1/dashboard/edge-telemetry",
            json={
                "site_id": str(uuid4()),
                "samples": [
                    {
                        "sampled_at": datetime.now(timezone.utc).isoformat(),
                        "label": "mm_all_prod",
                        "payload": {"gpu_load_pct": 72.0},
                    }
                ],
            },
            headers=operator_headers,
        )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["inserted"] == 1
    # INSERT tenant-scoped (tenant_id como 1ª coluna)
    sql = str(cur.executemany.call_args.args[0])
    assert "INSERT INTO public.edge_telemetry_samples" in sql


# --------------------------------------------------------------------------- #
# Read                                                                        #
# --------------------------------------------------------------------------- #

def test_read_training_curves_grouped(client, operator_headers):
    rows = [
        {"model_name": "yolox-tiny-ppe", "framework": "yolox", "epoch": 1,
         "metrics": {"ap5095": 0.1}},
        {"model_name": "yolox-tiny-ppe", "framework": "yolox", "epoch": 2,
         "metrics": {"ap5095": 0.2}},
        {"model_name": "rfdetr-nano-ppe", "framework": "rfdetr", "epoch": 1,
         "metrics": {"ap5095": 0.5}},
    ]
    pool, _ = _mock_pool(fetchall=rows)
    with patch("app.api.v1.dashboard_edge.routes.DatabasePool") as mock_dp:
        mock_dp.get_instance.return_value = pool
        resp = client.get(
            "/api/v1/dashboard/training-metrics?models=yolox-tiny-ppe,rfdetr-nano-ppe",
            headers=operator_headers,
        )
    assert resp.status_code == 200
    models = resp.get_json()["data"]["models"]
    assert len(models["yolox-tiny-ppe"]) == 2
    assert len(models["rfdetr-nano-ppe"]) == 1


def test_read_models_summary(client, operator_headers):
    rows = [
        {"model_name": "yolox-tiny-ppe", "framework": "yolox", "last_epoch": 10,
         "ap5095": "0.712", "ap_small": "0.385", "epoch_count": 10},
    ]
    pool, _ = _mock_pool(fetchall=rows)
    with patch("app.api.v1.dashboard_edge.routes.DatabasePool") as mock_dp:
        mock_dp.get_instance.return_value = pool
        resp = client.get(
            "/api/v1/dashboard/training-metrics/models", headers=operator_headers
        )
    assert resp.status_code == 200
    models = resp.get_json()["data"]["models"]
    assert models[0]["ap_small"] == 0.385  # string JSONB → float
    assert models[0]["epoch_count"] == 10


def test_read_telemetry_invalid_window(client, operator_headers):
    resp = client.get(
        "/api/v1/dashboard/edge-telemetry?window=99y", headers=operator_headers
    )
    assert resp.status_code == 400


def test_read_telemetry_series(client, operator_headers):
    rows = [
        {"site_id": None, "label": "mm_all_prod",
         "sampled_at": "2026-07-17T17:16:03+00:00",
         "payload": {"gpu_load_pct": 72.0}},
    ]
    pool, _ = _mock_pool(fetchall=rows)
    with patch("app.api.v1.dashboard_edge.routes.DatabasePool") as mock_dp:
        mock_dp.get_instance.return_value = pool
        resp = client.get(
            "/api/v1/dashboard/edge-telemetry?window=1h", headers=operator_headers
        )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["window"] == "1h"
    assert data["count"] == 1


# --------------------------------------------------------------------------- #
# Isolamento de tenant REAL (Postgres) — roda no CI; skip local sem DB        #
# --------------------------------------------------------------------------- #

def test_tenant_isolation_real_db(pg_pool, pg_raw):
    """Métrica do tenant A nunca aparece na leitura do tenant B (C-01).

    Usa os fixtures pg_pool/pg_raw (session/tenant reais, conftest.py) em vez
    de DatabasePool.reset()/initialize() manual. O singleton global é
    compartilhado pela sessão inteira do pytest (tests/integration/conftest.py
    o inicializa uma única vez via pg_pool, escopo "session"); chamar
    DatabasePool.reset() aqui fechava o pool real (`close_all()`) e trocava
    a instância, sem nunca restaurar o objeto original — todo teste de
    integração que rodasse DEPOIS deste (test_edge_fleet_overview.py,
    test_edge_heartbeat_summary.py, test_edge_site_detail_update.py, ...)
    reutilizava a mesma fixture pg_pool (cacheada para a sessão) apontando
    para um pool já fechado -> `PoolError: connection pool is closed`.
    ModelTrainingMetricsRepository recebe qualquer DatabasePool via DI
    (BaseRepository.__init__), então não há necessidade nenhuma de tocar no
    singleton global — basta passar o pg_pool da sessão direto pro repo."""
    from app.infrastructure.database.repositories.model_training_metrics_repository import (  # noqa: E501
        ModelTrainingMetricsRepository,
    )

    tid_a, tid_b = str(uuid4()), str(uuid4())
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.tenants (id, name, slug) VALUES (%s,%s,%s),(%s,%s,%s)",
            (tid_a, "A", f"a-{tid_a[:8]}", tid_b, "B", f"b-{tid_b[:8]}"),
        )
    try:
        repo = ModelTrainingMetricsRepository(pg_pool)
        repo.upsert_epochs(
            tid_a, "yolox-tiny-ppe", "yolox",
            [{"epoch": 1, "metrics": {"ap5095": 0.7}}],
        )
        # Idempotência: reingerir a mesma época não duplica
        repo.upsert_epochs(
            tid_a, "yolox-tiny-ppe", "yolox",
            [{"epoch": 1, "metrics": {"ap5095": 0.71}}],
        )
        curves_a = repo.curves(tid_a, [])
        curves_b = repo.curves(tid_b, [])
        assert len(curves_a) == 1, "reingestão duplicou época (upsert falhou)"
        assert curves_a[0]["metrics"]["ap5095"] == 0.71, "upsert não atualizou"
        assert curves_b == [], "vazamento cross-tenant (C-01)"
    finally:
        with pg_raw.cursor() as cur:
            cur.execute(
                "DELETE FROM public.model_training_metrics WHERE tenant_id IN (%s, %s)",
                (tid_a, tid_b),
            )
            cur.execute(
                "DELETE FROM public.tenants WHERE id IN (%s, %s)", (tid_a, tid_b)
            )
