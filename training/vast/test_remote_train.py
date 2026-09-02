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
        self.train_kwargs: dict = {}

    def train(self, **_kwargs) -> None:
        self.train_kwargs = dict(_kwargs)
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


class TestCapDeBatch:
    """O cap existe para não estourar a memória, não para ir rápido.

    Errar para cima custa a corrida inteira num OOM na primeira época; errar
    para baixo custa tempo. Por isso todo caminho de dúvida cai em 4.
    """

    def _fake_torch(self, gib):
        """torch mínimo cuja GPU relata `gib` de memória."""
        props = types.SimpleNamespace(total_memory=int(gib * (1024 ** 3)))
        mod = types.ModuleType("torch")
        mod.cuda = types.SimpleNamespace(get_device_properties=lambda _: props)
        return mod

    def test_placa_de_48g_libera_batch_16(self, remote_train_mod, monkeypatch) -> None:
        monkeypatch.setitem(sys.modules, "torch", self._fake_torch(47.4))
        assert remote_train_mod._cap_de_batch() == 16

    def test_batch_fixo_nao_se_adapta_a_placa_grande(
        self, remote_train_mod, monkeypatch,
    ) -> None:
        """O caso real de 02/09: pedimos 4090 (24G) nos dois braços do A/B e a
        RunPod entregou A6000 (47,4G) no segundo. Sem BATCH_FIXO, um braço rodou
        16×1 e o outro 4×4 — caminhos de normalização diferentes dentro do que
        deveria ser o mesmo experimento."""
        monkeypatch.setitem(sys.modules, "torch", self._fake_torch(47.4))
        monkeypatch.setattr(remote_train_mod, "BATCH_FIXO", True)
        monkeypatch.setattr(remote_train_mod, "BATCH", 4)
        assert remote_train_mod._cap_de_batch() == 4

    def test_batch_fixo_aborta_quando_a_placa_nao_comporta(
        self, remote_train_mod, monkeypatch,
    ) -> None:
        """Num experimento, morrer alto é melhor que divergir calado."""
        monkeypatch.setitem(sys.modules, "torch", self._fake_torch(23.7))
        monkeypatch.setattr(remote_train_mod, "BATCH_FIXO", True)
        monkeypatch.setattr(remote_train_mod, "BATCH", 16)
        with pytest.raises(RuntimeError, match="não cabe nesta placa"):
            remote_train_mod._cap_de_batch()

    def test_placa_de_24g_mantem_o_cap_antigo(self, remote_train_mod, monkeypatch) -> None:
        """A 3090 que causou o OOM real (job 90946c17) não pode ser liberada."""
        monkeypatch.setitem(sys.modules, "torch", self._fake_torch(23.7))
        assert remote_train_mod._cap_de_batch() == 4

    def test_sem_torch_cai_no_conservador(self, remote_train_mod, monkeypatch) -> None:
        quebrado = types.ModuleType("torch")
        quebrado.cuda = types.SimpleNamespace(
            get_device_properties=lambda _: (_ for _ in ()).throw(RuntimeError("no CUDA"))
        )
        monkeypatch.setitem(sys.modules, "torch", quebrado)
        assert remote_train_mod._cap_de_batch() == 4

    def test_batch_efetivo_16_nos_dois_caminhos(self, remote_train_mod, monkeypatch) -> None:
        """batch × grad_accum tem de dar 16 com ou sem a placa grande —
        senão a troca de GPU muda a matemática do treino, não só a velocidade."""
        for gib, esperado in ((47.4, 16), (23.7, 4)):
            model = _FakeRFDETRModel()
            model.epoch_logs = [{"epoch": 1, "loss": 1.0}]
            _install_fake_rfdetr(monkeypatch, model)
            monkeypatch.setitem(sys.modules, "torch", self._fake_torch(gib))
            monkeypatch.setattr(remote_train_mod, "BATCH", 16)
            monkeypatch.setattr(remote_train_mod, "post_callback", lambda *_: None)
            try:
                remote_train_mod.train_rfdetr(Path("/tmp/ds"))  # noqa: S108
            except RuntimeError:
                pass
            kw = model.train_kwargs
            assert kw["batch_size"] == esperado
            assert kw["batch_size"] * kw["grad_accum_steps"] == 16


