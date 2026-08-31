"""
Tests: FrameRepository.list_images_filtered — câmera arquivada x fila de
CLASSIFICAÇÃO (task B4, "critério fantasma").

Achado medido no DEV: a fila da aba Classificar (only_crops=True) exigia,
ao mesmo tempo, proposta de IA pendente (proposal_classes) E câmera com
is_active=true. Das 8 câmeras is_active=false do tenant RVB, 100% (159/159)
dos recortes elegíveis (não-anotado + proposta pendente + formato recorte)
pertenciam a elas — a interseção com câmera ativa era ZERO, vazio por
construção assim que qualquer filtro de classe entrava.

O recorte já existe e já foi MINERADO antes do arquivamento da câmera —
negar o veredito humano sobre ele não protege o modelo de nada, só descarta
trabalho feito. A galeria/export (only_crops ausente) continua excluindo
câmera arquivada — comportamento intencional de f885fd028, não deste fix.
"""
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.frame_repository import FrameRepository

TENANT_ID = str(uuid4())

_CAMERA_ACTIVE_CLAUSE = "cam.is_active = TRUE"


def _repo():
    cur = MagicMock()
    cur.fetchone.return_value = {"total": 0}
    cur.fetchall.return_value = []

    @contextmanager
    def _conn_ctx():
        conn = MagicMock()
        conn.cursor.return_value = cur
        yield conn

    pool = MagicMock()
    pool.get_connection.side_effect = _conn_ctx
    return FrameRepository(pool), cur


class TestOnlyCropsIgnoresCameraActive:
    def test_only_crops_does_not_filter_by_camera_active(self):
        repo, cur = _repo()
        repo.list_images_filtered(TENANT_ID, only_crops=True)
        count_sql = cur.execute.call_args_list[0][0][0]
        assert _CAMERA_ACTIVE_CLAUSE not in count_sql

    def test_only_crops_with_proposal_classes_ignores_camera_active(self):
        """A combinação exata do bug: filtro de classe (proposal_classes) +
        only_crops era a fila zerada por construção no DEV."""
        repo, cur = _repo()
        repo.list_images_filtered(
            TENANT_ID, only_crops=True, proposal_classes=["mascara"]
        )
        count_sql = cur.execute.call_args_list[0][0][0]
        assert _CAMERA_ACTIVE_CLAUSE not in count_sql

    def test_gallery_without_only_crops_still_filters_by_camera_active(self):
        """Comportamento intencional preservado: galeria/export continuam
        ignorando câmera arquivada (f885fd028) — só a fila de classificação
        (only_crops=True) fica de fora desta condição."""
        repo, cur = _repo()
        repo.list_images_filtered(TENANT_ID)
        count_sql = cur.execute.call_args_list[0][0][0]
        assert _CAMERA_ACTIVE_CLAUSE in count_sql
