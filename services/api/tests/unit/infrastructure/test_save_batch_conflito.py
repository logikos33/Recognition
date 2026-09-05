"""Dois anotadores, um frame: o segundo save NÃO pode apagar o do primeiro.

#801, medido no DEV em 05/09: o Estúdio entrega a mesma fila na mesma ordem
para todo mundo e `save_batch` é delete-then-insert cego. A sequência real
gravada na issue (frame `2e9dcee9`, o PRIMEIRO da fila dos dois):

    POST (A) → 200 {"saved":1}   GET → 1 caixa, created_by = A
    POST (B) → 200 {"saved":1}   GET → SÓ a caixa de B

A caixa de A sumiu, os dois viram 200 e ninguém foi avisado. Aqui o segundo
POST chega com a versão que ELE leu (frame vazio) e o frame já mudou — tem de
virar 409 nominal, com a transação inteira em rollback: nenhum DELETE.

Mesmo critério do 409 da fila de Verificação (`verification_service.
human_review`, onda 1): só o trabalho de OUTRA PESSOA bloqueia; re-salvar o
próprio segue permitido.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError
from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
    VERSAO_VAZIA,
    versao_das_linhas,
)

ANA, BRUNO = uuid4(), uuid4()
AGORA = datetime.now(timezone.utc)


def _caixa_no_banco(autor, quando=AGORA, **extra):
    """Linha de `frame_annotations` como o RealDictCursor devolve."""
    linha = {
        "id": uuid4(), "class_name": "Luvas",
        "x_center": 0.3, "y_center": 0.4, "width": 0.1, "height": 0.12,
        "source": "manual", "reviewed_by": None, "proposal_batch_id": None,
        "proposal_model_id": None, "proposal_confidence": None,
        "created_by": autor, "created_at": quando,
    }
    linha.update(extra)
    return linha


def _payload(cx=0.8):
    return [{"class_id": 1, "class_name": "Botas", "module_code": "epi",
             "x_center": cx, "y_center": 0.8, "width": 0.1, "height": 0.1}]


def _roda(linhas_no_banco, *, user_id, versao_esperada, nome_do_autor="Ana"):
    """Roda save_batch com cursor falso. Devolve os SQLs emitidos."""
    repo = AnnotationRepository.__new__(AnnotationRepository)
    cur = MagicMock()
    cur.fetchall.return_value = linhas_no_banco
    cur.fetchone.return_value = {"name": nome_do_autor}
    emitidos: list[str] = []

    def espia(sql, params=None):
        emitidos.append(sql)

    cur.execute = espia
    repo._execute_in_transaction = lambda fn: fn(MagicMock(), cur)  # type: ignore[method-assign]
    repo.save_batch(uuid4(), _payload(), user_id=user_id,
                    versao_esperada=versao_esperada)
    return emitidos


class TestGuardaDeVersao:
    def test_save_de_outra_pessoa_no_meio_do_caminho_vira_409_e_nao_apaga_nada(self):
        """O caso do #801 ponta a ponta: B leu o frame VAZIO, A gravou, B salva."""
        do_ana = [_caixa_no_banco(str(ANA))]

        with pytest.raises(ConflictError) as excecao:
            _roda(do_ana, user_id=BRUNO, versao_esperada=VERSAO_VAZIA)

        assert excecao.value.status_code == 409
        # Nominal: QUEM e QUANDO, sem UUID cru na cara do anotador (mesma
        # régua do `_quem_julgou` da Verificação).
        assert "Ana" in str(excecao.value)
        assert "agora há pouco" in str(excecao.value)
        assert str(ANA) not in str(excecao.value)

    def test_conflito_nao_emite_delete(self):
        """A garantia dura: ⛔ ZERO DELETE que perca anotação humana."""
        emitidos: list[str] = []
        repo = AnnotationRepository.__new__(AnnotationRepository)
        cur = MagicMock()
        cur.fetchall.return_value = [_caixa_no_banco(str(ANA))]
        cur.fetchone.return_value = {"name": "Ana"}
        cur.execute = lambda sql, params=None: emitidos.append(sql)
        repo._execute_in_transaction = lambda fn: fn(MagicMock(), cur)  # type: ignore[method-assign]

        with pytest.raises(ConflictError):
            repo.save_batch(uuid4(), _payload(), user_id=BRUNO,
                            versao_esperada=VERSAO_VAZIA)

        assert not any(sql.startswith("DELETE") for sql in emitidos)
        assert not any(sql.startswith("INSERT") for sql in emitidos)

    def test_versao_que_bate_grava_normalmente(self):
        do_ana = [_caixa_no_banco(str(ANA))]
        emitidos = _roda(do_ana, user_id=BRUNO,
                         versao_esperada=versao_das_linhas(do_ana))
        assert any(sql.startswith("DELETE") for sql in emitidos)
        assert any(sql.startswith("INSERT") for sql in emitidos)

    def test_reescrever_o_proprio_trabalho_nunca_e_conflito(self):
        """Espelha o `OR verified_by = %s` da Verificação: mudar de ideia sobre
        o que EU gravei continua valendo. Sem isto, aceitar uma proposta
        (accept_pre_annotations cria linhas novas, logo versão nova) faria o
        próprio anotador levar 409 na edição seguinte do mesmo frame."""
        meu = [_caixa_no_banco(str(BRUNO))]
        emitidos = _roda(meu, user_id=BRUNO, versao_esperada="versao-velha-minha")
        assert any(sql.startswith("DELETE") for sql in emitidos)

    def test_caixa_sem_autor_nao_bloqueia(self):
        """created_by NULL = Celery/propagação/script, não é gente (mesma
        regra do veredito 'claude-haiku' que não bloqueia na Verificação)."""
        da_maquina = [_caixa_no_banco(None)]
        emitidos = _roda(da_maquina, user_id=BRUNO, versao_esperada=VERSAO_VAZIA)
        assert any(sql.startswith("DELETE") for sql in emitidos)

    def test_frame_esvaziado_por_alguem_bloqueia_sem_nome(self):
        """Versão mudou e não sobrou linha para atribuir: alguém apagou tudo
        entre a minha leitura e o meu save. Sem nome para citar, mas 409 —
        re-gravar por cima desfaria a decisão do outro em silêncio."""
        with pytest.raises(ConflictError) as excecao:
            _roda([], user_id=BRUNO, versao_esperada="tinha-caixa-quando-eu-li")
        assert "Outro anotador" in str(excecao.value)

    def test_sem_versao_o_comportamento_antigo_continua(self):
        """Chamada interna (Celery, script) não tem cliente para mandar versão."""
        emitidos = _roda([_caixa_no_banco(str(ANA))], user_id=BRUNO,
                         versao_esperada=None)
        assert any(sql.startswith("DELETE") for sql in emitidos)

    def test_trava_da_linha_do_frame_vem_antes_de_qualquer_escrita(self):
        """Sem FOR UPDATE, dois saves simultâneos leem a MESMA versão e os dois
        passam pela conferência — e o caso real do #801 é justamente o frame
        VAZIO, onde não existe linha de anotação para travar."""
        emitidos = _roda([], user_id=BRUNO, versao_esperada=VERSAO_VAZIA)
        assert emitidos[0] == "SELECT id FROM training_frames WHERE id = %s FOR UPDATE"