class TestEarlyStoppingPatience:
    """A paciência do early-stop é o que decide quando o treino para.

    Com `lr_drop=15` no mesmo `model.train(...)`, o LR só cai de 10× na época
    15 — e a validação costuma dar um segundo salto DEPOIS disso. Uma
    paciência menor que o próprio lr_drop mata o run antes de ele ver o efeito
    do decay que este arquivo configura. Era 8, hardcoded.
    """

    def test_patience_vem_do_modulo_e_nao_e_menor_que_o_lr_drop(
        self, remote_train_mod, monkeypatch,
    ) -> None:
        model = _FakeRFDETRModel()
        model.epoch_logs = [{"epoch": 1, "loss": 1.0}]
        _install_fake_rfdetr(monkeypatch, model)
        monkeypatch.setattr(remote_train_mod, "post_callback", lambda *_: None)
        monkeypatch.setattr(remote_train_mod, "PATIENCE", 15)

        try:
            remote_train_mod.train_rfdetr(Path("/tmp/ds"))  # noqa: S108
        except RuntimeError:
            pass  # export/onnx não roda no fake — irrelevante aqui

        kwargs = model.train_kwargs
        assert kwargs["early_stopping"] is True
        # Reprova se alguém voltar a chumbar o número na chamada.
        assert kwargs["early_stopping_patience"] == 15
        assert kwargs["early_stopping_patience"] >= kwargs["lr_drop"], (
            "paciência menor que lr_drop: o run morre antes de ver o decay"
        )

    def test_patience_default_do_modulo_e_15(self, remote_train_mod) -> None:
        """Sem env, o default precisa ser o valor da regra — não o antigo 8."""
        assert remote_train_mod.PATIENCE == 15


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


