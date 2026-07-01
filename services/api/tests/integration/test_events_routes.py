"""
Integration tests: events endpoints (task-049).

Cobertura:
  GET /api/v1/events/search   — filtros, paginação, isolamento por tenant
  GET /api/v1/events/timeline — bucket, validação de input, isolamento

Estratégia idêntica à dos testes de branding:
  - DatabasePool.get_instance() mockado
  - get_storage() mockado (sem R2 real)
  - JWT com additional_claims (tenant_id, role)
  - success() → {"success": True, "data": {...}}
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TENANT_ID = str(uuid4())
OTHER_TENANT_ID = str(uuid4())
CAM_ID = str(uuid4())


@pytest.fixture
def operator_headers(app):
    """JWT com role operator — suficiente para leitura de eventos."""
    with app.app_context():
        from flask_jwt_extended import create_access_token

        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT_ID,
                "role": "operator",
                "tenant_schema": "public",
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(app):
    """JWT com role admin."""
    with app.app_context():
        from flask_jwt_extended import create_access_token

        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT_ID,
                "role": "admin",
                "tenant_schema": "public",
            },
        )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_alert_row(
    tenant_id: str = TENANT_ID,
    camera_id: str | None = None,
    module_code: str = "epi",
    violations: list | None = None,
    confidence: float = 0.92,
    evidence_key: str | None = None,
    created_at: datetime | None = None,
) -> dict:
    return {
        "id": uuid4(),
        "camera_id": uuid4() if camera_id is None else camera_id,
        "module_code": module_code,
        "violations": violations or ["no_helmet"],
        "confidence": confidence,
        "evidence_key": evidence_key,
        "created_at": created_at or datetime(2025, 6, 1, 14, 0, 0, tzinfo=timezone.utc),
    }


def _make_timeline_row(bucket: datetime, count: int) -> dict:
    return {"bucket": bucket, "count": count}


def _mock_pool(fetchone_returns=None, fetchall_returns=None):
    """
    Cria mock de DatabasePool para injeção via patch.

    Dois fetchone e fetchall independentes: o primeiro fetchone é para COUNT(*),
    o segundo é ignorado porque a route usa fetchall para os items.
    Aqui configuramos fetchone com count e fetchall com rows.
    """
    pool = MagicMock()
    conn = MagicMock()
    cur = MagicMock()

    # Para search: primeira chamada = COUNT(*), segunda chamada = rows
    # Para timeline: apenas fetchall
    count_row = fetchone_returns if fetchone_returns is not None else {"count": 0}
    cur.fetchone.return_value = count_row
    cur.fetchall.return_value = fetchall_returns or []

    # BaseRepository usa `cur = conn.cursor()` (chamada direta, sem context manager)
    conn.cursor.return_value = cur
    pool.get_connection.return_value.__enter__.return_value = conn
    pool.get_connection.return_value.__exit__.return_value = False

    return pool


def _mock_storage(url: str | None = None):
    """Storage mock: generate_presigned_download_url retorna URL fixa."""
    storage = MagicMock()
    storage.generate_presigned_download_url.return_value = url or "https://r2.example.com/frame.jpg"
    return storage


# ---------------------------------------------------------------------------
# GET /api/v1/events/search
# ---------------------------------------------------------------------------
class TestSearchEvents:

    def test_requires_jwt(self, client) -> None:
        """Sem JWT → 401/422."""
        res = client.get("/api/v1/events/search")
        assert res.status_code in (401, 422)

    def test_returns_empty_list(self, client, operator_headers) -> None:
        """Sem alertas cadastrados → lista vazia, total=0, pages=1."""
        pool = _mock_pool(fetchone_returns={"count": 0}, fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get("/api/v1/events/search", headers=operator_headers)

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["events"] == []
        assert data["data"]["total"] == 0
        assert data["data"]["pages"] == 1

    def test_returns_events_list(self, client, operator_headers) -> None:
        """Com alertas → lista com campo frame_url quando evidence_key presente."""
        rows = [_make_alert_row(evidence_key="frames/tenant/cam/1.jpg")]
        pool = _mock_pool(fetchone_returns={"count": 1}, fetchall_returns=rows)
        storage = _mock_storage("https://cdn.example.com/frame.jpg")
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get("/api/v1/events/search", headers=operator_headers)

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        events = data["data"]["events"]
        assert len(events) == 1
        assert events[0]["module_code"] == "epi"
        assert events[0]["confidence"] == pytest.approx(0.92)
        assert events[0]["frame_url"] == "https://cdn.example.com/frame.jpg"

    def test_frame_url_none_when_no_evidence(self, client, operator_headers) -> None:
        """Sem evidence_key → frame_url é null."""
        rows = [_make_alert_row(evidence_key=None)]
        pool = _mock_pool(fetchone_returns={"count": 1}, fetchall_returns=rows)
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get("/api/v1/events/search", headers=operator_headers)

        events = res.get_json()["data"]["events"]
        assert events[0]["frame_url"] is None

    def test_pagination_defaults(self, client, operator_headers) -> None:
        """Sem params → page=1, per_page=20."""
        pool = _mock_pool(fetchone_returns={"count": 0}, fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get("/api/v1/events/search", headers=operator_headers)

        d = res.get_json()["data"]
        assert d["page"] == 1
        assert d["per_page"] == 20

    def test_pagination_params(self, client, operator_headers) -> None:
        """page=2&per_page=5 → refletido na resposta."""
        pool = _mock_pool(fetchone_returns={"count": 0}, fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/search?page=2&per_page=5",
                headers=operator_headers,
            )

        d = res.get_json()["data"]
        assert d["page"] == 2
        assert d["per_page"] == 5

    def test_per_page_clamped_to_max(self, client, operator_headers) -> None:
        """per_page > 200 → clamped para 200."""
        pool = _mock_pool(fetchone_returns={"count": 0}, fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/search?per_page=9999",
                headers=operator_headers,
            )

        assert res.get_json()["data"]["per_page"] == 200

    def test_accepts_class_name_filter(self, client, operator_headers) -> None:
        """class_name[] passado → 200 sem erro SQL injection."""
        pool = _mock_pool(fetchone_returns={"count": 0}, fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/search?class_name[]=no_helmet&class_name[]=no_vest",
                headers=operator_headers,
            )

        assert res.status_code == 200

    def test_accepts_camera_id_filter(self, client, operator_headers) -> None:
        """camera_id[] passado → 200."""
        pool = _mock_pool(fetchone_returns={"count": 0}, fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                f"/api/v1/events/search?camera_id[]={CAM_ID}",
                headers=operator_headers,
            )

        assert res.status_code == 200

    def test_accepts_date_range_filter(self, client, operator_headers) -> None:
        """from/to válidos → 200."""
        pool = _mock_pool(fetchone_returns={"count": 0}, fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/search?from=2025-01-01T00:00:00&to=2025-12-31T23:59:59",
                headers=operator_headers,
            )

        assert res.status_code == 200

    def test_invalid_date_ignored_gracefully(self, client, operator_headers) -> None:
        """from inválido → ignorado (não causa 400 ou 500)."""
        pool = _mock_pool(fetchone_returns={"count": 0}, fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/search?from=not-a-date",
                headers=operator_headers,
            )

        assert res.status_code == 200

    def test_min_confidence_filter(self, client, operator_headers) -> None:
        """min_confidence passado → 200."""
        pool = _mock_pool(fetchone_returns={"count": 0}, fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/search?min_confidence=0.8",
                headers=operator_headers,
            )

        assert res.status_code == 200

    def test_invalid_min_confidence_ignored(self, client, operator_headers) -> None:
        """min_confidence inválido → ignorado."""
        pool = _mock_pool(fetchone_returns={"count": 0}, fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/search?min_confidence=abc",
                headers=operator_headers,
            )

        assert res.status_code == 200

    def test_tenant_isolation(self, client, app, operator_headers) -> None:
        """
        O WHERE sempre inclui tenant_id do JWT — não é possível para um
        operador vazar dados de outro tenant passando outro tenant_id.

        Verificamos que o SQL executado contém o tenant_id correto como
        parâmetro (não interpolado).
        """
        pool = _mock_pool(fetchone_returns={"count": 0}, fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get("/api/v1/events/search", headers=operator_headers)

        assert res.status_code == 200
        # O primeiro argumento executado deve conter o TENANT_ID do JWT
        # BaseRepository usa cur = conn.cursor() (direto, sem __enter__)
        cur = pool.get_connection.return_value.__enter__.return_value.cursor.return_value
        all_calls = cur.execute.call_args_list
        assert len(all_calls) >= 1
        # Primeiro execute é o COUNT(*) — seu segundo arg é a tupla de params
        count_call_params = all_calls[0][0][1]  # positional args: (sql, params)
        assert TENANT_ID in count_call_params

    def test_class_name_sql_injection_rejected(self, client, operator_headers) -> None:
        """
        class_name com conteúdo malicioso nunca é interpolado na SQL —
        é passado como parâmetro (ILIKE %s).
        Requisição deve retornar 200 (não 500), provando que não quebrou.
        """
        pool = _mock_pool(fetchone_returns={"count": 0}, fetchall_returns=[])
        storage = _mock_storage()
        malicious = "'; DROP TABLE alerts; --"
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                f"/api/v1/events/search?class_name[]={malicious}",
                headers=operator_headers,
            )

        assert res.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/v1/events/timeline
# ---------------------------------------------------------------------------
class TestEventsTimeline:

    def test_requires_jwt(self, client) -> None:
        """Sem JWT → 401/422."""
        res = client.get("/api/v1/events/timeline")
        assert res.status_code in (401, 422)

    def test_returns_empty_buckets(self, client, operator_headers) -> None:
        """Sem alertas → timeline=[], bucket='hour'."""
        pool = _mock_pool(fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/timeline?from=2025-01-01T00:00:00&to=2025-12-31T23:59:59",
                headers=operator_headers,
            )

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["timeline"] == []
        assert data["data"]["bucket"] == "hour"

    def test_returns_timeline_buckets(self, client, operator_headers) -> None:
        """Com dados → lista de buckets com count."""
        rows = [
            _make_timeline_row(datetime(2025, 6, 1, 14, 0, tzinfo=timezone.utc), 5),
            _make_timeline_row(datetime(2025, 6, 1, 15, 0, tzinfo=timezone.utc), 12),
        ]
        pool = _mock_pool(fetchall_returns=rows)
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/timeline?from=2025-01-01T00:00:00&to=2025-12-31T23:59:59",
                headers=operator_headers,
            )

        data = res.get_json()
        buckets = data["data"]["timeline"]
        assert len(buckets) == 2
        assert buckets[0]["count"] == 5
        assert buckets[1]["count"] == 12
        assert "2025-06-01T14:00:00" in buckets[0]["bucket"]

    def test_default_bucket_is_hour(self, client, operator_headers) -> None:
        """Sem parâmetro bucket → usa 'hour'."""
        pool = _mock_pool(fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/timeline?from=2025-01-01T00:00:00&to=2025-12-31T23:59:59",
                headers=operator_headers,
            )

        assert res.get_json()["data"]["bucket"] == "hour"

    def test_bucket_day(self, client, operator_headers) -> None:
        """bucket=day → bucket='day'."""
        pool = _mock_pool(fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/timeline?bucket=day&from=2025-01-01T00:00:00&to=2025-12-31T23:59:59",
                headers=operator_headers,
            )

        assert res.get_json()["data"]["bucket"] == "day"

    def test_bucket_week(self, client, operator_headers) -> None:
        """bucket=week → bucket='week'."""
        pool = _mock_pool(fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/timeline?bucket=week&from=2025-01-01T00:00:00&to=2025-12-31T23:59:59",
                headers=operator_headers,
            )

        assert res.get_json()["data"]["bucket"] == "week"

    def test_invalid_bucket_falls_back_to_hour(self, client, operator_headers) -> None:
        """bucket inválido → silenciosamente usa 'hour'."""
        pool = _mock_pool(fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/timeline?bucket=month&from=2025-01-01T00:00:00&to=2025-12-31T23:59:59",
                headers=operator_headers,
            )

        assert res.status_code == 200
        assert res.get_json()["data"]["bucket"] == "hour"

    def test_accepts_same_filters_as_search(self, client, operator_headers) -> None:
        """Timeline aceita os mesmos filtros de busca sem erro."""
        pool = _mock_pool(fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/timeline"
                "?class_name[]=no_helmet"
                "&module_code=epi"
                "&from=2025-01-01T00:00:00"
                "&to=2025-12-31T23:59:59"
                "&min_confidence=0.7",
                headers=operator_headers,
            )

        assert res.status_code == 200

    def test_bucket_is_from_allowlist(self, client, operator_headers) -> None:
        """
        O bucket passado ao SQL é sempre da allowlist (hour/day/week).
        Parâmetro arbitrário do user nunca chega ao SQL diretamente.
        """
        pool = _mock_pool(fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/timeline"
                "?bucket=malicious_value'; DROP TABLE alerts; --"
                "&from=2025-01-01T00:00:00&to=2025-12-31T23:59:59",
                headers=operator_headers,
            )

        assert res.status_code == 200
        # Após sanitização, bucket deve ser 'hour' (fallback)
        assert res.get_json()["data"]["bucket"] == "hour"

    def test_tenant_isolation_timeline(self, client, operator_headers) -> None:
        """tenant_id do JWT é sempre o primeiro parâmetro enviado ao SQL."""
        pool = _mock_pool(fetchall_returns=[])
        storage = _mock_storage()
        with (
            patch("app.api.v1.events.routes.DatabasePool.get_instance", return_value=pool),
            patch("app.api.v1.events.routes.get_storage", return_value=storage),
        ):
            res = client.get(
                "/api/v1/events/timeline?from=2025-01-01T00:00:00&to=2025-12-31T23:59:59",
                headers=operator_headers,
            )

        assert res.status_code == 200
        # BaseRepository usa cur = conn.cursor() (direto, sem __enter__)
        cur = pool.get_connection.return_value.__enter__.return_value.cursor.return_value
        execute_call = cur.execute.call_args_list[0]
        sql_params = execute_call[0][1]  # segundo arg posicional
        assert TENANT_ID in sql_params
