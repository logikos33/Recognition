"""`%s` em COMENTÁRIO SQL também é placeholder — o psycopg2 não lê comentário.

Em 2026-08-20 um comentário meu explicando o conserto do "dois escritores"
continha a string `metrics = %s`. O psycopg2 faz interpolação por % na string
CRUA, antes de qualquer parser de SQL: aquele `%s` dentro de `--` virou o 11º
placeholder para 10 parâmetros, e o dispatch morreu com
`IndexError: tuple index out of range` — depois de o job nascer, antes de o pod
subir. Custou US$ 0 e uma hora.

Este teste conta placeholders contra parâmetros em cada query do módulo. É burro
de propósito: o defeito também era.
"""
from __future__ import annotations

import ast
import pathlib

ALVO = pathlib.Path(__file__).resolve().parents[3] / "app/infrastructure/queue/tasks/training.py"


def _chamadas_com_sql(arvore: ast.AST) -> list[tuple[str, int, int]]:
    """(sql, n_placeholders, n_params) para toda chamada `_execute*` com tupla literal."""
    achados: list[tuple[str, int, int]] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call) or len(no.args) < 2:
            continue
        nome = getattr(no.func, "attr", "")
        if not nome.startswith("_execute"):
            continue
        sql, params = no.args[0], no.args[1]
        if not isinstance(sql, ast.Constant) or not isinstance(sql.value, str):
            continue
        if not isinstance(params, ast.Tuple):
            continue
        # Conta TODO `%`, não só `%s`. Um `%` solto — "90% de treino" num
        # comentário — também é consumido pelo psycopg2 e desalinha tudo. A
        # primeira versão deste teste contava só `%s`, deu VERDE num código
        # quebrado, e o defeito só apareceu reproduzindo a query no banco.
        achados.append((sql.value, sql.value.count("%"), len(params.elts)))
    return achados


def test_todo_placeholder_tem_parametro() -> None:
    arvore = ast.parse(ALVO.read_text(encoding="utf-8"))
    chamadas = _chamadas_com_sql(arvore)
    assert chamadas, "nenhuma query encontrada — o teste ficou cego"

    for sql, n_ph, n_par in chamadas:
        assert n_ph == n_par, (
            f"{n_ph} placeholders para {n_par} parâmetros.\n"
            f"⚠️ Conferir COMENTÁRIOS: `%s` E `%` solto dentro de `--` contam.\n"
            f"{sql[:200]}"
        )


def test_o_caso_real_de_2026_08_20() -> None:
    """A query do progresso, que quebrou — e o comentário que a quebrou."""
    fonte = ALVO.read_text(encoding="utf-8")
    inicio = fonte.index("UPDATE training_jobs")
    sql = fonte[inicio:fonte.index('"""', inicio)]
    # 11 desde 21/08: a guarda anti-ressurreição do #510 acrescentou um %s
    # (`AND NOT (%s = 'running' AND status IN ('completed','failed'))`), que
    # impede a reentrega do broker devolver a 'running' um job já fechado pelo
    # callback do pod. O número em si não é o ponto do teste — o ponto é que
    # `count("%")` e `count("%s")` sejam IGUAIS: psycopg2 interpola a string
    # CRUA, então um % solto (inclusive dentro de comentário SQL) desalinha os
    # parâmetros e quebra em produção. Foi assim duas vezes (#503 e #506).
    assert sql.count("%") == sql.count("%s"), (
        "todo % tem de ser placeholder — % solto, mesmo em comentário SQL, "
        "desalinha a tupla de parâmetros (incidentes #503 e #506)"
    )
    assert sql.count("%s") == 11, (
        "11 parâmetros: status, progress, epoch, metrics, 4x erro, status(completed_at), "
        "id, status(guarda anti-ressurreição do #510)"
    )