class TestFineTuneDoNossoCheckpoint:
    """v10 = fine-tune a partir do weights.pth do v9 (INIT_WEIGHTS_URL).

    Três coisas que mentiriam em silêncio se quebrassem: (1) sem a env o
    caminho padrão `RFDETRBase()` tem de ficar EXATAMENTE como era; (2) com a
    env, o construtor recebe pretrain_weights+resolution+num_classes do
    checkpoint (sem num_classes explícito o loader do rfdetr reinicializa a
    cabeça e o "fine-tune" vira pretrain); (3) taxonomia diferente entre o
    checkpoint e o dataset é recusada ANTES de gastar GPU — o rfdetr 1.5.2
    fatia a cabeça por índice sem reclamar.
    """

    class _Bias:
        def __init__(self, n: int) -> None:
            self.shape = (n,)

    def _fake_rfdetr(self, monkeypatch, classes_ds: list[str], registro: dict) -> None:
        class FakeBase:
            def __init__(self, **kw) -> None:
                registro["kwargs"] = kw
                self.callbacks = {"on_fit_epoch_end": []}

            def train(self, **_kw) -> None:
                registro["trained"] = True

            @staticmethod
            def _load_classes(d: str) -> list[str]:
                registro["load_classes_dir"] = d
                return list(classes_ds)

        pkg = types.ModuleType("rfdetr")
        pkg.RFDETRBase = FakeBase
        monkeypatch.setitem(sys.modules, "rfdetr", pkg)

    def _treinar(self, mod, monkeypatch):
        monkeypatch.setattr(mod, "post_callback", lambda _p: None)
        mod.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (mod.OUTPUT_DIR / "checkpoint_best_total.pth").write_bytes(b"x")
        monkeypatch.setattr(mod, "_exportar_best_onnx", lambda w, r: mod.OUTPUT_DIR / "m.onnx")
        return mod.train_rfdetr(Path("/tmp/ds"))  # noqa: S108

    def _ckpt(self, nomes, head: int, resolution: int | None = None):
        from types import SimpleNamespace  # noqa: PLC0415

        args = {} if nomes is None else {"class_names": nomes}
        if resolution is not None:
            args["resolution"] = resolution
        ck = {"args": SimpleNamespace(**args)} if args else {}
        return lambda _p: (ck, self._Bias(head))

    def test_sem_init_weights_caminho_padrao_intacto(self, remote_train_mod, monkeypatch) -> None:
        reg: dict = {}
        self._fake_rfdetr(monkeypatch, ["a", "b"], reg)
        monkeypatch.setattr(remote_train_mod, "INIT_WEIGHTS_URL", "")
        monkeypatch.setattr(
            remote_train_mod, "download",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("download não deveria rodar")),
        )
        self._treinar(remote_train_mod, monkeypatch)
        assert reg["kwargs"] == {}
        assert reg["trained"] is True

    def test_com_init_weights_baixa_e_constroi_do_checkpoint(
        self, remote_train_mod, monkeypatch,
    ) -> None:
        reg: dict = {}
        dl: dict = {}
        self._fake_rfdetr(monkeypatch, ["a", "b"], reg)
        monkeypatch.setattr(remote_train_mod, "INIT_WEIGHTS_URL", "https://r2/w.pth?sig=1")
        monkeypatch.setattr(remote_train_mod, "IMGSZ", 560)

        def fake_download(url, dest, *, expect_zip=False):
            dl.update(url=url, dest=dest, expect_zip=expect_zip)
            dest.write_bytes(b"PK")

        monkeypatch.setattr(remote_train_mod, "download", fake_download)
        monkeypatch.setattr(remote_train_mod, "_carregar_checkpoint", self._ckpt(["a", "b"], 3))
        self._treinar(remote_train_mod, monkeypatch)

        # torch.save é zip — o magic "PK" pega o XML de 404 do R2 de graça
        assert dl["expect_zip"] is True
        assert dl["dest"] == remote_train_mod.WORK_DIR / "init.pth"
        assert dl["url"] == "https://r2/w.pth?sig=1"
        # num_classes = head-1 EXPLÍCITO — senão o loader reinicializa a cabeça
        assert reg["kwargs"] == {
            "pretrain_weights": str(remote_train_mod.WORK_DIR / "init.pth"),
            "resolution": 560,
            "num_classes": 2,
        }
        assert reg["load_classes_dir"] == "/tmp/ds"  # noqa: S108
        assert reg["trained"] is True

    def test_taxonomia_diferente_recusa_antes_de_treinar(
        self, remote_train_mod, monkeypatch,
    ) -> None:
        """⛔ Mesma contagem, nome diferente: o rfdetr treinaria com a cabeça
        do v9 apontando para a classe errada, em silêncio."""
        reg: dict = {}
        self._fake_rfdetr(monkeypatch, ["a", "c"], reg)
        monkeypatch.setattr(remote_train_mod, "INIT_WEIGHTS_URL", "https://r2/w.pth?sig=1")
        monkeypatch.setattr(remote_train_mod, "download", lambda u, d, **k: d.write_bytes(b"PK"))
        monkeypatch.setattr(remote_train_mod, "_carregar_checkpoint", self._ckpt(["a", "b"], 3))
        with pytest.raises(RuntimeError, match="fine-tune recusado"):
            self._treinar(remote_train_mod, monkeypatch)
        assert "trained" not in reg

    def test_checkpoint_sem_nomes_confere_pela_contagem(
        self, remote_train_mod, monkeypatch,
    ) -> None:
        reg: dict = {}
        self._fake_rfdetr(monkeypatch, ["a", "b", "c"], reg)
        monkeypatch.setattr(remote_train_mod, "INIT_WEIGHTS_URL", "https://r2/w.pth?sig=1")
        monkeypatch.setattr(remote_train_mod, "download", lambda u, d, **k: d.write_bytes(b"PK"))
        monkeypatch.setattr(remote_train_mod, "_carregar_checkpoint", self._ckpt(None, 3))
        with pytest.raises(RuntimeError, match="fine-tune recusado"):
            self._treinar(remote_train_mod, monkeypatch)
        assert "trained" not in reg

    def test_resolucao_diferente_do_checkpoint_recusa(
        self, remote_train_mod, monkeypatch,
    ) -> None:
        """⛔ Checkpoint @560 (v9) com IMGSZ default do dispatch (640 → 616):
        PE treinado numa resolução, fine-tune noutra — confound silencioso."""
        reg: dict = {}
        self._fake_rfdetr(monkeypatch, ["a", "b"], reg)
        monkeypatch.setattr(remote_train_mod, "INIT_WEIGHTS_URL", "https://r2/w.pth?sig=1")
        monkeypatch.setattr(remote_train_mod, "IMGSZ", 640)
        monkeypatch.setattr(remote_train_mod, "download", lambda u, d, **k: d.write_bytes(b"PK"))
        monkeypatch.setattr(
            remote_train_mod, "_carregar_checkpoint", self._ckpt(["a", "b"], 3, resolution=560),
        )
        with pytest.raises(RuntimeError, match=r"checkpoint @560, IMGSZ pede 616.*imgsz=560"):
            self._treinar(remote_train_mod, monkeypatch)
        assert "kwargs" not in reg and "trained" not in reg

    def test_resolucao_igual_ao_checkpoint_passa(
        self, remote_train_mod, monkeypatch,
    ) -> None:
        reg: dict = {}
        self._fake_rfdetr(monkeypatch, ["a", "b"], reg)
        monkeypatch.setattr(remote_train_mod, "INIT_WEIGHTS_URL", "https://r2/w.pth?sig=1")
        monkeypatch.setattr(remote_train_mod, "IMGSZ", 560)
        monkeypatch.setattr(remote_train_mod, "download", lambda u, d, **k: d.write_bytes(b"PK"))
        monkeypatch.setattr(
            remote_train_mod, "_carregar_checkpoint", self._ckpt(["a", "b"], 3, resolution=560),
        )
        self._treinar(remote_train_mod, monkeypatch)
        assert reg["kwargs"]["resolution"] == 560
        assert reg["trained"] is True

    def test_carregar_checkpoint_sem_bias_falha(self, remote_train_mod, monkeypatch, tmp_path) -> None:
        fake_torch = types.ModuleType("torch")
        fake_torch.load = lambda *a, **k: {"model": {"x": 1}}
        monkeypatch.setitem(sys.modules, "torch", fake_torch)
        with pytest.raises(RuntimeError, match="class_embed.bias"):
            remote_train_mod._carregar_checkpoint(tmp_path / "w.pth")


