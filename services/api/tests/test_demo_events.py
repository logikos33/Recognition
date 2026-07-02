"""
Recognition — Tests: Demo Events (WS4 Investigação).

Cobre:
1. Endpoints /api/v1/admin/demo-events são superadmin-only (403 para admin/operator)
2. Seed: tenant_id explícito do body, clamp 1..500, module_code validado
3. Remoção: DELETE atinge APENAS demo_events do tenant informado (alerts intocada)
4. Service: violations [{class, confidence}] e created_at dentro dos últimos 7 dias
5. AlertRepository: bucket 'week' não degrada mais para 'hour' (regressão BUG-5)
6. AlertRepository: search_events/timeline com include_demo=True monta UNION ALL
   tenant-scoped nos dois branches; include_demo=False exclui demo_events
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import AuthorizationError, ValidationError
from app.domain.services import demo_event_service
from app.infrastructure.database.repositories.alert_repository import AlertRepository
from app.infrastructure.database.repositories.demo_event_repository import DemoEventRepository

TENANT_A = "22222222-dddd-0000-0000-000000000001"
TENANT_B = "33333333-eeee-0000-0000-000000000002"


# ---------------------------------------------------------------------------
# Fixtures: tokens com roles distintos
# ---------------------------------------------------------------------------

@pytest.fixture
def superadmin_headers(app):
    """JWT com role=superadmin."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={"role": "superadmin"},
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(app):
    """JWT com role=admin (admin de tenant — não é superadmin)."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={"role": "admin"},
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_headers(app):
    """JWT com role=operator (cliente comum)."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={"role": "operator"},
        )
    return {"Authorization": f"Bearer {token}"}


def _mock_sql_pool(fetchall=None, fetchone=None):
    """Pool mockado que captura SQL executado (BaseRepository)."""
    pool = MagicMock()
    conn = pool.get_connection.return_value.__enter__.return_value
    cur = conn.cursor.return_value
    cur.fetchall.return_value = fetchall if fetchall is not None else []
    cur.fetchone.return_value = fetchone
    cur.rowcount = 0
    return pool, cur


# ---------------------------------------------------------------------------
# Endpoints admin — autorização (superadmin only)
# ---------------------------------------------------------------------------

class TestDemoEventsAuthorization:

    def test_seed_superadmin_201_with_tenant_from_body(self, client, superadmin_headers):
        """POST /seed como superadmin → 201 e service recebe tenant_id do body."""
        with patch(
            "app.domain.services.demo_event_service.seed",
            return_value={"created": 30, "batch_id": str(uuid4())},
        ) as mock_seed:
            res = client.post(
                "/api/v1/admin/demo-events/seed",
                headers=superadmin_headers,
                json={"tenant_id": TENANT_A, "module_code": "epi", "count": 30},
            )

        assert res.status_code == 201, f"Esperado 201, obtido {res.status_code}"
        body = res.get_json()
        assert body.get("success") is True
        assert body["data"]["created"] == 30
        assert mock_seed.call_args.kwargs["tenant_id"] == TENANT_A
        assert mock_seed.call_args.kwargs["module_code"] == "epi"

    @pytest.mark.parametrize("headers_fixture", ["admin_headers", "operator_headers"])
    def test_seed_non_superadmin_403(self, client, headers_fixture, request):
        headers = request.getfixturevalue(headers_fixture)
        res = client.post(
            "/api/v1/admin/demo-events/seed",
            headers=headers,
            json={"tenant_id": TENANT_A, "module_code": "epi"},
        )
        assert res.status_code == 403, f"Esperado 403, obtido {res.status_code}"

    @pytest.mark.parametrize("headers_fixture", ["admin_headers", "operator_headers"])
    def test_status_non_superadmin_403(self, client, headers_fixture, request):
        headers = request.getfixturevalue(headers_fixture)
        res = client.get(
            f"/api/v1/admin/demo-events?tenant_id={TENANT_A}", headers=headers
        )
        assert res.status_code == 403

    @pytest.mark.parametrize("headers_fixture", ["admin_headers", "operator_headers"])
    def test_remove_non_superadmin_403(self, client, headers_fixture, request):
        headers = request.getfixturevalue(headers_fixture)
        res = client.delete(
            f"/api/v1/admin/demo-events?tenant_id={TENANT_A}", headers=headers
        )
        assert res.status_code == 403

    def test_unauthenticated_401(self, client):
        res = client.post(
            "/api/v1/admin/demo-events/seed",
            json={"tenant_id": TENANT_A, "module_code": "epi"},
        )
        assert res.status_code in (401, 422)

    def test_seed_without_tenant_id_400(self, client, superadmin_headers):
        res = client.post(
            "/api/v1/admin/demo-events/seed",
            headers=superadmin_headers,
            json={"module_code": "epi"},
        )
        assert res.status_code == 400

    def test_seed_invalid_module_code_400(self, client, superadmin_headers):
        """module_code fora de epi/fueling → 400 (ValidationError do service)."""
        with patch(
            "app.domain.services.demo_event_service._get_repo"
        ) as mock_repo_factory:
            mock_repo_factory.return_value.tenant_exists.return_value = True
            res = client.post(
                "/api/v1/admin/demo-events/seed",
                headers=superadmin_headers,
                json={"tenant_id": TENANT_A, "module_code": "hacking"},
            )
        assert res.status_code == 400

    def test_status_superadmin_200(self, client, superadmin_headers):
        with patch(
            "app.domain.services.demo_event_service.status",
            return_value={"counts": [], "total": 0},
        ):
            res = client.get(
                f"/api/v1/admin/demo-events?tenant_id={TENANT_A}",
                headers=superadmin_headers,
            )
        assert res.status_code == 200
        assert res.get_json()["data"]["total"] == 0


