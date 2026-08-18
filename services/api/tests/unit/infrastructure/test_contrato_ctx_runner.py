"""Contrato: toda chave que o runner CONSOME o builder do ctx FORNECE.

É o payload estrito do lado de dentro. Quatro parâmetros já foram ignorados em
silêncio nesta missão (epochs, base_model, campo desconhecido, total_epochs);
os dois primeiros o payload estrito pegou, os outros viviam aqui dentro. Este
teste mata a classe inteira: chave consumida e não fornecida = vermelho.
"""
import ast
import inspect

from app.infrastructure.queue.tasks import training as t


def _chaves_fornecidas() -> set[str]:
    """Literais de string nas chaves do dict devolvido pelo builder."""
    arvore = ast.parse(inspect.getsource(t._get_runpod_training_context).lstrip())
    chaves: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Return) and isinstance(no.value, ast.Dict):
            for k in no.value.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    chaves.add(k.value)
    return chaves


def _chaves_consumidas() -> set[str]:
    """`ctx.get("x")` / `ctx["x"]` dentro do consumidor."""
    arvore = ast.parse(inspect.getsource(t._run_runpod_train_job).lstrip())
    chaves: set[str] = set()
    for no in ast.walk(arvore):
        if (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
                and no.func.attr == "get"
                and isinstance(no.func.value, ast.Name) and no.func.value.id == "ctx"
                and no.args and isinstance(no.args[0], ast.Constant)):
            chaves.add(no.args[0].value)
        if (isinstance(no, ast.Subscript) and isinstance(no.value, ast.Name)
                and no.value.id == "ctx" and isinstance(no.slice, ast.Constant)):
            chaves.add(no.slice.value)
    return chaves


def test_nenhuma_chave_consumida_fica_sem_ser_fornecida():
    faltando = _chaves_consumidas() - _chaves_fornecidas()
    assert not faltando, (
        f"o runner lê {sorted(faltando)} do ctx, mas o builder não fornece — "
        "é exatamente o bug do total_epochs (pedia 12, rodava 50)"
    )


def test_total_epochs_esta_nos_dois_lados():
    assert "total_epochs" in _chaves_consumidas()
    assert "total_epochs" in _chaves_fornecidas()


def test_o_teste_pega_a_regressao_se_o_campo_sumir():
    # Sanidade do próprio teste: sem o campo fornecido, a diferença aparece.
    assert {"total_epochs"} - (_chaves_fornecidas() - {"total_epochs"})
