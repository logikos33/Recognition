"""
Tests: FrameRepository — curadoria de frames (migration 110).

Cobre:
- list_images_filtered: filtros novos ?camera_id= e ?curation_status=
  (default exclui 'excluida'; explícito filtra exatamente pelo valor pedido)
- get_facets: contagens por câmera e por status, cada faceta respeitando os
  filtros das OUTRAS dimensões (nunca o da própria)
- update_curation_status: UPDATE em lote escopado por tenant_id
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.frame_repository import FrameRepository

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
    return FrameRepository(_pool_with_cursor(cur)), cur


class TestListImagesFilteredCuration:
    def _repo_with_counts(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"total": 0}
        cur.fetchall.return_value = []
        return _repo(cur)

    def test_default_excludes_excluida(self):
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID)
        count_sql, count_params = cur.execute.call_args_list[0][0]
        assert "tf.curation_status != 'excluida'" in count_sql
        assert count_params == (TENANT_ID,)

    def test_explicit_curation_status_filters_exactly(self):
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID, curation_status="excluida")
        count_sql, count_params = cur.execute.call_args_list[0][0]
        assert "tf.curation_status = %s" in count_sql
        assert "!=" not in count_sql
        assert count_params == (TENANT_ID, "excluida")

    def test_explicit_curation_status_duvida(self):
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID, curation_status="duvida")
        count_params = cur.execute.call_args_list[0][0][1]
        assert count_params == (TENANT_ID, "duvida")

    def test_camera_id_filter_adds_condition_and_param(self):
        repo, cur = self._repo_with_counts()
        cam = str(uuid4())
        repo.list_images_filtered(TENANT_ID, camera_id=cam)
        count_sql, count_params = cur.execute.call_args_list[0][0]
        assert "tf.camera_id = %s" in count_sql
        assert cam in count_params

    def test_select_includes_new_columns(self):
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID)
        select_sql = cur.execute.call_args_list[1][0][0]
        assert "tf.camera_id" in select_sql
        assert "tf.curation_status" in select_sql

    def test_select_includes_annotation_count(self):
        """Card da galeria mostra "nº de caixas" — COUNT correlacionado de
        frame_annotations, mesmo padrão bounded-by-page_size do provenance."""
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID)
        select_sql = cur.execute.call_args_list[1][0][0]
        assert "AS annotation_count" in select_sql
        assert "FROM frame_annotations fa" in select_sql

    def test_camera_and_curation_and_source_combine(self):
        repo, cur = self._repo_with_counts()
        cam = str(uuid4())
        repo.list_images_filtered(
            TENANT_ID, camera_id=cam, curation_status="active", source="nvr"
        )
        count_sql, count_params = cur.execute.call_args_list[0][0]
        assert "tf.source = %s" in count_sql
        assert "tf.camera_id = %s" in count_sql
        assert "tf.curation_status = %s" in count_sql
        assert count_params == (TENANT_ID, "nvr", cam, "active")


class TestGetFacets:
    def _repo_with_rows(self, camera_rows, status_rows):
        cur = MagicMock()
        cur.fetchall.side_effect = [camera_rows, status_rows]
        return _repo(cur)

    def test_camera_facet_shape(self):
        cam = uuid4()
        repo, cur = self._repo_with_rows(
            camera_rows=[{"camera_id": cam, "camera_name": "Portaria", "count": 5}],
            status_rows=[],
        )
        result = repo.get_facets(TENANT_ID)
        assert result["cameras"] == [
            {"camera_id": str(cam), "camera_name": "Portaria", "count": 5}
        ]

    def test_camera_facet_does_not_filter_by_own_camera_id(self):
        """Selecionar uma câmera não pode zerar a contagem das DEMAIS câmeras
        — a faceta de câmera nunca filtra pelo próprio camera_id."""
        repo, cur = self._repo_with_rows(camera_rows=[], status_rows=[])
        picked_camera = str(uuid4())
        repo.get_facets(TENANT_ID, camera_id=picked_camera)
        camera_sql, camera_params = cur.execute.call_args_list[0][0]
        assert picked_camera not in camera_params
        assert "tf.camera_id = %s" not in camera_sql

    def test_camera_facet_respects_curation_status_filter(self):
        repo, cur = self._repo_with_rows(camera_rows=[], status_rows=[])
        repo.get_facets(TENANT_ID, curation_status="duvida")
        camera_sql, camera_params = cur.execute.call_args_list[0][0]
        assert "tf.curation_status = %s" in camera_sql
        assert "duvida" in camera_params

    def test_camera_facet_default_excludes_excluida(self):
        repo, cur = self._repo_with_rows(camera_rows=[], status_rows=[])
        repo.get_facets(TENANT_ID)
        camera_sql = cur.execute.call_args_list[0][0][0]
        assert "tf.curation_status != 'excluida'" in camera_sql

    def test_status_facet_partitions_active_by_annotated(self):
        repo, cur = self._repo_with_rows(
            camera_rows=[],
            status_rows=[
                {"curation_status": "active", "is_annotated": False, "count": 10},
                {"curation_status": "active", "is_annotated": True, "count": 4},
                {"curation_status": "duvida", "is_annotated": False, "count": 2},
                {"curation_status": "excluida", "is_annotated": True, "count": 1},
            ],
        )
        result = repo.get_facets(TENANT_ID)
        assert result["status"] == {
            "nao_anotado": 10,
            "anotado": 4,
            "duvida": 2,
            "excluida": 1,
        }

    def test_status_facet_does_not_filter_by_curation_status(self):
        repo, cur = self._repo_with_rows(camera_rows=[], status_rows=[])
        repo.get_facets(TENANT_ID, curation_status="duvida")
        status_sql = cur.execute.call_args_list[1][0][0]
        assert "curation_status = %s" not in status_sql

    def test_status_facet_respects_camera_id_filter(self):
        repo, cur = self._repo_with_rows(camera_rows=[], status_rows=[])
        cam = str(uuid4())
        repo.get_facets(TENANT_ID, camera_id=cam)
        status_sql, status_params = cur.execute.call_args_list[1][0]
        assert "tf.camera_id = %s" in status_sql
        assert cam in status_params

    def test_empty_status_counts_default_to_zero(self):
        repo, cur = self._repo_with_rows(camera_rows=[], status_rows=[])
        result = repo.get_facets(TENANT_ID)
        assert result["status"] == {
            "nao_anotado": 0, "anotado": 0, "duvida": 0, "excluida": 0,
        }


class TestUpdateCurationStatus:
    def test_update_scoped_by_tenant(self):
        cur = MagicMock()
        cur.rowcount = 3
        repo, cur = _repo(cur)
        frame_ids = [uuid4(), uuid4(), uuid4()]
        updated_by = uuid4()
        result = repo.update_curation_status(
            frame_ids=frame_ids, status="duvida", tenant_id=TENANT_ID,
            updated_by=updated_by,
        )
        assert result == 3
        query, params = cur.execute.call_args[0]
        assert "SET curation_status = %s" in query
        assert "WHERE id = ANY(%s::uuid[]) AND tenant_id = %s" in query
        assert params[0] == "duvida"
        assert params[1] == str(updated_by)
        assert params[2] == [str(fid) for fid in frame_ids]
        assert params[3] == TENANT_ID

    def test_update_without_updated_by_is_none(self):
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        repo.update_curation_status(
            frame_ids=[uuid4()], status="excluida", tenant_id=TENANT_ID,
        )
        params = cur.execute.call_args[0][1]
        assert params[1] is None

    def test_never_deletes_row_only_updates(self):
        cur = MagicMock()
        cur.rowcount = 1
        repo, cur = _repo(cur)
        repo.update_curation_status(
            frame_ids=[uuid4()], status="active", tenant_id=TENANT_ID,
        )
        query = cur.execute.call_args[0][0]
        assert "DELETE" not in query.upper()
        assert query.strip().upper().startswith("UPDATE")


class TestListImagesFilteredPendingReview:
    """Fila de aprovação de propostas (migration 111) — ?pending_review=true.

    Pendente = pre_annotations JSONB não vazio E pre_annotation_review_
    status IS NULL (fonte única: _PENDING_PROPOSAL_CONDITION) — SEM
    condição sobre frame_annotations: proposta nova em frame JÁ ANOTADO
    continua na fila até o veredito. Proposta rejeitada estampa 'rejected'
    e sai do filtro (é o buraco de modelo que a 111 fecha).
    """

    def _repo_with_counts(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"total": 0, "total_pending_proposals": 0}
        cur.fetchall.return_value = []
        return _repo(cur)

    def test_pending_review_true_adds_condition(self):
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID, pending_review=True)
        count_sql = cur.execute.call_args_list[0][0][0]
        assert "pre_annotation_review_status IS NULL" in count_sql
        assert "pre_annotations IS NOT NULL" in count_sql

    def test_pending_review_keeps_annotated_frames_in_queue(self):
        """Regressão real (job de propagação com 3 propostas em 2 frames):
        um NOT EXISTS de frame_annotations no WHERE escondia da fila o
        frame que já tinha anotação humana E propostas pendentes — o toast
        anunciava 3 propostas e o filtro mostrava 1 imagem, sem nada ter
        se perdido no banco. Pendente não pode depender de o frame já ter
        (ou não) caixa humana."""
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID, pending_review=True)
        count_sql = cur.execute.call_args_list[0][0][0]
        assert "NOT EXISTS" not in count_sql

    def test_pending_review_aggregates_total_proposals(self):
        """total_pending_proposals vem na MESMA query de COUNT — é o número
        do cabeçalho da fila, que precisa bater com o toast da propagação e
        com a soma dos pending_proposals_count dos cards."""
        repo, cur = self._repo_with_counts()
        cur.fetchone.return_value = {"total": 2, "total_pending_proposals": 3}
        result = repo.list_images_filtered(TENANT_ID, pending_review=True)
        count_sql = cur.execute.call_args_list[0][0][0]
        assert "SUM(jsonb_array_length(tf.pre_annotations))" in count_sql
        assert result["total"] == 2
        assert result["total_pending_proposals"] == 3

    def test_no_pending_review_skips_aggregate(self):
        """Fora da fila o agregado não é computado (None no retorno, sem
        jsonb_array_length na query de COUNT — parse de JSONB tem custo)."""
        repo, cur = self._repo_with_counts()
        result = repo.list_images_filtered(TENANT_ID)
        count_sql = cur.execute.call_args_list[0][0][0]
        assert "jsonb_array_length" not in count_sql
        assert result["total_pending_proposals"] is None

    def test_per_frame_pending_proposals_count_always_selected(self):
        """Todo card ganha pending_proposals_count (CASE por frame no
        SELECT), em QUALQUER filtro — card com proposta e sem caixa humana
        mostrava '0 caixas' e selo '⚠ Proposta' ao mesmo tempo."""
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID)
        frames_sql = cur.execute.call_args_list[1][0][0]
        assert "AS pending_proposals_count" in frames_sql
        assert "jsonb_array_length(tf.pre_annotations)" in frames_sql

    def test_pending_review_false_or_none_omits_condition(self):
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID)
        count_sql = cur.execute.call_args_list[0][0][0]
        assert "pre_annotation_review_status" not in count_sql

        cur.reset_mock()
        repo.list_images_filtered(TENANT_ID, pending_review=False)
        count_sql = cur.execute.call_args_list[0][0][0]
        assert "pre_annotation_review_status" not in count_sql

    def test_pending_review_combines_with_camera_and_source(self):
        repo, cur = self._repo_with_counts()
        cam = str(uuid4())
        repo.list_images_filtered(
            TENANT_ID, pending_review=True, camera_id=cam, source="nvr",
        )
        count_sql, count_params = cur.execute.call_args_list[0][0]
        assert "pre_annotation_review_status IS NULL" in count_sql
        assert "tf.camera_id = %s" in count_sql
        assert "tf.source = %s" in count_sql
        assert cam in count_params


class TestMarkPreAnnotationReview:
    """Estampa de revisão de proposta (migration 111) — accepted/rejected."""

    def test_update_sets_status_by_and_at(self):
        cur = MagicMock()
        fid, uid, tid = uuid4(), uuid4(), TENANT_ID
        cur.fetchone.return_value = {
            "id": fid, "pre_annotation_review_status": "rejected",
        }
        repo, cur = _repo(cur)
        result = repo.mark_pre_annotation_review(fid, "rejected", uid, tid)
        assert result["pre_annotation_review_status"] == "rejected"

        query, params = cur.execute.call_args[0]
        assert "pre_annotation_review_status = %s" in query
        assert "pre_annotation_reviewed_by = %s" in query
        assert "pre_annotation_reviewed_at = NOW()" in query
        assert "RETURNING tf.*" in query
        assert params[0] == "rejected"
        assert str(uid) in params
        assert str(fid) in params
        assert tid in params

    def test_ownership_condition_mirrors_mark_validated(self):
        """Mesmo padrão de posse-no-UPDATE de mark_validated: dono do vídeo
        OU (sem vídeo E tenant do contexto) — defesa em profundidade além
        do ownership check já feito no service via get_by_id_and_user."""
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.mark_pre_annotation_review(uuid4(), "accepted", uuid4(), TENANT_ID)
        query = cur.execute.call_args[0][0]
        assert "EXISTS (SELECT 1 FROM training_videos tv" in query
        assert "tf.video_id IS NULL AND tf.tenant_id = %s" in query

    def test_none_tenant_id_becomes_sql_null_not_string(self):
        """tenant_id=None vira Python None (→ SQL NULL via psycopg2), nunca
        a STRING 'None' — mesmo cuidado de get_by_id_and_user/mark_validated
        (str(tenant_id) quebraria o cast ::uuid do lado do Postgres)."""
        cur = MagicMock()
        cur.fetchone.return_value = None
        repo, cur = _repo(cur)
        repo.mark_pre_annotation_review(uuid4(), "accepted", uuid4(), None)
        params = cur.execute.call_args[0][1]
        assert params[-1] is None
        assert "None" not in params