class TestHardwareDaCorrida:
    """A placa que a RunPod entregou tem de chegar ao job.

    Motivo (medido em 02/09): pedimos 4090 nos dois braços de um A/B e veio uma
    A6000 no segundo, sem erro. `get_pod` devolve `gpuTypeIds: null`, então sem
    esta leitura de dentro do pod nada registra em que hardware o modelo rodou.
    """

    def _torch_de(self, monkeypatch, *, total_bytes: int, nome: str) -> None:
        props = types.SimpleNamespace(total_memory=total_bytes, name=nome)
        fake = types.ModuleType("torch")
        fake.cuda = types.SimpleNamespace(get_device_properties=lambda _i: props)
        monkeypatch.setitem(sys.modules, "torch", fake)

    def test_reporta_vram_e_nome(self, remote_train_mod, monkeypatch) -> None:
        self._torch_de(monkeypatch, total_bytes=int(47.4 * 1024**3), nome="NVIDIA RTX A6000")
        d = remote_train_mod._hardware_da_corrida()
        assert d["vram_gib"] == 47.4
        assert d["gpu"] == "NVIDIA RTX A6000"

    def test_gpu_ilegivel_nao_derruba(self, remote_train_mod, monkeypatch) -> None:
        """Proveniência é sensor, não guarda: falhar a leitura não mata o treino."""
        quebrado = types.ModuleType("torch")
        quebrado.cuda = types.SimpleNamespace(
            get_device_properties=lambda _i: (_ for _ in ()).throw(RuntimeError("sem cuda"))
        )
        monkeypatch.setitem(sys.modules, "torch", quebrado)
        d = remote_train_mod._hardware_da_corrida()
        assert d["vram_gib"] is None and d["gpu"] is None

    def test_vai_dentro_de_metrics_no_primeiro_callback(
        self, remote_train_mod, monkeypatch,
    ) -> None:
        """`_validate_callback_payload` remonta o payload com chaves FIXAS —
        um `hardware` IRMÃO de `metrics` seria descartado em silêncio."""
        self._torch_de(monkeypatch, total_bytes=24 * 1024**3, nome="NVIDIA GeForce RTX 4090")
        enviados: list = []
        monkeypatch.setattr(remote_train_mod, "post_callback", enviados.append)
        monkeypatch.setattr(
            remote_train_mod, "prepare_dataset",
            lambda: (_ for _ in ()).throw(RuntimeError("para aqui")),
        )
        with pytest.raises(RuntimeError, match="para aqui"):
            remote_train_mod.main()
        primeiro = enviados[0]
        assert "hardware" not in primeiro, "hardware fora de metrics é descartado pelo backend"
        assert primeiro["metrics"]["hardware"]["gpu"] == "NVIDIA GeForce RTX 4090"


