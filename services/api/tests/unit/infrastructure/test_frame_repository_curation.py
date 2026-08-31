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
from datetime import date
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

    def test_camera_ids_filter_uses_any_uuid_array(self):
        repo, cur = self._repo_with_counts()
        cams = [str(uuid4()), str(uuid4())]
        repo.list_images_filtered(TENANT_ID, camera_ids=cams)
        count_sql, count_params = cur.execute.call_args_list[0][0]
        assert "tf.camera_id = ANY(%s::uuid[])" in count_sql
        assert "tf.camera_id = %s" not in count_sql
        assert count_params == (TENANT_ID, cams)

    def test_camera_ids_takes_priority_over_camera_id(self):
        """Multi-seleção (camera_ids) tem prioridade sobre camera_id singular
        — o front nunca manda os dois juntos, mas se mandar, camera_ids
        vence (é o caminho novo; camera_id só existe por compat)."""
        repo, cur = self._repo_with_counts()
        cams = [str(uuid4())]
        single = str(uuid4())
        repo.list_images_filtered(TENANT_ID, camera_id=single, camera_ids=cams)
        count_sql, count_params = cur.execute.call_args_list[0][0]
        assert "tf.camera_id = ANY(%s::uuid[])" in count_sql
        assert single not in count_params
        assert count_params == (TENANT_ID, cams)

    def test_empty_camera_ids_falls_back_to_camera_id(self):
        repo, cur = self._repo_with_counts()
        single = str(uuid4())
        repo.list_images_filtered(TENANT_ID, camera_id=single, camera_ids=[])
        count_sql, count_params = cur.execute.call_args_list[0][0]
        assert "tf.camera_id = %s" in count_sql
        assert count_params == (TENANT_ID, single)


