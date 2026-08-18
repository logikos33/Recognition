"""
Issue #459 — o dispatch escrevia por cima do que o pod já havia reportado.

`tasks/training.py::update_job` gravava três campos com os DEFAULTS da própria
assinatura (`progress=0`, `epoch=0`, `metrics=None`):

    metrics = %s              -- SOBRESCREVE  (o repository funde com ||)
    progress = %s             -- volta para 0
    current_epoch = %s        -- volta para 0

E ele roda depois do pod existir: `update_fn("running", progress=5)` dispara
logo após a criação do pod, e `update_job("failed", metrics=metrics_falha or
None)` no fim — os dois podem chegar depois de um callback.

O comentário do próprio repository chama `metrics = %s` de *"o 5º 'dois
escritores'"*: o padrão foi reconhecido e corrigido num dos sites. O outro ficou.

Estes testes leem o SQL gerado — é o que dá sem banco, e o defeito É o SQL.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sql_do_update():
    """Grava progresso uma vez e devolve (SQL normalizado, params)."""
    from app.infrastructure.queue.tasks import training as training_mod

    def _rodar(**kwargs):
        repo = MagicMock()
        training_mod._gravar_progresso_do_job(repo, "job-1", **kwargs)
        chamada = repo._execute_mutation_no_return.call_args
        return " ".join(chamada.args[0].split()), chamada.args[1]

    return _rodar


class TestDispatchNaoApagaOQuePodReportou:
    def test_metrics_funde_em_vez_de_sobrescrever(self, sql_do_update):
        sql, _ = sql_do_update(status="running", progress=5)
        assert "metrics = COALESCE(metrics, '{}'::jsonb) || %s::jsonb" in sql
        assert "metrics = %s," not in sql, (
            "`metrics = %s` apaga tudo que o pod reportou — é o defeito do #459"
        )

    def test_progress_nao_anda_para_tras(self, sql_do_update):
        sql, _ = sql_do_update(status="failed")
        assert "progress = GREATEST(COALESCE(progress, 0), %s)" in sql, (
            "um 'failed' sem progress (default 0) zerava 90% de treino já feito"
        )

    def test_epoch_zero_do_dispatch_nao_apaga_a_epoca_real(self, sql_do_update):
        sql, _ = sql_do_update(status="running", progress=5)
        assert "current_epoch = COALESCE(NULLIF(%s, 0), current_epoch)" in sql

    def test_guard_de_stopped_continua(self, sql_do_update):
        """A correção não pode comer o guard que já existia."""
        sql, _ = sql_do_update(status="running", progress=5)
        assert "status != 'stopped'" in sql