class TestMetricasDoLog:
    """O modelo tem de nascer sabendo quanto vale.

    O RF-DETR 1.5.2 não põe mAP no dict de `on_fit_epoch_end` — ele IMPRIME. Por
    isso `trained_models` sempre gravou map50=0/precision=0/recall=0, em TODO
    modelo do sistema, e o ranking campeão×desafiante comparava zeros. As linhas
    abaixo são cópias LITERAIS do pod.log do job 04508616 (US$ 1,71 pagos).
    """

    LOG_REAL = (
        "2026-09-02 17:20:51,022 INFO rf-detr -  Average Precision  (AP) @[ IoU=0.50:0.95 "
        "| area=   all | maxDets=500 ] = 0.401\n"
        "2026-09-02 17:20:51,023 INFO rf-detr -  Average Precision  (AP) @[ IoU=0.50      "
        "| area=   all | maxDets=500 ] = 0.562\n"
        "2026-09-02 17:20:51,024 INFO rf-detr -  Average Precision  (AP) @[ IoU=0.50:0.95 "
        "| area= small | maxDets=500 ] = 0.300\n"
        "2026-09-02 17:20:52,001 INFO rf-detr - Early stopping: Current mAP (EMA): 0.4301, "
        "Best: 0.4386, Diff: 0.0085, Min delta: 0.001\n"
    )

    def test_extrai_do_log_real(self, remote_train_mod, monkeypatch) -> None:
        monkeypatch.setattr(remote_train_mod, "_LOG_BUFFER", [self.LOG_REAL])
        m = remote_train_mod._metricas_do_log()
        assert m["map"] == 0.401       # AP@[.5:.95], area=all — NÃO o de area=small
        assert m["map50"] == 0.562     # AP@0.50 — o que alimenta trained_models.map50
        assert m["map_ema"] == 0.4301
        # `Best` é o número que elege o checkpoint_best_total, que vira o ONNX
        # servido: a métrica gravada é a DO ARTEFATO ENTREGUE, não a da última época.
        assert m["map_ema_best"] == 0.4386

    def test_ignora_area_small_e_medium(self, remote_train_mod, monkeypatch) -> None:
        """`area=all` é a métrica do modelo; small/medium/large são recortes.
        Casar o padrão errado gravaria 0,300 como se fosse o mAP."""
        monkeypatch.setattr(remote_train_mod, "_LOG_BUFFER", [self.LOG_REAL])
        assert remote_train_mod._metricas_do_log()["map"] != 0.300

    def test_log_sem_metrica_nao_inventa(self, remote_train_mod, monkeypatch) -> None:
        monkeypatch.setattr(remote_train_mod, "_LOG_BUFFER", ["pip install rfdetr\n"])
        assert remote_train_mod._metricas_do_log() == {}