# ---------------------------------------------------------------------------
# Service — seed/remove
# ---------------------------------------------------------------------------

class TestDemoEventService:

    def _patched_repos(self):
        repo = MagicMock()
        repo.tenant_exists.return_value = True
        repo.first_camera_of_tenant.return_value = None
        repo.create_batch.side_effect = lambda tenant, rows: len(rows)
        module_repo = MagicMock()
        module_repo.get_classes.return_value = []
        return repo, module_repo

    def test_seed_non_superadmin_role_raises(self):
        with pytest.raises(AuthorizationError):
            demo_event_service.seed(TENANT_A, "epi", 10, user_role="admin")

    def test_seed_clamps_count_to_500(self):
        repo, module_repo = self._patched_repos()
        with patch.object(demo_event_service, "_get_repo", return_value=repo), \
             patch.object(demo_event_service, "_get_module_repo", return_value=module_repo):
            result = demo_event_service.seed(
                TENANT_A, "epi", 5000, user_role="superadmin"
            )
        assert result["created"] == 500
        rows = repo.create_batch.call_args.args[1]
        assert len(rows) == 500

    def test_seed_clamps_count_to_minimum_1(self):
        repo, module_repo = self._patched_repos()
        with patch.object(demo_event_service, "_get_repo", return_value=repo), \
             patch.object(demo_event_service, "_get_module_repo", return_value=module_repo):
            result = demo_event_service.seed(
                TENANT_A, "epi", 0, user_role="superadmin"
            )
        assert result["created"] == 1

    def test_seed_invalid_module_raises_validation(self):
        repo, module_repo = self._patched_repos()
        with patch.object(demo_event_service, "_get_repo", return_value=repo), \
             pytest.raises(ValidationError):
            demo_event_service.seed(TENANT_A, "quality", 10, user_role="superadmin")

    def test_seed_invalid_tenant_uuid_raises_validation(self):
        with pytest.raises(ValidationError):
            demo_event_service.seed("not-a-uuid", "epi", 10, user_role="superadmin")

    def test_seed_generates_violations_shape_and_recent_created_at(self):
        """violations = [{class, confidence}] e created_at nos últimos 7 dias."""
        import json

        repo, module_repo = self._patched_repos()
        with patch.object(demo_event_service, "_get_repo", return_value=repo), \
             patch.object(demo_event_service, "_get_module_repo", return_value=module_repo):
            demo_event_service.seed(TENANT_A, "epi", 20, user_role="superadmin")

        rows = repo.create_batch.call_args.args[1]
        assert len(rows) == 20
        now = datetime.now()
        seven_days_ago = now - timedelta(days=7, minutes=1)
        for row in rows:
            violations = json.loads(row["violations"])
            assert 1 <= len(violations) <= 2
            for v in violations:
                assert set(v.keys()) == {"class", "confidence"}
                assert isinstance(v["class"], str) and v["class"]
                assert 0.60 <= v["confidence"] <= 0.98
            assert row["confidence"] == max(v["confidence"] for v in violations)
            assert seven_days_ago <= row["created_at"] <= now
            assert row["module_code"] == "epi"
            assert row["camera_label"]

    def test_seed_same_batch_id_for_all_rows(self):
        repo, module_repo = self._patched_repos()
        with patch.object(demo_event_service, "_get_repo", return_value=repo), \
             patch.object(demo_event_service, "_get_module_repo", return_value=module_repo):
            result = demo_event_service.seed(TENANT_A, "fueling", 5, user_role="superadmin")

        rows = repo.create_batch.call_args.args[1]
        batch_ids = {row["batch_id"] for row in rows}
        assert batch_ids == {result["batch_id"]}

    def test_remove_passes_tenant_and_module_to_repo(self):
        repo, _ = self._patched_repos()
        repo.delete_by_tenant.return_value = 12
        with patch.object(demo_event_service, "_get_repo", return_value=repo):
            result = demo_event_service.remove(
                TENANT_A, user_role="superadmin", module_code="epi"
            )
        assert result["deleted"] == 12
        repo.delete_by_tenant.assert_called_once_with(TENANT_A, "epi")

    def test_remove_non_superadmin_raises(self):
        with pytest.raises(AuthorizationError):
            demo_event_service.remove(TENANT_A, user_role="operator")


