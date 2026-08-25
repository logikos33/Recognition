"""Salvar no estúdio não pode transformar caixa do MODELO em caixa humana.

`save_batch` faz delete-then-insert e gravava `source='manual'` cravado em toda
linha. Abrir um frame de proposta aceita e salvar sem tocar em nada convertia a
geometria do modelo em "desenhada por humano" — e o gate de procedência do
treino (#536) decide justamente por esse campo.

Medido no RVB antes do fix: 403 caixas `source='manual'` com coordenadas
IDÊNTICAS às de uma proposta do mesmo frame (v10_base_vencedor 195, v9_best
187, propositor_best 17, propositor 4).
"""
from unittest.mock import MagicMock
from uuid import uuid4

from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
    _chave_geometrica,
)

PROPOSTA = ("Luvas", 0.30, 0.40, 0.10, 0.12)
LOTE, MODELO, REVISOR = uuid4(), uuid4(), uuid4()


def _caixa(class_name, cx, cy, w, h) -> dict:
    return {"class_id": 1, "class_name": class_name, "module_code": "epi",
            "x_center": cx, "y_center": cy, "width": w, "height": h}


def _roda(annotations: list[dict]) -> list[tuple]:
    """Roda save_batch com um cursor falso e devolve os INSERTs emitidos."""
    repo = AnnotationRepository.__new__(AnnotationRepository)
    cur = MagicMock()
    # ⚠️ DICIONÁRIO, não tupla: o pool usa RealDictCursor (connection.py:61).
    # A primeira versão deste duplê devolvia tupla, o código indexava por
    # posição, o teste passou — e a chamada real contra o DEV voltou 500.
    # Duplê que não imita o driver de verdade testa a si mesmo.
    cur.fetchall.return_value = [{
        "class_name": PROPOSTA[0], "x_center": PROPOSTA[1], "y_center": PROPOSTA[2],
        "width": PROPOSTA[3], "height": PROPOSTA[4],
        "source": "pre_annotation", "reviewed_by": REVISOR,
        "proposal_batch_id": LOTE, "proposal_model_id": MODELO,
        "proposal_confidence": 0.87,
    }]
    capturado: list[tuple] = []

    def _exec(transacao):
        return transacao(MagicMock(), cur)

    repo._execute_in_transaction = _exec  # type: ignore[method-assign]
    original = cur.execute

    def espia(sql, params=None):
        if sql.startswith("INSERT"):
            capturado.append(params)
        return original(sql, params)

    cur.execute = espia
    repo.save_batch(uuid4(), annotations, user_id=uuid4())
    return capturado


def test_caixa_nao_tocada_mantem_a_proveniencia_da_proposta():
    inserts = _roda([_caixa(*PROPOSTA)])

    assert len(inserts) == 1
    # ordem do INSERT: ..., source, created_by, reviewed_by, lote, modelo, conf
    source, _created_by, reviewed_by, lote, modelo, conf = inserts[0][-6:]
    assert source == "pre_annotation", (
        "salvar sem tocar converteu geometria do modelo em 'manual' — "
        "é o defeito que contaminou o braço só-humano do #536"
    )
    assert reviewed_by == REVISOR
    assert (lote, modelo, conf) == (LOTE, MODELO, 0.87)


def test_caixa_movida_pelo_humano_vira_manual():
    """Aí a geometria passou pela mão de gente — e é isso que o treino quer."""
    movida = ("Luvas", 0.35, 0.40, 0.10, 0.12)  # x mudou
    inserts = _roda([_caixa(*movida)])

    source, _cb, reviewed_by, lote, modelo, conf = inserts[0][-6:]
    assert source == "manual"
    assert (reviewed_by, lote, modelo, conf) == (None, None, None, None)


def test_caixa_nova_vira_manual():
    inserts = _roda([_caixa("Botas", 0.7, 0.8, 0.2, 0.2)])
    assert inserts[0][-6] == "manual"


def test_mesma_geometria_de_classe_diferente_nao_herda():
    """Trocar a CLASSE é decisão humana, mesmo sem mexer na caixa."""
    inserts = _roda([_caixa("Botas", *PROPOSTA[1:])])
    assert inserts[0][-6] == "manual"


def test_chave_tolera_ruido_de_float_mas_nao_ajuste_real():
    base = _chave_geometrica("Luvas", 0.3, 0.4, 0.1, 0.12)
    # ida e volta por JSON/float não pode quebrar a identidade
    assert _chave_geometrica("Luvas", 0.3 + 1e-12, 0.4, 0.1, 0.12) == base
    # meio por cento de deslocamento é ajuste de gente
    assert _chave_geometrica("Luvas", 0.305, 0.4, 0.1, 0.12) != base
