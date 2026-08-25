"""No fim do treino, `epochs_ran` manda sobre o número do framework.

Medido no A/B do #536: o job 28dc8844 fechou com `current_epoch = 50` e
`metrics.epochs_ran = 17`. Ele parou cedo (early_stopping_patience=8) e o 50
de um callback anterior — o contador cru do framework, que sobe e desce
(#420) — sobreviveu porque a guarda antiga só recusava `epoch > total`.

Comparar dois treinos por esse campo diria "um rodou 50, o outro 17" quando os
dois só convergiram em momentos diferentes.
"""
from app.api.v1.training.job_handlers import _epoca_confiavel

JOB = {"id": "j1", "total_epochs": 50}


def test_no_fim_vale_epochs_ran_e_nao_o_contador_do_framework():
    epoca, _ = _epoca_confiavel(
        JOB,
        {"status": "completed", "epoch": 50, "metrics": {"epochs_ran": 17.0}},
    )
    assert epoca == 17


def test_durante_o_treino_nada_muda():
    """Só o callback final tem `epochs_ran`; no meio, o comportamento é o antigo."""
    epoca, _ = _epoca_confiavel(
        JOB, {"status": "running", "epoch": 12, "metrics": {"stage": 2.0}},
    )
    assert epoca == 12


def test_fim_sem_epochs_ran_cai_no_comportamento_antigo():
    epoca, _ = _epoca_confiavel(
        JOB, {"status": "completed", "epoch": 31, "metrics": {}},
    )
    assert epoca == 31


def test_epochs_ran_ilegivel_nao_derruba_o_callback():
    """Guard de sanidade não pode ser mais frágil que o campo que ele protege."""
    epoca, _ = _epoca_confiavel(
        JOB,
        {"status": "completed", "epoch": 44, "metrics": {"epochs_ran": "dezessete"}},
    )
    assert epoca == 44


def test_epoca_maior_que_o_total_continua_recusada():
    """A guarda do #420 segue de pé para o caminho sem `epochs_ran`."""
    epoca, metrics = _epoca_confiavel(
        JOB, {"status": "running", "epoch": 137, "metrics": {}},
    )
    assert epoca is None
    assert metrics["epoch_reportado_invalido"] == 137


def _fonte_training() -> str:
    """training.py resolvido a partir do teste — o pytest roda de services/api."""
    from pathlib import Path

    # tests/unit/api/ -> unit -> tests -> services/api
    raiz = Path(__file__).resolve().parents[3]
    return (raiz / "app" / "infrastructure" / "queue" / "tasks"
            / "training.py").read_text(encoding="utf-8")


class TestOUltimoEscritorNaoGravaOOrcamento:
    """A task Celery escreve DEPOIS do callback do pod — e escrevia o pedido.

    `dispatch_training` terminava com `update_job("completed", epoch=epochs)`,
    onde `epochs` é o TOTAL PEDIDO. Como esse UPDATE roda depois do callback
    final, ele gravava o orçamento por cima da contagem real e desfazia o
    guard do #420/#536 sem deixar rastro: o job 28dc8844 rodou 17 épocas
    (early stop) e a linha ficou com 50.
    """

    def test_o_codigo_nao_passa_mais_o_total_pedido(self):
        fonte = _fonte_training()
        assert 'update_job("completed", progress=100, epoch=epochs' not in fonte, (
            "`epochs` é o total PEDIDO; gravá-lo como época realizada desfaz o "
            "guard do #420 no último UPDATE do job"
        )
        assert "epochs_ran" in fonte, (
            "a contagem real do pod é `epochs_ran`; sem ela não há o que gravar"
        )

    def test_sem_epochs_ran_preserva_o_que_o_pod_reportou(self):
        """0 cai no NULLIF(...,0) do UPDATE e mantém o valor anterior."""
        import re

        fonte = _fonte_training()
        trecho = re.search(
            r"rodadas = int\(float\(\(metrics or \{\}\)\.get\(\"epochs_ran\"\) or (\d)\)\)",
            fonte,
        )
        assert trecho and trecho.group(1) == "0", (
            "o fallback tem de ser 0 — qualquer outro número INVENTA uma época"
        )