# ---------------------------------------------------------------------------
# DemoEventRepository — DELETE atinge só demo_events do tenant
# ---------------------------------------------------------------------------

class TestDemoEventRepository:

    def test_delete_scoped_by_tenant_and_table(self):
        """DELETE filtra pelo tenant informado e NUNCA toca a tabela alerts."""
        pool, cur = _mock_sql_pool()
        cur.rowcount = 7
        repo = DemoEventRepository(pool)

        deleted = repo.delete_by_tenant(TENANT_A, "epi")

        assert deleted == 7
        sql, params = cur.execute.call_args.args
        assert "DELETE FROM demo_events" in sql
        assert "alerts" not in sql
        assert "tenant_id = %s" in sql
        assert params == (TENANT_A, "epi")

    def test_delete_without_module_scoped_by_tenant(self):
        pool, cur = _mock_sql_pool()
        cur.rowcount = 3
        repo = DemoEventRepository(pool)

        repo.delete_by_tenant(TENANT_B)

        sql, params = cur.execute.call_args.args
        assert "DELETE FROM demo_events" in sql
        assert params == (TENANT_B,)

    def test_create_batch_inserts_only_into_demo_events(self):
        pool, cur = _mock_sql_pool()
        cur.rowcount = 2
        repo = DemoEventRepository(pool)

        created = repo.create_batch(
            TENANT_A,
            [
                {
                    "camera_id": None,
                    "camera_label": "Pátio (demo)",
                    "module_code": "epi",
                    "violations": '[{"class": "no_helmet", "confidence": 0.9}]',
                    "confidence": 0.9,
                    "batch_id": str(uuid4()),
                    "created_by": None,
                    "created_at": datetime.now(),
                }
            ]
            * 2,
        )

        assert created == 2
        sql = cur.executemany.call_args.args[0]
        assert "INSERT INTO demo_events" in sql
        assert "alerts" not in sql
        params_list = cur.executemany.call_args.args[1]
        assert all(p[0] == TENANT_A for p in params_list)


