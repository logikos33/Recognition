"""
Tests: remote_train.py — acumulação de métricas no callback por-época (RF-DETR).

remote_train.py roda NA GPU remota (zero import do pacote app/) — importado
aqui via importlib a partir do path do arquivo, não como parte da suíte
services/api/tests/. Framework rfdetr é substituído por um fake mínimo
(sem instalar torch/rfdetr) — só o suficiente para disparar
model.callbacks["on_fit_epoch_end"].

Achado da revisão adversarial (falha-antes/passa-depois): o callback
por-época enviava só o log daquela época (`metrics`), não o acumulado
(`last_metrics`) — como o backend faz UPDATE...SET metrics=%s (overwrite,
não merge), uma chave só logada em epoch 1 (ex.: loss) sumia do
progresso ao vivo assim que epoch 2 logava outra chave (ex.: map50) sem
repetir loss. Fix: enviar dict(last_metrics) acumulado.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).parent / "remote_train.py"


class _FakeRFDETRModel:
    """Fake mínimo: só o suficiente para exercitar on_fit_epoch_end."""

    def __init__(self) -> None:
        self.callbacks: dict[str, list] = {"on_fit_epoch_end": []}
        self.epoch_logs: list[dict] = []

    def train(self, **_kwargs) -> None:
        for log in self.epoch_logs:
            for cb in self.callbacks["on_fit_epoch_end"]:
                cb(log)

    def export(self, **_kwargs) -> None:
        pass  # sem .onnx real — train_rfdetr levanta RuntimeError depois,
        # após os callbacks já terem disparado (é o que o teste observa)


@pytest.fixture
def remote_train_mod(tmp_path, monkeypatch):
    """Importa remote_train.py isolado, com OUTPUT_DIR/WORK_DIR em tmp_path
    (o módulo real usa /root — não pode rodar em máquina de dev/CI)."""
    spec = importlib.util.spec_from_file_location(
        "remote_train_under_test", _MODULE_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["remote_train_under_test"] = mod
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod, "WORK_DIR", tmp_path)
    monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path / "train_output")
    monkeypatch.setattr(mod, "EPOCHS", 2)
    monkeypatch.setattr(mod, "pip_install", lambda *a, **k: None)

    yield mod
    sys.modules.pop("remote_train_under_test", None)


def _install_fake_rfdetr(monkeypatch, model: _FakeRFDETRModel) -> None:
    fake_pkg = types.ModuleType("rfdetr")
    fake_pkg.RFDETRBase = lambda: model
    monkeypatch.setitem(sys.modules, "rfdetr", fake_pkg)


class TestEpochCallbackAccumulatesMetrics:
    def test_epoch_2_callback_still_includes_epoch_1_only_key(
        self, remote_train_mod, monkeypatch,
    ) -> None:
        """epoch 1 loga só loss; epoch 2 loga só map50 (padrão comum:
        mAP calculado a cada N épocas). O callback de epoch 2 deve conter
        AMBAS as chaves (acumulado), não só map50."""
        model = _FakeRFDETRModel()
        model.epoch_logs = [
            {"epoch": 1, "loss": 1.5},
            {"epoch": 2, "map50": 0.42},
        ]
        _install_fake_rfdetr(monkeypatch, model)

        captured: list[dict] = []
        monkeypatch.setattr(remote_train_mod, "post_callback", captured.append)

        try:
            remote_train_mod.train_rfdetr(Path("/tmp/ds"))  # noqa: S108
        except RuntimeError:
            pass  # export/onnx não roda no fake — irrelevante para este teste

        assert len(captured) == 2
        epoch1_payload, epoch2_payload = captured
        assert epoch1_payload["metrics"] == {"loss": 1.5}
        # A CORREÇÃO: epoch 2 preserva loss de epoch 1 (acumulado)
        assert epoch2_payload["metrics"] == {"loss": 1.5, "map50": 0.42}

    def test_single_epoch_metrics_key_unaffected(
        self, remote_train_mod, monkeypatch,
    ) -> None:
        model = _FakeRFDETRModel()
        model.epoch_logs = [{"epoch": 1, "map50": 0.5, "loss": 0.9}]
        _install_fake_rfdetr(monkeypatch, model)

        captured: list[dict] = []
        monkeypatch.setattr(remote_train_mod, "post_callback", captured.append)

        try:
            remote_train_mod.train_rfdetr(Path("/tmp/ds"))  # noqa: S108
        except RuntimeError:
            pass

        assert len(captured) == 1
        assert captured[0]["metrics"] == {"map50": 0.5, "loss": 0.9}


class TestEpocaEhContagemNossa:
    """Issue #420 — `log["epoch"]` do RF-DETR não é o número da época.

    No job `f31f5381` ele subiu a 49, VOLTOU a 32, depois a 13, e o job fechou
    com `current_epoch = 50` contra `total_epochs = 12`. Comportamento de
    contador de passo. O hook `on_fit_epoch_end` é chamado uma vez por época —
    contar as chamadas é a única fonte que não mente.
    """

    def _rodar(self, remote_train_mod, monkeypatch, logs):
        model = _FakeRFDETRModel()
        model.epoch_logs = logs
        _install_fake_rfdetr(monkeypatch, model)
        captured: list[dict] = []
        monkeypatch.setattr(remote_train_mod, "post_callback", captured.append)
        try:
            remote_train_mod.train_rfdetr(Path("/tmp/ds"))  # noqa: S108
        except RuntimeError:
            pass
        return captured

    def test_epoch_do_framework_nao_manda(self, remote_train_mod, monkeypatch) -> None:
        """O caso real: o número do framework sobe e DESCE. O nosso não."""
        captured = self._rodar(
            remote_train_mod, monkeypatch,
            [{"epoch": 49, "loss": 1.0}, {"epoch": 32, "loss": 0.9}, {"epoch": 13, "loss": 0.8}],
        )
        assert [c["epoch"] for c in captured] == [1, 2, 3]

    def test_numero_do_framework_vai_para_metrica_com_nome_honesto(
        self, remote_train_mod, monkeypatch,
    ) -> None:
        """⛔ Não é descartado — só deixa de se passar por época."""
        captured = self._rodar(remote_train_mod, monkeypatch, [{"epoch": 49, "loss": 1.0}])
        assert captured[0]["metrics"]["epoch_bruto_do_framework"] == 49

    def test_framework_coerente_nao_polui_metrica(
        self, remote_train_mod, monkeypatch,
    ) -> None:
        captured = self._rodar(
            remote_train_mod, monkeypatch, [{"epoch": 1, "loss": 1.0}, {"epoch": 2, "loss": 0.9}],
        )
        assert [c["epoch"] for c in captured] == [1, 2]
        assert all("epoch_bruto_do_framework" not in c["metrics"] for c in captured)

    def test_log_sem_epoch_continua_contando(self, remote_train_mod, monkeypatch) -> None:
        captured = self._rodar(remote_train_mod, monkeypatch, [{"loss": 1.0}, {"loss": 0.9}])
        assert [c["epoch"] for c in captured] == [1, 2]


class TestCheckpointBest:
    """Escolher o .pth errado agora é publicar o ONNX errado (#511).

    Enquanto o checkpoint só decidia qual arquivo de PESOS subir, o fallback
    lexical era feio. Agora ele decide de qual estado sai o ONNX SERVIDO.
    """

    def _semear(self, mod, *nomes: str) -> None:
        mod.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for nome in nomes:
            (mod.OUTPUT_DIR / nome).write_bytes(b"x")

    def test_prefere_best_total_sobre_ema_e_sobre_epoca(self, remote_train_mod) -> None:
        self._semear(
            remote_train_mod, "checkpoint_9.pth", "checkpoint_40.pth",
            "checkpoint_best_ema.pth", "checkpoint_best_total.pth",
        )
        assert remote_train_mod._checkpoint_best().name == "checkpoint_best_total.pth"

    def test_cai_para_best_ema_quando_nao_ha_total(self, remote_train_mod) -> None:
        self._semear(remote_train_mod, "checkpoint_40.pth", "checkpoint_best_ema.pth")
        assert remote_train_mod._checkpoint_best().name == "checkpoint_best_ema.pth"

    def test_sem_best_falha_em_vez_de_chutar_uma_epoca(self, remote_train_mod) -> None:
        """⛔ A ordem LEXICAL do fallback antigo elegia checkpoint_9 sobre
        checkpoint_40 — a época 9 viraria o modelo servido. Melhor morrer."""
        self._semear(remote_train_mod, "checkpoint_9.pth", "checkpoint_40.pth")
        with pytest.raises(RuntimeError, match="checkpoint_best_total"):
            remote_train_mod._checkpoint_best()


class TestEpocasRodadasNaoSaoAsPedidas:
    """5º caminho de mentira: com early-stop ligado, EPOCHS é o ORÇAMENTO
    pedido, não o que rodou. O callback final postava EPOCHS fixo — um treino
    que parou na época 2 de 50 seria registrado como 50 épocas."""

    def _treinar_2_de_50(self, mod, monkeypatch) -> dict:
        model = _FakeRFDETRModel()
        model.epoch_logs = [{"loss": 1.0}, {"loss": 0.9}]
        _install_fake_rfdetr(monkeypatch, model)
        monkeypatch.setattr(mod, "EPOCHS", 50)
        monkeypatch.setattr(mod, "post_callback", lambda _p: None)
        # best existe → _checkpoint_best passa; o export real precisa de
        # torch+rfdetr (roda no pod, não aqui).
        mod.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (mod.OUTPUT_DIR / "checkpoint_best_total.pth").write_bytes(b"x")
        monkeypatch.setattr(
            mod, "_exportar_best_onnx",
            lambda w, r: mod.OUTPUT_DIR / "inference_model.onnx",
        )
        _onnx, _w, metrics = mod.train_rfdetr(Path("/tmp/ds"))  # noqa: S108
        return metrics

    def test_metrics_registra_as_epocas_realmente_rodadas(
        self, remote_train_mod, monkeypatch,
    ) -> None:
        metrics = self._treinar_2_de_50(remote_train_mod, monkeypatch)
        assert metrics["epochs_ran"] == 2.0

    def test_callback_final_reporta_2_e_nao_as_50_pedidas(
        self, remote_train_mod, monkeypatch,
    ) -> None:
        """A CORREÇÃO, pela porta de entrada real (main)."""
        metrics = self._treinar_2_de_50(remote_train_mod, monkeypatch)
        captured: list[dict] = []
        monkeypatch.setattr(remote_train_mod, "post_callback", captured.append)
        monkeypatch.setattr(remote_train_mod, "prepare_dataset", lambda: Path("/tmp/ds"))  # noqa: S108
        monkeypatch.setattr(
            remote_train_mod, "train_rfdetr",
            lambda _d: (remote_train_mod.OUTPUT_DIR / "m.onnx", None, metrics),
        )
        monkeypatch.setattr(remote_train_mod, "validate_onnx", lambda _p: None)

        assert remote_train_mod.main() == 0
        final = captured[-1]
        assert final["status"] == "completed"
        assert final["epoch"] == 2, "reportou o orçamento pedido, não o que rodou"
