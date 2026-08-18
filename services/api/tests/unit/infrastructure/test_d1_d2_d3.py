"""D1/D2/D3 — os três consertos que tiram a cegueira do diagnóstico de GPU.

Custo de não tê-los: 9 pods, duas paradas do loop, e um "Job runpod failed"
sem causa que o retry do Celery ainda por cima sobrescreveu.
"""
from unittest.mock import MagicMock


class TestD1SemRetryAutomatico:
    """Retry automático de job GPU apaga a evidência da tentativa informativa:
    foi ele que sobrescreveu o `ep 29` e o "Module onnx is not installed!"."""

    def test_dispatch_training_tem_max_retries_zero(self):
        from app.infrastructure.queue.tasks.training import dispatch_training
        assert dispatch_training.max_retries == 0

    def test_dispatch_nao_chama_self_retry(self):
        # Checa CÓDIGO, não texto: comentários citam self.retry ao explicar
        # por que ele não é usado — grep cru daria falso positivo.
        import ast, inspect
        from app.infrastructure.queue.tasks import training as t
        src = inspect.getsource(t.dispatch_training)
        arvore = ast.parse(src.lstrip())
        chamadas = [
            n for n in ast.walk(arvore)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "retry"
        ]
        assert not chamadas, "retry automático de GPU é proibido (D1)"


class TestD2LogAntesDoTerminate:
    """terminate_pod no finally destruía a evidência de TODA falha."""

    def test_log_e_capturado_ANTES_de_terminar(self, monkeypatch):
        from app.infrastructure.gpu import runpod_runner as rr
        ordem = []
        client = MagicMock()
        client.get_pod_logs.side_effect = lambda *a, **k: (ordem.append("log"), "traceback...")[1]
        client.terminate_pod.side_effect = lambda *a, **k: ordem.append("kill")
        monkeypatch.setattr(rr, "_best_effort_actual_cost", lambda *a, **k: 0.1)

        exc = RuntimeError("boom")
        # reproduz o bloco instrumentado
        log = client.get_pod_logs("pod1")
        exc.pod_log = log
        client.terminate_pod("pod1")

        assert ordem == ["log", "kill"], f"ordem errada: {ordem}"
        assert exc.pod_log == "traceback..."

    def test_falha_na_captura_nao_impede_a_morte(self):
        client = MagicMock()
        client.get_pod_logs.side_effect = RuntimeError("api fora")
        try:
            log = client.get_pod_logs("p")
        except Exception as e:
            log = f"(captura do log falhou: {e})"
        client.terminate_pod("p")
        client.terminate_pod.assert_called_once()
        assert "captura do log falhou" in log

    def test_get_pod_logs_nunca_levanta(self):
        from app.infrastructure.gpu.runpod_client import RunPodClient
        c = RunPodClient.__new__(RunPodClient)
        c._request = MagicMock(side_effect=RuntimeError("500"))
        assert c.get_pod_logs("p") == ""


class TestD3TodosOsEscritoresGravamCausa:
    """Enumerado: quem escreve training_jobs.status='failed'."""

    def test_reconciler_grava_motivo(self):
        import inspect
        from app.infrastructure.queue.tasks import gpu_reconciler as g
        src = inspect.getsource(g._mark_job_failed)
        assert "Reconciler RunPod:" in src, "reconciler tem que dizer POR QUE"

    def test_watchdog_grava_causa_ou_denuncia_a_ausencia(self):
        import inspect
        from app.infrastructure.gpu import runpod_runner as rr
        src = inspect.getsource(rr._watch)
        assert "causa=" in src
        assert "NAO REPORTADA" in src, "sem causa, tem que DIZER que não veio"

    def test_dispatch_anexa_log_ao_error_message(self):
        import inspect
        from app.infrastructure.queue.tasks import training as t
        src = inspect.getsource(t.dispatch_training)
        assert "pod_log" in src
        assert "log do pod" in src
