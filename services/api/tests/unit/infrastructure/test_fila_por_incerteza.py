"""Fila por incerteza (aprendizado ativo) — e o cursor tem de acompanhar.

`ordenar=incerteza` põe primeiro o recorte cuja proposta está mais perto de
0,5: é onde o modelo está em dúvida e onde o clique do humano ensina mais.

O invariante que este arquivo guarda é o do cursor: **a chave do keyset tem de
ser a MESMA do ORDER BY**. Trocar a ordem sem trocar a chave faz a paginação
pular linhas em silêncio — foi exatamente o defeito que o cursor veio
consertar (#496/#500: OFFSET sobre conjunto que encolhe escondeu 49,7% do
acervo do RVB, e a tela ainda anunciava "fila concluída").

Provado contra o banco do DEV em 25/08:
    recente    → 0,241 0,005 0,072 0,158 0,175 0,194 0,151  (arbitrário)
    incerteza  → 0,005 0,072 0,151 0,158 0,175 0,194 0,241  (crescente)
"""
from __future__ import annotations


from app.infrastructure.database.repositories.frame_repository import FrameRepository

_TENANT = "63c219d8-fbef-4f3c-a7c9-058c742482e2"


def _sql_de(**kwargs) -> tuple[str, tuple]:
    """Roda a query e devolve (sql, params) do SELECT principal."""
    repo = FrameRepository.__new__(FrameRepository)
    chamadas = []

    def _execute(sql, params=None):
        chamadas.append((sql, params))
        return []

    def _execute_one(sql, params=None):
        chamadas.append((sql, params))
        return {"total": 0, "count": 0}

    repo._execute = _execute  # type: ignore[method-assign]
    repo._execute_one = _execute_one  # type: ignore[method-assign]
    repo.list_images_filtered(_TENANT, **kwargs)
    principal = [c for c in chamadas if "FROM training_frames tf" in c[0]]
    return principal[-1]


class TestOrdenacao:
    def test_padrao_continua_por_recencia(self):
        sql, _ = _sql_de(page_size=5)
        assert "ORDER BY tf.created_at" in sql
        assert "ABS((p->>'confidence')" not in sql.split("ORDER BY")[1]

    def test_incerteza_ordena_pela_distancia_a_meio(self):
        sql, _ = _sql_de(page_size=5, ordenar="incerteza")
        ordem = sql.split("ORDER BY")[1]
        assert "ABS((p->>'confidence')::float - 0.5)" in ordem
        assert " ASC" in ordem, "mais duvidoso PRIMEIRO"
        assert "tf.created_at" not in ordem, "recência não desempata incerteza"

    def test_frame_sem_proposta_vai_para_o_fim(self):
        """`COALESCE(..., 1.0)`: sem confiança não há incerteza para ordenar.

        Pô-lo no começo seria ordem arbitrária vestida de prioridade."""
        sql, _ = _sql_de(page_size=5, ordenar="incerteza")
        assert "), 1.0)" in sql

    def test_min_sobre_as_propostas_do_frame(self):
        """Basta UMA proposta duvidosa para o recorte valer a revisão."""
        sql, _ = _sql_de(page_size=5, ordenar="incerteza")
        assert "SELECT MIN(ABS(" in sql


class TestCursorAcompanhaAOrdem:
    """Se a chave do keyset divergir do ORDER BY, a fila pula em silêncio."""

    def test_cursor_de_recencia_usa_created_at(self):
        sql, _ = _sql_de(page_size=5, cursor="11111111-1111-1111-1111-111111111111")
        assert "(tf.created_at, tf.id)" in sql

    def test_cursor_de_incerteza_usa_a_MESMA_expressao_do_order_by(self):
        sql, _ = _sql_de(
            page_size=5, ordenar="incerteza",
            cursor="11111111-1111-1111-1111-111111111111",
        )
        antes, depois = sql.split("ORDER BY")
        assert "(tf.created_at, tf.id)" not in antes, (
            "cursor por created_at com ordem por incerteza pula linha"
        )
        # a expressão do WHERE e a do ORDER BY têm de ser a mesma
        assert "ABS((p->>'confidence')::float - 0.5)" in antes
        assert "ABS((p->>'confidence')::float - 0.5)" in depois

    def test_cursor_de_incerteza_le_a_linha_em_vez_de_confiar_no_cliente(self):
        """O par de corte sai de uma subconsulta pelo id, nunca de texto do
        cliente — foi assim que o cursor perdeu subsegundo na RFC 822."""
        sql, params = _sql_de(
            page_size=5, ordenar="incerteza",
            cursor="11111111-1111-1111-1111-111111111111",
        )
        assert "FROM training_frames c " in sql
        assert "c.id = %s AND c.tenant_id = %s" in sql
        assert "11111111-1111-1111-1111-111111111111" in params

    def test_comparador_de_incerteza_e_maior_que(self):
        """Ordem ASC ⇒ a próxima página é o que vem DEPOIS."""
        sql, _ = _sql_de(
            page_size=5, ordenar="incerteza",
            cursor="11111111-1111-1111-1111-111111111111",
        )
        antes = sql.split("ORDER BY")[0]
        assert "tf.id) > " in antes


class TestARotaNaoDerrubaAFilaPorOrdemInvalida:
    def test_valor_desconhecido_cai_no_padrao(self):
        from app.api.v1.training.image_handlers import _ORDENACOES

        assert _ORDENACOES == {"recente", "incerteza"}

    def test_ordem_invalida_nao_vira_400(self):
        """Ordem é preferência, não filtro: errar aqui não pode tirar a fila
        do ar. O handler loga e usa o padrão."""
        from pathlib import Path

        import app.api.v1.training.image_handlers as mod

        codigo = Path(mod.__file__).read_text(encoding="utf-8")
        # Só o bloco do `ordenar` — a fatia larga pegava a validação seguinte
        # (`source inválido`), que devolve 400 de propósito e não é o alvo.
        trecho = codigo.split("ordenar = request.args.get")[1].split(
            "if source is not None"
        )[0]
        assert "_ORDENACOES" in trecho
        assert "error(" not in trecho, "ordem inválida não devolve 400"
        assert "logger.warning" in trecho, "mas também não passa em silêncio"
