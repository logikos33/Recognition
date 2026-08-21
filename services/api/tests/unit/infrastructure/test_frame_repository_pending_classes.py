"""
Tests: FrameRepository.list_images_filtered — `pending_proposal_classes`.

A aba Classificar (intercalação normais/propostas) precisa saber, por item da
fila, de QUAIS classes são as propostas pendentes: só proposta de PRESENÇA de
tipo visível é pré-selecionada, e recorte sem nada pré-selecionado não pode
entrar no braço "propostas". A contagem (`pending_proposals_count`) sozinha
não diz isso — daí a coluna nova, com a mesma normalização (lower/trim) do
filtro ?proposal_classes=.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.frame_repository import FrameRepository

TENANT_ID = str(uuid4())


def _repo():
    cur = MagicMock()
    cur.fetchone.return_value = {"total": 0, "total_pending_proposals": 0}
    cur.fetchall.return_value = []

    @contextmanager
    def _conn_ctx():
        conn = MagicMock()
        conn.cursor.return_value = cur
        yield conn

    pool = MagicMock()
    pool.get_connection.side_effect = _conn_ctx
    return FrameRepository(pool), cur


class TestPendingProposalClasses:
    def test_frames_select_exposes_pending_proposal_classes(self):
        repo, cur = _repo()
        repo.list_images_filtered(TENANT_ID)
        frames_sql = cur.execute.call_args_list[1][0][0]
        assert "AS pending_proposal_classes" in frames_sql
        # Nomes normalizados como o filtro por classe (lower/trim, class ou label legado).
        assert "lower(trim(COALESCE(p->>'class', p->>'label', '')))" in frames_sql
        # Só proposta PENDENTE conta — mesmo predicado de pending_proposals_count.
        assert frames_sql.count("tf.pre_annotation_review_status IS NULL") >= 2
        # Guard de tipo: pre_annotations legado pode não ser array.
        assert "jsonb_typeof(tf.pre_annotations) = 'array'" in frames_sql

    def test_present_in_every_filter_combination(self):
        for kwargs in ({}, {"pending_review": True}, {"proposal_classes": ["mascara"]}):
            repo, cur = _repo()
            repo.list_images_filtered(TENANT_ID, **kwargs)
            assert "AS pending_proposal_classes" in cur.execute.call_args_list[1][0][0]