class TestGetFacets:
    def _repo_with_rows(self, camera_rows, status_rows, pending_count=0):
        cur = MagicMock()
        cur.fetchall.side_effect = [camera_rows, status_rows, [{"count": pending_count}]]
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
            pending_count=3,
        )
        result = repo.get_facets(TENANT_ID)
        assert result["status"] == {
            "nao_anotado": 10,
            "anotado": 4,
            "duvida": 2,
            "excluida": 1,
            "proposta_pendente": 3,
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

    def test_status_facet_respects_camera_ids_multi_selection(self):
        """Faceta cruzada: contagem por status acompanha a seleção múltipla
        de câmeras do seletor de treinamento (requisito 6 do filtro)."""
        repo, cur = self._repo_with_rows(camera_rows=[], status_rows=[])
        cams = [str(uuid4()), str(uuid4())]
        repo.get_facets(TENANT_ID, camera_ids=cams)
        status_sql, status_params = cur.execute.call_args_list[1][0]
        assert "tf.camera_id = ANY(%s::uuid[])" in status_sql
        assert cams in status_params

    def test_status_facet_camera_ids_takes_priority_over_camera_id(self):
        repo, cur = self._repo_with_rows(camera_rows=[], status_rows=[])
        cams = [str(uuid4())]
        single = str(uuid4())
        repo.get_facets(TENANT_ID, camera_id=single, camera_ids=cams)
        status_sql, status_params = cur.execute.call_args_list[1][0]
        assert "tf.camera_id = ANY(%s::uuid[])" in status_sql
        assert single not in status_params

    def test_camera_facet_never_filters_by_camera_ids(self):
        """Mesma regra de auto-exclusão de camera_id: a faceta de câmera
        (a própria dimensão) não pode ser restringida por camera_ids —
        senão marcar 3 câmeras zeraria a contagem das demais na lista."""
        repo, cur = self._repo_with_rows(camera_rows=[], status_rows=[])
        cams = [str(uuid4()), str(uuid4())]
        repo.get_facets(TENANT_ID, camera_ids=cams)
        camera_sql, camera_params = cur.execute.call_args_list[0][0]
        assert "tf.camera_id = ANY(%s::uuid[])" not in camera_sql
        assert cams not in camera_params

    def test_empty_status_counts_default_to_zero(self):
        repo, cur = self._repo_with_rows(camera_rows=[], status_rows=[])
        result = repo.get_facets(TENANT_ID)
        assert result["status"] == {
            "nao_anotado": 0, "anotado": 0, "duvida": 0, "excluida": 0,
            "proposta_pendente": 0,
        }

    def test_pending_facet_uses_pending_proposal_condition(self):
        """Chip 'Propostas pendentes' ganha contador (era None — MVP sem
        lote deixava o chip cego). Mesmo predicado único da fila real."""
        repo, cur = self._repo_with_rows(
            camera_rows=[], status_rows=[], pending_count=349,
        )
        result = repo.get_facets(TENANT_ID)
        assert result["status"]["proposta_pendente"] == 349
        pending_sql = cur.execute.call_args_list[2][0][0]
        assert "pre_annotation_review_status IS NULL" in pending_sql
        assert "pre_annotations IS NOT NULL" in pending_sql

    def test_pending_facet_excludes_excluida_by_default(self):
        repo, cur = self._repo_with_rows(camera_rows=[], status_rows=[])
        repo.get_facets(TENANT_ID)
        pending_sql = cur.execute.call_args_list[2][0][0]
        assert "tf.curation_status != 'excluida'" in pending_sql

    def test_pending_facet_is_count_not_jsonb_sum(self):
        """Facet é barata de propósito — COUNT(*), não SUM(jsonb_array_
        length) (esse agregado só se paga na fila ativa, list_images_
        filtered com pending_review=True)."""
        repo, cur = self._repo_with_rows(camera_rows=[], status_rows=[])
        repo.get_facets(TENANT_ID)
        pending_sql = cur.execute.call_args_list[2][0][0]
        assert "jsonb_array_length" not in pending_sql
        assert "COUNT(*)" in pending_sql

    def test_pending_facet_respects_source_and_camera_ids(self):
        repo, cur = self._repo_with_rows(camera_rows=[], status_rows=[])
        cams = [str(uuid4())]
        repo.get_facets(TENANT_ID, source="nvr", camera_ids=cams)
        pending_sql, pending_params = cur.execute.call_args_list[2][0]
        assert "tf.source = %s" in pending_sql
        assert "tf.camera_id = ANY(%s::uuid[])" in pending_sql
        assert pending_params == (TENANT_ID, "nvr", cams)

    def test_pending_facet_never_filters_by_curation_status_arg(self):
        """Mesma regra da faceta de status: 'proposta_pendente' não pode
        ser restringida pelo curation_status escolhido — senão a soma das
        outras facetas por trás do chip mentiria sobre o resto da fila."""
        repo, cur = self._repo_with_rows(camera_rows=[], status_rows=[])
        repo.get_facets(TENANT_ID, curation_status="duvida")
        pending_sql, pending_params = cur.execute.call_args_list[2][0]
        assert "tf.curation_status = %s" not in pending_sql
        assert "duvida" not in pending_params


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


class TestListImagesFilteredProposalClasses:
    """#516 — filtro por classe da aba Classificar (`?proposal_classes=`)."""

    def _repo_with_counts(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"total": 0}
        cur.fetchall.return_value = []
        return _repo(cur)

    def test_proposal_classes_adds_jsonb_match_and_pending_condition(self):
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID, proposal_classes=["mascara", "Sem Mascara"])
        count_sql, count_params = cur.execute.call_args_list[0][0]
        assert "jsonb_array_elements(tf.pre_annotations)" in count_sql
        assert "= ANY(%s::text[])" in count_sql
        # Só proposta PENDENTE conta — mesmo predicado da fila de aprovação.
        assert "tf.pre_annotation_review_status IS NULL" in count_sql
        # Nome normalizado dos dois lados (lower/trim), nunca id.
        assert ["mascara", "sem mascara"] in count_params
        assert "class_id" not in count_sql.split("FROM training_frames tf WHERE", 1)[1]

    def test_proposal_classes_guards_non_array_jsonb(self):
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID, proposal_classes=["mascara"])
        count_sql, _ = cur.execute.call_args_list[0][0]
        assert "jsonb_typeof(tf.pre_annotations) = 'array'" in count_sql

    def test_none_or_empty_proposal_classes_omits_condition(self):
        for valor in (None, []):
            repo, cur = self._repo_with_counts()
            repo.list_images_filtered(TENANT_ID, proposal_classes=valor)
            count_sql, _ = cur.execute.call_args_list[0][0]
            assert "jsonb_array_elements" not in count_sql

    def test_proposal_classes_combines_with_camera_and_cursor(self):
        repo, cur = self._repo_with_counts()
        cam, cursor = str(uuid4()), str(uuid4())
        repo.list_images_filtered(
            TENANT_ID, camera_ids=[cam], proposal_classes=["gloves"], cursor=cursor,
        )
        select_sql, select_params = cur.execute.call_args_list[1][0]
        assert "tf.camera_id = ANY(%s::uuid[])" in select_sql
        assert "jsonb_array_elements" in select_sql
        assert "(tf.created_at, tf.id) <" in select_sql
        assert ["gloves"] in select_params


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