class TestPinsQueJaMataramPod:
    """Cada pin aqui nasceu de um pod pago que morreu. Remover um é reabrir a
    cova — este teste existe para que a remoção seja deliberada, não distraída.

    numpy<2 ....... job b4d69cde, época 0, 02/09 18h38: ImportError '_center'
                    (numpy misto 1.x/2.x via rfdetr→supervision→scipy). O job
                    04508616, MESMO código e imagem, rodara 3h antes.
    transformers<5  jobs 9504a3a2 / pods m0amcgnl4: rfdetr importa
                    BackboneConfigMixin, API removida na série 5.x.
    rfdetr==1.5.2 . versão provada; >=1.9 exige transformers>=5.1 e o pip morre
                    em ResolutionImpossible antes da época 0.
    """

    def test_train_rfdetr_pina_o_que_precisa(self, remote_train_mod, monkeypatch) -> None:
        pedidos: list = []
        monkeypatch.setattr(remote_train_mod, "pip_install", lambda *p: pedidos.extend(p))
        monkeypatch.setattr(
            remote_train_mod, "_cap_de_batch",
            lambda: (_ for _ in ()).throw(RuntimeError("parar depois do pip")),
        )
        with pytest.raises(Exception):
            remote_train_mod.train_rfdetr(Path("/tmp/ds"))
        assert "numpy<2" in pedidos, "sem o pin o pod morre na época 0 (job b4d69cde)"
        assert "transformers<5" in pedidos
        assert "rfdetr==1.5.2" in pedidos

    def test_versoes_resolvidas_nao_explode_sem_o_pacote(
        self, remote_train_mod, caplog,
    ) -> None:
        """Roda no venv local, onde rfdetr/supervision não existem: a função tem
        de registrar o que achar e ignorar o resto, nunca derrubar o install."""
        remote_train_mod._logar_versoes_resolvidas()


class TestLockDoAmbiente:
    """O ambiente é artefato, não instalação repetida.

    Em 02/09, com os MESMOS pacotes de topo, o pip montou ambientes diferentes
    em horas diferentes do mesmo dia e matou dois pods na época 0. Pin de topo
    não alcança a transitiva; o lock alcança.
    """

    def test_pip_usa_o_lock(self, monkeypatch, tmp_path) -> None:
        # Instância LIMPA de propósito: a fixture `remote_train_mod` substitui
        # `pip_install` por um stub, e um teste do pip_install que roda o stub
        # não testa nada.
        spec = importlib.util.spec_from_file_location("rt_lock", _MODULE_PATH)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["rt_lock"] = mod
        spec.loader.exec_module(mod)
        chamadas: list = []
        monkeypatch.setattr(mod, "_CONSTRAINTS_PATH", tmp_path / "c.txt")
        monkeypatch.setattr(mod, "_logar_versoes_resolvidas", lambda: None)
        monkeypatch.setattr(mod.subprocess, "run", lambda cmd, **k: chamadas.append(cmd))
        mod.pip_install("rfdetr==1.5.2")
        sys.modules.pop("rt_lock", None)
        remote_train_mod = mod
        cmd = chamadas[0]
        assert "-c" in cmd, "sem -c o lock não é aplicado e a transitiva volta a flutuar"
        assert cmd[cmd.index("-c") + 1] == str(tmp_path / "c.txt")
        assert (tmp_path / "c.txt").read_text() == remote_train_mod._CONSTRAINTS

    def test_lock_travou_o_que_ja_quebrou(self, remote_train_mod) -> None:
        lock = remote_train_mod._CONSTRAINTS
        assert "numpy==1.26.4" in lock          # matou o pod b4d69cde
        assert "typing_extensions==4.16.0" in lock  # matou 40e61279 e b5569408
        assert "pydantic-core==2.46.5" in lock  # quem importava Sentinel

    def test_torch_fora_do_lock(self, remote_train_mod) -> None:
        """A imagem traz 2.4.1+cu124, build que não existe no PyPI: pinar faria
        o pip tentar buscar e falhar."""
        assert "torch==" not in remote_train_mod._CONSTRAINTS
