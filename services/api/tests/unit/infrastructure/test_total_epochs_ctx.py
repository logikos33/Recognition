"""O job é a fonte de verdade de total_epochs — e o ctx tem que carregá-la.

O SELECT já buscava tj.total_epochs e o consumidor já fazia
`ctx.get("total_epochs") or epochs`, mas o campo nunca entrava no dict: todo
treino caía no default 50 do parâmetro Celery, em silêncio. Pedir 12 e receber
50 invalida qualquer comparação entre treinos.
"""
import inspect
from app.infrastructure.queue.tasks import training as t


def test_ctx_carrega_total_epochs():
    src = inspect.getsource(t._get_runpod_training_context)
    assert '"total_epochs": job.get("total_epochs")' in src


def test_o_consumidor_prefere_o_valor_do_job():
    src = inspect.getsource(t._run_runpod_train_job)
    assert 'ctx.get("total_epochs") or epochs' in src


def test_resolucao_usa_o_job_quando_presente():
    assert int({"total_epochs": 12}.get("total_epochs") or 50) == 12


def test_resolucao_cai_no_default_so_quando_ausente():
    assert int({}.get("total_epochs") or 50) == 50
    assert int({"total_epochs": None}.get("total_epochs") or 50) == 50
