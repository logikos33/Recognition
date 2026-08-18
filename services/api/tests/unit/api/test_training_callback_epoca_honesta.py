"""
Issue #420 — `training_jobs.current_epoch` reportava passo, não época.

O job `f31f5381` fechou com `current_epoch = 50` e `total_epochs = 12`. Durante
o TREINO 1 o campo subiu a 49, **voltou a 32**, depois a 13 — contador de passo.
Isso já produziu conclusão errada nesta missão ("rodou 12 épocas porque
current_epoch=12"), e a barra de progresso da UI lê este campo.

Época maior que o total pedido não é época. ⛔ Não se grava, ⛔ não se trunca:
truncar inventaria um número plausível. O valor cru vai para `metrics` com nome
que diz o que ele é.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

_JOB_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_TOKEN = "callback-token-valido-de-verdade"


def _chamar(app, *, body: dict, total_epochs):
    from app.api.v1.training.job_handlers import training_progress_callback_handler

    repo = MagicMock()
    repo.get_job_by_id.return_value = {
        "id": _JOB_ID, "callback_token": _TOKEN, "total_epochs": total_epochs,
    }
    with app.test_request_context(
        f"/api/v1/training/jobs/{_JOB_ID}/progress-callback",
        method="POST",
        json=body,
        headers={"X-Callback-Token": _TOKEN},
    ), patch(
        "app.api.v1.training.job_handlers._get_training_repo", return_value=repo,
    ):
        training_progress_callback_handler(_JOB_ID)
    return repo.update_job_status.call_args


class TestEpocaHonesta:
    def test_epoca_dentro_do_total_e_gravada(self, app) -> None:
        call = _chamar(
            app,
            body={"status": "running", "progress": 50, "epoch": 6, "metrics": {"loss": 1.2}},
            total_epochs=12,
        )
        assert call.kwargs["current_epoch"] == 6
        assert call.kwargs["metrics"] == {"loss": 1.2}

    def test_epoca_igual_ao_total_e_gravada(self, app) -> None:
        call = _chamar(
            app,
            body={"status": "running", "progress": 99, "epoch": 12, "metrics": {}},
            total_epochs=12,
        )
        assert call.kwargs["current_epoch"] == 12

    def test_caso_real_50_com_total_12_nao_e_gravado(self, app) -> None:
        """O job f31f5381, exatamente como aconteceu."""
        call = _chamar(
            app,
            body={"status": "running", "progress": 90, "epoch": 50, "metrics": {"loss": 0.4}},
            total_epochs=12,
        )
        assert call.kwargs["current_epoch"] is None, "50 não é época de um treino de 12"
        assert call.kwargs["metrics"]["epoch_reportado_invalido"] == 50
        assert call.kwargs["metrics"]["loss"] == 0.4, "métrica legítima não se perde"

    def test_sem_total_epochs_nao_inventa_regra(self, app) -> None:
        call = _chamar(
            app,
            body={"status": "running", "progress": 10, "epoch": 3, "metrics": {}},
            total_epochs=None,
        )
        assert call.kwargs["current_epoch"] == 3

    def test_callback_sem_epoch_passa_none(self, app) -> None:
        call = _chamar(
            app, body={"status": "running", "progress": 10, "metrics": {}}, total_epochs=12
        )
        assert call.kwargs["current_epoch"] is None

    def test_total_epochs_como_string_ainda_barra(self, app) -> None:
        """total_epochs já apareceu como str em caminho legado."""
        call = _chamar(
            app,
            body={"status": "running", "progress": 90, "epoch": 50, "metrics": {}},
            total_epochs="12",
        )
        assert call.kwargs["current_epoch"] is None

    def test_total_epochs_ilegivel_nao_derruba_o_callback(self, app) -> None:
        """Guard de sanidade não pode ser mais frágil que o campo que protege."""
        call = _chamar(
            app,
            body={"status": "running", "progress": 90, "epoch": 7, "metrics": {}},
            total_epochs="doze",
        )
        assert call.kwargs["current_epoch"] == 7
