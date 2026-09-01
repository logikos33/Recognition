"""
Tests: FrameRepository.list_images_filtered — câmera arquivada/rascunho x
fila de CLASSIFICAÇÃO e galeria de Anotar (task B4, "critério fantasma").

Achado medido no DEV: a fila da aba Classificar (only_crops=True) exigia,
ao mesmo tempo, proposta de IA pendente (proposal_classes) E câmera com
is_active=true. Das 8 câmeras is_active=false do tenant RVB, 100% (159/159)
dos recortes elegíveis (não-anotado + proposta pendente + formato recorte)
pertenciam a elas — a interseção com câmera ativa era ZERO, vazio por
construção assim que qualquer filtro de classe entrava.

O recorte já existe e já foi MINERADO antes do arquivamento da câmera —
negar o veredito humano sobre ele não protege o modelo de nada, só descarta
trabalho feito.

RODADA 3 (veredito do cético, QUEBRA 2): a galeria (only_crops ausente)
tinha o MESMO defeito — `is_active` é sobrecarregado entre câmera ARQUIVADA
(intencional) e câmera RASCUNHO de import em lote (create_draft, nunca
ativada) que já pode ter frame de triagem via snapshot ONVIF. O filtro
`f885fd028` escondia da galeria de Anotar material de câmera que nunca foi
arquivada. Removido — nenhuma das três superfícies (fila, galeria, export)
filtra mais por `cameras.is_active`.
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

    def test_gallery_without_only_crops_also_ignores_camera_active(self):
        """RODADA 3 (QUEBRA 2): a galeria (only_crops ausente) NÃO filtra
        mais por câmera arquivada/rascunho — mesma causa raiz da fila e do
        export. Câmera RASCUNHO de import (is_active=false, nunca
        arquivada) pode ter frame de triagem via snapshot ONVIF antes de
        qualquer decisão humana; escondê-lo da galeria de Anotar era o
        mesmo "critério fantasma" da fila, só que sem nome ainda."""
        repo, cur = _repo()
        repo.list_images_filtered(TENANT_ID)
        count_sql = cur.execute.call_args_list[0][0][0]
        assert _CAMERA_ACTIVE_CLAUSE not in count_sql
