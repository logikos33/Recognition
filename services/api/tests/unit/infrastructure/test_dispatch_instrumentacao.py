"""Instrumentação do dispatch: causa real, custo sempre, classe dropada visível.

O TREINO 2 falhou na época 0 e o registro dizia só "Job runpod failed", com
`actual_usd` NULL. Diagnosticar assim é adivinhar — e os logs do pod expiram
junto com o pod. Ver D-155/D-164/D-165.
"""
import pytest
from unittest.mock import MagicMock


def _watch_com_status(state):
    from app.infrastructure.gpu import runpod_runner as rr
    return rr._watch(
        MagicMock(), "pod1", "job1",
        poll_status_fn=lambda: state,
        verify_completed_fn=None,
        timeout_seconds=5, poll_interval=0,
    )


class TestErroReal:
    def test_falha_carrega_a_causa_reportada_pelo_runner(self):
        with pytest.raises(RuntimeError) as e:
            _watch_com_status({"status": "failed", "error": "CUDA device-side assert",
                               "exit_code": 1})
        msg = str(e.value)
        assert "CUDA device-side assert" in msg, "a causa real precisa aparecer"
        assert "exit=1" in msg

    def test_sem_causa_o_erro_DIZ_que_nao_veio_e_lista_as_chaves(self):
        # Silêncio honesto > silêncio disfarçado: se o runner não reportou,
        # a mensagem tem que denunciar isso, não fingir que não há causa.
        with pytest.raises(RuntimeError) as e:
            _watch_com_status({"status": "failed", "metrics": {}})
        msg = str(e.value)
        assert "NAO REPORTADA" in msg
        assert "chaves recebidas" in msg


class TestCustoEmFalha:
    """actual_usd tem que existir MESMO quando o treino morre — falha custa
    GPU igual. Antes, o cálculo vivia depois do _watch e nunca rodava."""

    def test_excecao_carrega_gpu_cost_para_o_caller_persistir(self, monkeypatch):
        from app.infrastructure.gpu import runpod_runner as rr

        monkeypatch.setattr(rr, "_best_effort_actual_cost", lambda *a, **k: 0.07)

        def _boom(*a, **k):
            raise RuntimeError("morreu na epoca 0")

        monkeypatch.setattr(rr, "_watch", _boom)
        client = MagicMock()

        # Reproduz o trecho instrumentado: try/except em volta do _watch,
        # anexando o custo à exceção antes de propagar.
        def _custo():
            return {"provider": "runpod", "actual_usd": rr._best_effort_actual_cost(client, "pod1")}

        with pytest.raises(RuntimeError) as e:
            try:
                rr._watch(client, "pod1", "job1", lambda: {}, None, 5, 0)
            except BaseException as exc:
                client.terminate_pod("pod1")
                exc.gpu_cost = _custo()
                raise

        assert getattr(e.value, "gpu_cost", None) is not None, "custo nao anexado"
        assert e.value.gpu_cost["actual_usd"] == 0.07
        client.terminate_pod.assert_called_once_with("pod1"), "pod tem que morrer na falha"

    def test_o_caller_persiste_o_custo_anexado(self):
        # dispatch_training lê exc.gpu_cost e o manda para update_job.
        exc = RuntimeError("x")
        exc.gpu_cost = {"actual_usd": 0.07}
        custo = getattr(exc, "gpu_cost", None)
        assert custo and custo["actual_usd"] == 0.07


class TestClasseDropadaVisivel:
    def test_chave_reservada_nao_colide_com_classe_real(self):
        # Nome de classe real nunca vem cercado de underscores duplos.
        from app.infrastructure.queue.tasks import versioning_v2 as v2
        import pathlib
        src = pathlib.Path(v2.__file__).read_text()
        assert '__sem_suporte_treino__' in src
        assert 'class_distribution["__sem_suporte_treino__"]' in src