# ---------------------------------------------------------------------------
# AlertRepository — bucket 'week' e UNION ALL include_demo
# ---------------------------------------------------------------------------

class TestAlertRepositoryEvents:

    def test_timeline_accepts_week_bucket(self):
        """Regressão BUG-5: bucket 'week' não degrada mais para 'hour'."""
        pool, cur = _mock_sql_pool()
        repo = AlertRepository(pool)

        repo.timeline_by_bucket(
            tenant_id=TENANT_A,
            from_ts=datetime(2026, 6, 1),
            to_ts=datetime(2026, 7, 1),
            bucket="week",
            include_demo=False,
        )

        sql = cur.execute.call_args.args[0]
        assert "date_trunc('week'" in sql
        assert "date_trunc('hour'" not in sql

    def test_timeline_invalid_bucket_degrades_to_hour(self):
        pool, cur = _mock_sql_pool()
        repo = AlertRepository(pool)

        repo.timeline_by_bucket(
            tenant_id=TENANT_A,
            from_ts=datetime(2026, 6, 1),
            to_ts=datetime(2026, 7, 1),
            bucket="century; DROP TABLE alerts",
            include_demo=False,
        )

        sql = cur.execute.call_args.args[0]
        assert "date_trunc('hour'" in sql
        assert "DROP TABLE" not in sql

    def test_search_events_include_demo_builds_union_with_is_demo(self):
        """include_demo=True: UNION ALL com os dois branches tenant-scoped."""
        pool, cur = _mock_sql_pool(fetchall=[], fetchone={"count": 0})
        repo = AlertRepository(pool)

        repo.search_events(tenant_id=TENANT_A, include_demo=True)

        # Última execução é a query paginada (a primeira é o COUNT)
        page_sql, page_params = cur.execute.call_args.args
        assert "UNION ALL" in page_sql
        assert "FALSE AS is_demo" in page_sql
        assert "TRUE AS is_demo" in page_sql
        assert "FROM demo_events d" in page_sql
        assert "a.tenant_id = %s" in page_sql
        assert "d.tenant_id = %s" in page_sql
        # Isolamento: tenant aparece 1x por branch (A invisível para B)
        assert list(page_params).count(TENANT_A) == 2

    def test_search_events_include_demo_false_excludes_demo_table(self):
        pool, cur = _mock_sql_pool(fetchall=[], fetchone={"count": 0})
        repo = AlertRepository(pool)

        repo.search_events(tenant_id=TENANT_A, include_demo=False)

        page_sql = cur.execute.call_args.args[0]
        assert "demo_events" not in page_sql
        assert "UNION ALL" not in page_sql

    def test_timeline_include_demo_builds_union(self):
        pool, cur = _mock_sql_pool()
        repo = AlertRepository(pool)

        repo.timeline_by_bucket(
            tenant_id=TENANT_A,
            from_ts=datetime(2026, 6, 24),
            to_ts=datetime(2026, 7, 1),
            bucket="day",
            include_demo=True,
        )

        sql, params = cur.execute.call_args.args
        assert "UNION ALL" in sql
        assert "FROM demo_events d" in sql
        assert list(params).count(TENANT_A) == 2

    def test_search_events_filters_are_parametrized_per_branch(self):
        """Filtros (module/class) replicados nos dois branches, sempre via %s."""
        pool, cur = _mock_sql_pool(fetchall=[], fetchone={"count": 0})
        repo = AlertRepository(pool)

        repo.search_events(
            tenant_id=TENANT_A,
            module_code="epi",
            class_names=["no_helmet"],
            include_demo=True,
        )

        page_sql, page_params = cur.execute.call_args.args
        assert "a.module_code = %s" in page_sql
        assert "d.module_code = %s" in page_sql
        params = list(page_params)
        assert params.count("epi") == 2
        assert params.count('%"class": "no_helmet"%') == 2
        # Zero interpolação do valor do filtro no SQL
        assert "no_helmet" not in page_sql