class TestListImagesFilteredCursor:
    """Paginacao por CURSOR (keyset) — o OFFSET pulava metade do acervo.

    OFFSET so e correto sobre conjunto imovel. A fila de anotacao encolhe a
    cada veredito e cresce por cima a cada coleta do NVR, entao a janela
    `OFFSET n*page_size` escorrega e o que fica entre um lote e o proximo
    nunca chega ao anotador (medido no acervo do RVB: 3.521 de 7.081, 49,7%).
    """

    def _repo_with_counts(self):
        cur = MagicMock()
        cur.fetchone.return_value = {"total": 0}
        cur.fetchall.return_value = []
        return _repo(cur)

    def test_sem_cursor_mantem_offset(self):
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID, page=3, page_size=40)
        rows_sql, rows_params = cur.execute.call_args_list[1][0]
        assert "OFFSET %s" in rows_sql
        assert "(tf.created_at, tf.id) <" not in rows_sql
        assert rows_params[-2:] == (40, 80)

    def test_cursor_troca_offset_por_predicado_no_where(self):
        repo, cur = self._repo_with_counts()
        fid = str(uuid4())
        repo.list_images_filtered(TENANT_ID, page=3, page_size=40, cursor=fid)
        rows_sql, rows_params = cur.execute.call_args_list[1][0]
        assert "(tf.created_at, tf.id) < " in rows_sql
        assert "OFFSET" not in rows_sql
        # o par sai de SUBCONSULTA pelo id — nunca de texto vindo do cliente
        assert "SELECT c.created_at, c.id FROM training_frames c" in rows_sql
        assert rows_params[-3:] == (fid, TENANT_ID, 40)

    def test_subconsulta_do_cursor_e_escopada_por_tenant(self):
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID, cursor=str(uuid4()))
        rows_sql = cur.execute.call_args_list[1][0][0]
        assert "c.id = %s AND c.tenant_id = %s" in rows_sql

    def test_cursor_em_ordem_asc_inverte_a_comparacao(self):
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID, order="asc", cursor=str(uuid4()))
        rows_sql = cur.execute.call_args_list[1][0][0]
        assert "(tf.created_at, tf.id) > " in rows_sql

    def test_total_ignora_o_cursor(self):
        """`total` conta o conjunto do FILTRO, nao "quantos faltam".

        Se o cursor entrasse na COUNT, `total` mudaria de significado a cada
        lote sem avisar — e a galeria, que le `total`, nem manda cursor.
        """
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID, cursor=str(uuid4()))
        count_sql, count_params = cur.execute.call_args_list[0][0]
        assert "(tf.created_at, tf.id)" not in count_sql
        assert count_params == (TENANT_ID,)

    def test_order_by_tem_desempate_por_id(self):
        """created_at empatado sem desempate = linha repetida entre paginas."""
        repo, cur = self._repo_with_counts()
        repo.list_images_filtered(TENANT_ID)
        rows_sql = cur.execute.call_args_list[1][0][0]
        assert "ORDER BY tf.created_at DESC, tf.id DESC" in rows_sql


class TestActiveLearningQueueCuration:
    """A fila de active learning servia o que a curadoria ja tinha descartado.

    `list_images_filtered` filtra `curation_status` desde a migration 110;
    este caminho irmao nunca recebeu o mesmo filtro. Curadoria NAO apaga
    frame do banco — sem o predicado, excluida/duvida voltam para a fila.
    """

    def test_exclui_frame_nao_ativo(self):
        cur = MagicMock()
        cur.fetchall.return_value = []
        repo, cur = _repo(cur)
        repo.list_unlabeled_by_uncertainty(TENANT_ID, "epi", limit=5)
        for chamada in cur.execute.call_args_list:
            sql = chamada[0][0]
            assert "tf.curation_status = 'active'" in sql, sql


class TestPropagationPoolCuration:
    """#497 — terceira porta do mesmo enunciado do #496.

    O pool da propagação semeada baixava do R2 e rodava SAM+DINOv2 em frame
    já descartado na curadoria; pior, `apply_propagation_proposals` reseta
    `pre_annotation_review_status` e devolve o descartado pra fila humana.
    """

    def test_pool_exclui_frame_descartado_na_curadoria(self):
        repo, cur = _repo()
        cur.fetchall.return_value = []
        repo.list_for_propagation_pool(
            TENANT_ID, [str(uuid4())], date(2026, 8, 1), date(2026, 8, 2)
        )
        sql = cur.execute.call_args_list[0][0][0]
        assert "curation_status = 'active'" in sql
