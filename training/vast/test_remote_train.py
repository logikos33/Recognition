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