class TestVersao:
    def test_frame_sem_caixa_tem_versao_legivel(self):
        assert versao_das_linhas([]) == VERSAO_VAZIA

    def test_versao_nao_depende_da_ordem_das_linhas(self):
        a, b = _caixa_no_banco(str(ANA)), _caixa_no_banco(str(BRUNO))
        assert versao_das_linhas([a, b]) == versao_das_linhas([b, a])

    def test_conjunto_diferente_de_caixas_muda_a_versao(self):
        a, b = _caixa_no_banco(str(ANA)), _caixa_no_banco(str(BRUNO))
        assert versao_das_linhas([a]) != versao_das_linhas([a, b])
        assert versao_das_linhas([a]) != VERSAO_VAZIA


class TestMensagem:
    def test_cita_o_autor_mais_recente_quando_ha_varios(self):
        antigo = _caixa_no_banco(str(ANA), quando=AGORA - timedelta(hours=3))
        recente = _caixa_no_banco(str(BRUNO), quando=AGORA - timedelta(minutes=5))
        with pytest.raises(ConflictError) as excecao:
            _roda([antigo, recente], user_id=uuid4(),
                  versao_esperada=VERSAO_VAZIA, nome_do_autor="Bruno")
        assert "Bruno" in str(excecao.value)
        assert "há 5 minutos" in str(excecao.value)

    def test_diz_o_que_fazer_sem_jargao_de_http(self):
        with pytest.raises(ConflictError) as excecao:
            _roda([_caixa_no_banco(str(ANA))], user_id=BRUNO,
                  versao_esperada=VERSAO_VAZIA)
        frase = str(excecao.value)
        assert "recarregue o frame" in frase.lower()
        assert "409" not in frase and "conflict" not in frase.lower()
