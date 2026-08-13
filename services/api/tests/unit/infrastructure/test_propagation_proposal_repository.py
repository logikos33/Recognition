"""
Tests: PropagationProposalRepository (migration 118 — ledger por-proposta).

Cobre:
- list_proposals: WHERE por tenant/status/job/classe/confiança/câmera,
  ordenação whitelisted, facets by_class (força status=pending, ignora o
  próprio class_names)
- reject_batch: filtros combinados (job/class/confidence/seleção), guarda
  contra rejeitar sem NENHUM filtro, escopo por tenant sempre presente
  (nunca vaza pra outro tenant), NUNCA faz DELETE (rejeitado é dado de
  avaliação), reconstrói a projeção dos frames afetados
- reject_one / mark_accepted: None quando a linha já não está mais pending
  (corrida/cross-tenant/inexistente) — nunca reconstrói projeção nesse caso
- replace_frame_proposals: DELETE só das linhas pending + INSERT das novas
- mark_frame_rows_status: sync do estúdio legado, rebuild condicional
- _REBUILD_PROJECTION_SQL: só agrega linhas 'pending' (rejeitada nunca
  volta pro JSONB)
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.infrastructure.database.repositories.propagation_proposal_repository import (
    PropagationProposalRepository,
)

TENANT_ID = str(uuid4())


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
    return PropagationProposalRepository(_pool_with_cursor(cur)), cur


class TestListProposals:
    def _repo_with_rows(self, count=0, rows=None, facet_rows=None):
        cur = MagicMock()
        cur.fetchone.return_value = {"total": count}
        cur.fetchall.side_effect = [rows or [], facet_rows or []]
        return _repo(cur)

    def test_default_scopes_by_tenant_and_pending_status(self):
        repo, cur = self._repo_with_rows()
        repo.list_proposals(TENANT_ID)
        count_sql, count_params = cur.execute.call_args_list[0][0]
        assert "pp.tenant_id = %s" in count_sql
        assert "pp.status = %s" in count_sql
        assert count_params == (TENANT_ID, "pending")

    def test_job_id_filter_adds_condition(self):
        repo, cur = self._repo_with_rows()
        job_id = str(uuid4())
        repo.list_proposals(TENANT_ID, job_id=job_id)
        count_sql, count_params = cur.execute.call_args_list[0][0]
        assert "pp.job_id = %s" in count_sql
        assert job_id in count_params

    def test_class_names_filter_uses_any(self):
        repo, cur = self._repo_with_rows()
        repo.list_proposals(TENANT_ID, class_names=["capacete", "colete"])
        count_sql, count_params = cur.execute.call_args_list[0][0]
        assert "pp.class_name = ANY(%s)" in count_sql
        assert ["capacete", "colete"] in count_params

    def test_confidence_range_filters(self):
        repo, cur = self._repo_with_rows()
        repo.list_proposals(TENANT_ID, confidence_min=0.2, confidence_max=0.8)
        count_sql, count_params = cur.execute.call_args_list[0][0]
        assert "pp.confidence >= %s" in count_sql
        assert "pp.confidence <= %s" in count_sql
        assert 0.2 in count_params
        assert 0.8 in count_params

    def test_camera_ids_filter_uses_uuid_array_on_joined_frame(self):
        repo, cur = self._repo_with_rows()
        cams = [str(uuid4()), str(uuid4())]
        repo.list_proposals(TENANT_ID, camera_ids=cams)
        count_sql, count_params = cur.execute.call_args_list[0][0]
        assert "tf.camera_id = ANY(%s::uuid[])" in count_sql
        assert cams in count_params

    def test_joins_training_frames_for_r2_key(self):
        repo, cur = self._repo_with_rows()
        repo.list_proposals(TENANT_ID)
        select_sql = cur.execute.call_args_list[1][0][0]
        assert "JOIN training_frames tf ON tf.id = pp.frame_id" in select_sql
        assert "tf.r2_key" in select_sql

    def test_sort_and_order_whitelisted_default_confidence_asc(self):
        repo, cur = self._repo_with_rows()
        repo.list_proposals(TENANT_ID)
        select_sql = cur.execute.call_args_list[1][0][0]
        assert "ORDER BY pp.confidence ASC NULLS LAST" in select_sql

    def test_sort_by_class_name_desc(self):
        repo, cur = self._repo_with_rows()
        repo.list_proposals(TENANT_ID, sort="class_name", order="desc")
        select_sql = cur.execute.call_args_list[1][0][0]
        assert "ORDER BY pp.class_name DESC" in select_sql
        assert "NULLS LAST" not in select_sql

    def test_invalid_sort_falls_back_to_confidence(self):
        repo, cur = self._repo_with_rows()
        repo.list_proposals(TENANT_ID, sort="'; DROP TABLE x; --")
        select_sql = cur.execute.call_args_list[1][0][0]
        assert "ORDER BY pp.confidence" in select_sql
        assert "DROP TABLE" not in select_sql

    def test_invalid_order_falls_back_to_asc(self):
        repo, cur = self._repo_with_rows()
        repo.list_proposals(TENANT_ID, order="whatever")
        select_sql = cur.execute.call_args_list[1][0][0]
        assert "ASC" in select_sql

    def test_row_shape_includes_nested_frame(self):
        row = {
            "id": uuid4(), "frame_id": uuid4(), "job_id": None,
            "class_name": "capacete", "confidence": 0.7, "bbox": [0.5, 0.5, 0.1, 0.1],
            "status": "pending", "source": "propagation",
            "r2_key": "frames/a.jpg", "width": 640, "height": 480, "camera_id": None,
        }
        repo, cur = self._repo_with_rows(count=1, rows=[row])
        result = repo.list_proposals(TENANT_ID)
        assert result["proposals"][0]["frame"]["r2_key"] == "frames/a.jpg"
        assert result["proposals"][0]["job_id"] is None
        assert result["total"] == 1

    def test_facets_force_pending_status_regardless_of_requested_status(self):
        repo, cur = self._repo_with_rows()
        repo.list_proposals(TENANT_ID, status="rejected")
        facet_sql, facet_params = cur.execute.call_args_list[2][0]
        assert "GROUP BY pp.class_name" in facet_sql
        assert "pending" in facet_params

    def test_facets_ignore_class_names_own_dimension(self):
        """Selecionar uma classe não pode zerar a contagem das demais na
        UI — a faceta by_class nunca filtra pela própria dimensão."""
        repo, cur = self._repo_with_rows()
        repo.list_proposals(TENANT_ID, class_names=["capacete"])
        facet_sql, facet_params = cur.execute.call_args_list[2][0]
        assert "class_name = ANY" not in facet_sql
        assert ["capacete"] not in facet_params

    def test_facets_respect_job_and_confidence_filters(self):
        repo, cur = self._repo_with_rows()
        job_id = str(uuid4())
        repo.list_proposals(TENANT_ID, job_id=job_id, confidence_min=0.5)
        facet_sql, facet_params = cur.execute.call_args_list[2][0]
        assert "pp.job_id = %s" in facet_sql
        assert "pp.confidence >= %s" in facet_sql
        assert job_id in facet_params

    def test_facets_shape(self):
        repo, cur = self._repo_with_rows(
            facet_rows=[{"class_name": "capacete", "count": 3}],
        )
        result = repo.list_proposals(TENANT_ID)
        assert result["facets"]["by_class"] == [{"class_name": "capacete", "count": 3}]

    def test_pagination_shape(self):
        repo, cur = self._repo_with_rows(count=125)
        result = repo.list_proposals(TENANT_ID, page=2, page_size=60)
        assert result["page"] == 2
        assert result["page_size"] == 60
        assert result["total_pages"] == 3
        select_params = cur.execute.call_args_list[1][0][1]
        assert select_params[-2:] == (60, 60)  # LIMIT 60 OFFSET 60


class TestRejectBatch:
    def _cur_with_rows(self, frame_ids):
        cur = MagicMock()
        cur.fetchall.return_value = [{"frame_id": fid} for fid in frame_ids]
        return cur

    def test_no_filter_raises_value_error(self):
        repo, cur = _repo()
        with pytest.raises(ValueError):
            repo.reject_batch(TENANT_ID, str(uuid4()), reason="selection")
        cur.execute.assert_not_called()

    def test_reject_by_job_id(self):
        fid = str(uuid4())
        cur = self._cur_with_rows([fid])
        repo, cur = _repo(cur)
        job_id = str(uuid4())
        reviewed_by = str(uuid4())
        result = repo.reject_batch(TENANT_ID, reviewed_by, reason="job", job_id=job_id)

        update_sql, update_params = cur.execute.call_args_list[0][0]
        assert "job_id = %s" in update_sql
        assert "status = 'rejected'" in update_sql
        assert "DELETE" not in update_sql.upper()
        assert job_id in update_params
        assert TENANT_ID in update_params
        assert result["rejected_count"] == 1
        assert result["affected_frames"] == [fid]

    def test_reject_by_class_names(self):
        cur = self._cur_with_rows([str(uuid4())])
        repo, cur = _repo(cur)
        result = repo.reject_batch(
            TENANT_ID, str(uuid4()), reason="class", class_names=["capacete"],
        )
        update_sql, update_params = cur.execute.call_args_list[0][0]
        assert "class_name = ANY(%s)" in update_sql
        assert ["capacete"] in update_params
        assert result["rejected_count"] == 1

    def test_reject_by_confidence_lt(self):
        cur = self._cur_with_rows([str(uuid4())])
        repo, cur = _repo(cur)
        repo.reject_batch(TENANT_ID, str(uuid4()), reason="confidence", confidence_lt=0.3)
        update_sql, update_params = cur.execute.call_args_list[0][0]
        assert "confidence < %s" in update_sql
        assert 0.3 in update_params

    def test_reject_by_selection_proposal_ids(self):
        cur = self._cur_with_rows([str(uuid4())])
        repo, cur = _repo(cur)
        pids = [str(uuid4()), str(uuid4())]
        repo.reject_batch(TENANT_ID, str(uuid4()), reason="selection", proposal_ids=pids)
        update_sql, update_params = cur.execute.call_args_list[0][0]
        assert "id = ANY(%s::uuid[])" in update_sql
        assert pids in update_params

    def test_reject_by_frame_ids(self):
        cur = self._cur_with_rows([str(uuid4())])
        repo, cur = _repo(cur)
        fids = [str(uuid4())]
        repo.reject_batch(TENANT_ID, str(uuid4()), reason="selection", frame_ids=fids)
        update_sql, update_params = cur.execute.call_args_list[0][0]
        assert "frame_id = ANY(%s::uuid[])" in update_sql
        assert fids in update_params

    def test_always_scoped_by_tenant_id_never_leaks_cross_tenant(self):
        """Escopo por tenant_id SEMPRE presente no WHERE — ids de outro
        tenant simplesmente não casam a cláusula, sem 404/403 (C-01)."""
        cur = self._cur_with_rows([])
        repo, cur = _repo(cur)
        repo.reject_batch(TENANT_ID, str(uuid4()), reason="selection", proposal_ids=[str(uuid4())])
        update_sql, update_params = cur.execute.call_args_list[0][0]
        assert "tenant_id = %s" in update_sql
        assert TENANT_ID in update_params

    def test_only_targets_pending_rows(self):
        cur = self._cur_with_rows([])
        repo, cur = _repo(cur)
        repo.reject_batch(TENANT_ID, str(uuid4()), reason="selection", proposal_ids=[str(uuid4())])
        update_sql = cur.execute.call_args_list[0][0][0]
        assert "status = 'pending'" in update_sql

    def test_rebuilds_projection_of_affected_frames(self):
        f1, f2 = str(uuid4()), str(uuid4())
        cur = self._cur_with_rows([f1, f2, f1])  # linha duplicada no mesmo frame
        repo, cur = _repo(cur)
        result = repo.reject_batch(
            TENANT_ID, str(uuid4()), reason="selection", proposal_ids=[str(uuid4())],
        )
        assert result["rejected_count"] == 3
        assert result["affected_frame_count"] == 2  # DISTINCT frame_id
        assert sorted(result["affected_frames"]) == sorted([f1, f2])

        rebuild_sql, rebuild_params = cur.execute.call_args_list[1][0]
        assert "pp.status = 'pending'" in rebuild_sql
        assert "jsonb_agg" in rebuild_sql
        assert sorted(rebuild_params[0]) == sorted([f1, f2])
        assert rebuild_params[1] == TENANT_ID

    def test_no_rows_matched_skips_projection_rebuild(self):
        cur = self._cur_with_rows([])
        repo, cur = _repo(cur)
        result = repo.reject_batch(
            TENANT_ID, str(uuid4()), reason="selection", proposal_ids=[str(uuid4())],
        )
        assert result["rejected_count"] == 0
        assert result["affected_frames"] == []
        cur.execute.assert_called_once()  # só o UPDATE, sem rebuild


class TestRejectOne:
    def test_success_rebuilds_projection_and_returns_row(self):
        fid, pid, reviewer = uuid4(), uuid4(), uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": pid, "frame_id": fid, "status": "rejected"}
        repo, cur = _repo(cur)

        result = repo.reject_one(TENANT_ID, reviewer, pid, reason="selection")

        assert result["status"] == "rejected"
        update_sql, update_params = cur.execute.call_args_list[0][0]
        assert "status = 'rejected'" in update_sql
        assert "status = 'pending'" in update_sql
        assert "DELETE" not in update_sql.upper()
        assert str(pid) in update_params
        assert str(reviewer) in update_params

        rebuild_sql, rebuild_params = cur.execute.call_args_list[1][0]
        assert "jsonb_agg" in rebuild_sql
        assert rebuild_params[0] == [str(fid)]

    def test_not_pending_or_cross_tenant_returns_none_without_rebuild(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)

        result = repo.reject_one(TENANT_ID, uuid4(), uuid4())

        assert result is None
        cur.execute.assert_called_once()  # nenhum rebuild disparado


class TestMarkAccepted:
    def test_success_rebuilds_projection(self):
        fid, pid, reviewer = uuid4(), uuid4(), uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": pid, "frame_id": fid, "status": "accepted"}
        repo, cur = _repo(cur)

        result = repo.mark_accepted(TENANT_ID, pid, "accepted", reviewer)

        assert result["status"] == "accepted"
        update_sql = cur.execute.call_args_list[0][0][0]
        assert "status = 'pending'" in update_sql  # só trava linha ainda pendente
        rebuild_sql = cur.execute.call_args_list[1][0][0]
        assert "jsonb_agg" in rebuild_sql

    def test_status_corrected_is_passed_through(self):
        fid, pid, reviewer = uuid4(), uuid4(), uuid4()
        cur = MagicMock()
        cur.fetchone.return_value = {"id": pid, "frame_id": fid, "status": "corrected"}
        repo, cur = _repo(cur)

        repo.mark_accepted(TENANT_ID, pid, "corrected", reviewer)

        update_params = cur.execute.call_args_list[0][0][1]
        assert "corrected" in update_params

    def test_race_returns_none_without_rebuild(self):
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)

        result = repo.mark_accepted(TENANT_ID, uuid4(), "accepted", uuid4())

        assert result is None
        cur.execute.assert_called_once()


class TestGetProposal:
    def test_scoped_by_tenant_and_joins_module_code(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"id": uuid4(), "module_code": "epi"}
        repo, cur = _repo(cur)

        repo.get_proposal(TENANT_ID, uuid4())

        query, params = cur.execute.call_args[0]
        assert "JOIN training_frames tf ON tf.id = pp.frame_id" in query
        assert "pp.tenant_id = %s" in query
        assert TENANT_ID in params


class TestReplaceFrameProposals:
    def test_deletes_only_pending_rows_then_inserts_new(self):
        frame_id, tenant_id, job_id = uuid4(), TENANT_ID, uuid4()
        cur = MagicMock()
        repo, cur = _repo(cur)

        proposals = [
            {"bbox": [0.5, 0.5, 0.1, 0.1], "class": "capacete", "confidence": 0.9},
            {"bbox": [0.3, 0.3, 0.1, 0.1], "class": "colete", "confidence": 0.7},
        ]
        count = repo.replace_frame_proposals(frame_id, tenant_id, job_id, proposals)

        assert count == 2
        delete_sql, delete_params = cur.execute.call_args_list[0][0]
        assert delete_sql.strip().upper().startswith("DELETE")
        assert "status = 'pending'" in delete_sql
        assert str(frame_id) in delete_params

        insert_calls = cur.execute.call_args_list[1:]
        assert len(insert_calls) == 2
        for call in insert_calls:
            sql, params = call[0]
            assert sql.strip().upper().startswith("INSERT")
            assert "'pending'" in sql
            assert str(job_id) in params

    def test_job_id_none_becomes_sql_null(self):
        cur = MagicMock()
        repo, cur = _repo(cur)
        repo.replace_frame_proposals(
            uuid4(), TENANT_ID, None,
            [{"bbox": [0.5, 0.5, 0.1, 0.1], "class": "capacete", "confidence": 0.5}],
        )
        insert_params = cur.execute.call_args_list[1][0][1]
        assert insert_params[2] is None

    def test_empty_proposals_only_deletes(self):
        cur = MagicMock()
        repo, cur = _repo(cur)
        count = repo.replace_frame_proposals(uuid4(), TENANT_ID, uuid4(), [])
        assert count == 0
        cur.execute.assert_called_once()


class TestMarkFrameRowsStatus:
    def test_rejected_sets_manual_reason_and_rebuilds(self):
        cur = MagicMock()
        cur.rowcount = 2
        repo, cur = _repo(cur)
        frame_id, reviewer = uuid4(), uuid4()

        count = repo.mark_frame_rows_status(
            frame_id, TENANT_ID, "rejected", reviewer, reason="manual",
        )

        assert count == 2
        update_sql, update_params = cur.execute.call_args_list[0][0]
        assert "status = %s" in update_sql
        assert "status = 'pending'" in update_sql
        assert "rejected" in update_params
        assert "manual" in update_params

        rebuild_sql = cur.execute.call_args_list[1][0][0]
        assert "jsonb_agg" in rebuild_sql

    def test_accepted_has_no_reason(self):
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        repo.mark_frame_rows_status(uuid4(), TENANT_ID, "accepted", uuid4())
        update_params = cur.execute.call_args_list[0][0][1]
        assert update_params[2] is None

    def test_zero_rows_skips_rebuild(self):
        cur = MagicMock()
        cur.rowcount = 0
        repo, cur = _repo(cur)
        count = repo.mark_frame_rows_status(uuid4(), TENANT_ID, "accepted", uuid4())
        assert count == 0
        cur.execute.assert_called_once()

    def test_reviewed_by_none_becomes_sql_null(self):
        cur = MagicMock()
        cur.rowcount = 0
        repo, cur = _repo(cur)
        repo.mark_frame_rows_status(uuid4(), TENANT_ID, "rejected", None, reason="manual")
        update_params = cur.execute.call_args_list[0][0][1]
        assert update_params[1] is None


class TestRebuildProjectionSql:
    """A SQL de reconstrução da projeção (contrato) só agrega linhas
    'pending' — proposta rejeitada NUNCA volta a aparecer no JSONB do
    frame, mesmo que a linha em si nunca seja deletada."""

    def test_only_aggregates_pending_rows(self):
        sql = PropagationProposalRepository._REBUILD_PROJECTION_SQL
        assert "pp.status = 'pending'" in sql
        assert "jsonb_build_object" in sql
        assert "'[]'::jsonb" in sql  # sem linha pending -> projeção vazia

    def test_skips_execute_when_no_frame_ids(self):
        cur = MagicMock()
        repo, cur = _repo(cur)
        repo._rebuild_projection(cur, [], TENANT_ID)
        cur.execute.assert_not_called()
