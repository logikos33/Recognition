"""
Tests: AnnotationRepository — yolo_classes tenant-scoped (migration 093).
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.infrastructure.database.repositories.annotation_repository import AnnotationRepository


def _pool_with_cursor(mock_cursor):
    @contextmanager
    def _conn_ctx():
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        yield mock_conn

    mock_pool = MagicMock()
    mock_pool.get_connection.side_effect = _conn_ctx
    return mock_pool


def _repo(mock_cursor=None):
    cur = mock_cursor or MagicMock()
    return AnnotationRepository(_pool_with_cursor(cur)), cur


class TestCreateClassTenantScoped:
    def test_missing_tenant_id_raises_type_error(self):
        """Fail-closed (mesmo padrão do #313/#315): tenant_id é keyword-only
        sem default — não existe mais fallback silencioso via
        `(SELECT tenant_id FROM users WHERE id = ...)` (tenant DE CASA,
        divergente do contexto assumido). Chamar sem tenant_id é um erro de
        programação, não um caminho válido."""
        uid = uuid4()
        repo, _ = _repo()
        with pytest.raises(TypeError):
            repo.create_class(uid, "Capacete", "#22c55e")  # type: ignore[call-arg]

    def test_explicit_tenant_required_no_coalesce_from_users(self):
        tenant = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 2, "tenant_id": str(tenant)}
        repo, cur = _repo(cur)
        result = repo.create_class(uuid4(), "Bico", "#f00", tenant_id=tenant)
        assert result["id"] == 2
        query, params = cur.execute.call_args[0]
        assert "tenant_id" in query
        assert "module_code" in query
        assert "SELECT tenant_id FROM users" not in query
        assert params[3] == str(tenant)
        assert params[4] is None          # module_code → COALESCE 'epi'

    def test_explicit_tenant_and_module(self):
        tenant = uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 2}
        repo, cur = _repo(cur)
        repo.create_class(uuid4(), "Bico", "#f00", tenant_id=tenant, module_code="fueling")
        params = cur.execute.call_args[0][1]
        assert params[3] == str(tenant)
        assert params[4] == "fueling"


class TestGetClassesForTenant:
    def test_tenant_with_user_fallback(self):
        """Fallback p/ linhas legadas: tenant_id IS NULL AND user_id = dono."""
        tenant = str(uuid4())
        uid = uuid4()
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": 1, "name": "Capacete"}]
        repo, cur = _repo(cur)
        result = repo.get_classes_for_tenant(tenant, user_id=uid)
        assert len(result) == 1
        query, params = cur.execute.call_args[0]
        assert "tenant_id = %s OR (tenant_id IS NULL AND user_id = %s)" in query
        assert "module_code = %s" in query
        assert params == (tenant, str(uid), "epi")

    def test_tenant_only_no_fallback(self):
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_classes_for_tenant(tenant, module_code="fueling")
        query, params = cur.execute.call_args[0]
        assert "user_id" not in query
        assert params == (tenant, "fueling")

    def test_legacy_get_classes_by_user_untouched(self):
        uid = uuid4()
        cur = MagicMock()
        cur.fetchall.return_value = [{"id": 1}]
        repo, cur = _repo(cur)
        repo.get_classes_by_user(uid)
        query, params = cur.execute.call_args[0]
        assert "WHERE user_id = %s" in query
        assert params == (str(uid),)

    def test_exclude_archived_adds_condition(self):
        """migration 110 — usado pelo anotador (ModuleService.get_classes)
        para não oferecer classe aposentada."""
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_classes_for_tenant(tenant, exclude_archived=True)
        query = cur.execute.call_args[0][0]
        assert "archived_at IS NULL" in query

    def test_exclude_archived_false_is_backward_compatible(self):
        """Default (False) preserva a query exata de antes da 110 — callers
        de gestão (TenantClassService.list_classes) e validação
        (annotation_service) continuam vendo tudo."""
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_classes_for_tenant(tenant, module_code="fueling")
        query, params = cur.execute.call_args[0]
        assert "archived_at" not in query
        assert query == (
            "SELECT * FROM yolo_classes "
            "WHERE tenant_id = %s AND module_code = %s "
            "ORDER BY id"
        )
        assert params == (tenant, "fueling")

    def test_order_by_curation_uses_display_order(self):
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_classes_for_tenant(tenant, order_by_curation=True)
        query = cur.execute.call_args[0][0]
        assert "ORDER BY display_order NULLS LAST, id" in query

    def test_exclude_archived_and_order_with_user_fallback(self):
        tenant = str(uuid4())
        uid = uuid4()
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.get_classes_for_tenant(
            tenant, user_id=uid, exclude_archived=True, order_by_curation=True
        )
        query = cur.execute.call_args[0][0]
        assert "archived_at IS NULL" in query
        assert "ORDER BY display_order NULLS LAST, id" in query


class TestGetUsageCountsByTenant:
    def test_returns_class_id_to_count_map(self):
        tenant = str(uuid4())
        cur = MagicMock()
        cur.fetchall.return_value = [
            {"class_id": 0, "n": 7},
            {"class_id": 100_042, "n": 3},
        ]
        repo, cur = _repo(cur)
        result = repo.get_usage_counts_by_tenant(tenant)
        assert result == {0: 7, 100_042: 3}
        query, params = cur.execute.call_args[0]
        assert "JOIN training_frames tf ON tf.id = fa.frame_id" in query
        assert "tf.tenant_id = %s" in query
        assert params == (tenant,)

    def test_empty_when_no_annotations(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        assert repo.get_usage_counts_by_tenant(str(uuid4())) == {}


class TestPatchClassRepository:
    def test_patch_name_builds_single_set(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 5, "name": "Novo"}
        repo, cur = _repo(cur)
        result = repo.patch_class(5, "tenant-1", {"name": "Novo"})
        assert result["name"] == "Novo"
        query, params = cur.execute.call_args[0]
        assert "SET name = %s" in query
        assert "WHERE id = %s AND tenant_id = %s" in query
        assert params == ("Novo", 5, "tenant-1")

    def test_patch_multiple_fields(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 5}
        repo, cur = _repo(cur)
        repo.patch_class(5, "tenant-1", {"name": "N", "color": "#fff000", "display_order": 3})
        query, params = cur.execute.call_args[0]
        assert "name = %s" in query
        assert "color = %s" in query
        assert "display_order = %s" in query
        assert params == ("N", "#fff000", 3, 5, "tenant-1")

    def test_patch_archived_true_sets_now(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 5, "archived_at": "2026-08-10"}
        repo, cur = _repo(cur)
        repo.patch_class(5, "tenant-1", {"archived": True})
        query, params = cur.execute.call_args[0]
        assert "archived_at = NOW()" in query
        assert params == (5, "tenant-1")  # nenhum param extra p/ archived

    def test_patch_archived_false_sets_null(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 5, "archived_at": None}
        repo, cur = _repo(cur)
        repo.patch_class(5, "tenant-1", {"archived": False})
        query = cur.execute.call_args[0][0]
        assert "archived_at = NULL" in query

    def test_patch_no_fields_reads_existing(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": 5, "name": "X"}
        repo, cur = _repo(cur)
        result = repo.patch_class(5, "tenant-1", {})
        assert result["id"] == 5
        query = cur.execute.call_args[0][0]
        assert query.startswith("SELECT * FROM yolo_classes")

    def test_patch_other_tenant_returns_none(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        result = repo.patch_class(5, "tenant-1", {"name": "X"})
        assert result is None


class TestDeleteClassNamespacedGuard:
    """Migration 103 removeu a FK de frame_annotations.class_id para
    yolo_classes(id) — o valor gravado é o id NAMESPACED (class_namespace),
    não o id cru. count/delete precisam checar pelo id efetivamente usado."""

    def test_delete_uses_referenced_class_id_when_given(self):
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        repo.delete_class(5, "tenant-1", referenced_class_id=100_005)
        query, params = cur.execute.call_args[0]
        assert "a.class_id = %s" in query
        assert params == (5, "tenant-1", 100_005)

    def test_delete_falls_back_to_raw_class_id_when_omitted(self):
        """Compat: caller antigo que não passa referenced_class_id continua
        funcionando (mesmo SQL de antes da 110)."""
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        repo.delete_class(5, "tenant-1")
        params = cur.execute.call_args[0][1]
        assert params == (5, "tenant-1", 5)

    def test_delete_with_user_fallback_and_referenced_id(self):
        uid = uuid4()
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        repo.delete_class(5, "tenant-1", user_id=uid, referenced_class_id=100_005)
        query, params = cur.execute.call_args[0]
        assert "a.class_id = %s" in query
        assert params == (5, "tenant-1", str(uid), 100_005)
