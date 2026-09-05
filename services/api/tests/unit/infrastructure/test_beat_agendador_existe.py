"""O agendamento EXISTE — não só está escrito.

═══ O QUE ESTAVA ERRADO (medido, não relatado) ═══

05/09/2026, `GET /health/backup` no DEV:

    HTTP 503
    {"idade_horas": 270.8, "mais_novo": "2026-08-25T11:21:36+00:00", "total": 1}

Onze dias sem backup, um único arquivo. A rota existe justamente para denunciar
isso (tasks/backup.py). O que ela não conseguia dizer é POR QUÊ.

`railway status --json`, nos dois ambientes:

    Desenvolvimento: Redis, landing-page, API-V3, Postgres, celery-worker, Frontend
    production:      Redis, landing-page, API-V3, Postgres, celery-worker, Frontend

Não há serviço `SERVICE_TYPE=beat`. Nunca houve. O SAFE_BEAT_SCHEDULE inteiro
— backup, compliance, CEP, drift, reconciliação de pods RunPod — estava
agendado para um scheduler que não existe.

Estes testes fixam as duas metades do conserto:
  1. o worker (que EXISTE nos dois ambientes, em réplica única) sobe com `-B`;
  2. o backup usa hora de parede, não intervalo — porque o estado do beat mora
     em /tmp e nasce zerado a cada deploy, e o DEV redeploya a cada merge.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest
from celery.schedules import crontab

_RAIZ = pathlib.Path(__file__).resolve().parents[5]

# Import REAL do celery_app mesmo que outro teste tenha deixado um stub
# transparente em sys.modules (mesmo padrão de test_beat_schedule.py).
_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_carregado = sys.modules.get(_CELERY_APP_KEY)
if _carregado is not None and getattr(_carregado, "__file__", None) is None:
    sys.modules.pop(_CELERY_APP_KEY, None)

from app.infrastructure.queue import celery_app  # noqa: E402


@pytest.fixture(scope="module")
def railway_start():
    spec = importlib.util.spec_from_file_location(
        "railway_start_sob_teste_beat", _RAIZ / "railway_start.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestWorkerAgendaDeFato:
    """Sem um `-B` (ou um serviço beat), o schedule é um comentário."""

    def test_worker_sobe_com_beat_embutido_por_padrao(self, railway_start, monkeypatch):
        monkeypatch.delenv("CELERY_BEAT_EMBEDDED", raising=False)
        argv = railway_start.argv_do_worker()
        assert "-B" in argv, (
            "worker sem -B e sem serviço beat = NINGUÉM agenda. "
            "Foi exatamente este estado que deixou o DEV 11 dias sem backup."
        )

    def test_estado_do_beat_fora_do_diretorio_da_app(self, railway_start, monkeypatch):
        monkeypatch.delenv("CELERY_BEAT_EMBEDDED", raising=False)
        argv = railway_start.argv_do_worker()
        assert f"--schedule={railway_start.ARQUIVO_SCHEDULE_BEAT}" in argv
        assert railway_start.ARQUIVO_SCHEDULE_BEAT.startswith("/tmp/")

    @pytest.mark.parametrize("valor", ["0", "false", "no", "off", "OFF"])
    def test_variavel_desliga_para_o_dia_do_servico_beat_dedicado(
        self, railway_start, monkeypatch, valor
    ):
        """Escape hatch: dois schedulers dobrariam disparo. Um serviço beat
        dedicado desliga o embutido por variável, sem deploy de código."""
        monkeypatch.setenv("CELERY_BEAT_EMBEDDED", valor)
        assert "-B" not in railway_start.argv_do_worker()

    def test_worker_continua_consumindo_as_mesmas_filas(self, railway_start):
        """`-B` não pode ter mexido no consumo — regressão do que já funcionava."""
        argv = railway_start.argv_do_worker()
        assert f"--queues={railway_start.FILAS_DO_WORKER}" in argv
        assert "--concurrency=2" in argv


class TestBackupNaoDependeDoUptime:
    """Intervalo + estado efêmero + deploy frequente = nunca vence."""

    def _entrada(self) -> dict:
        return celery_app.celery.conf.beat_schedule["backup-postgres"]

    def test_backup_agendado_por_hora_de_parede_e_nao_por_intervalo(self):
        agenda = self._entrada()["schedule"]
        assert isinstance(agenda, crontab), (
            "com intervalo, o beat conta a partir do último boot; o estado vive "
            "em /tmp e zera a cada deploy, e o DEV deploya a cada merge — a "
            "entrada de 12h nunca venceria num dia de trabalho."
        )

    def test_backup_duas_vezes_por_dia(self):
        agenda = self._entrada()["schedule"]
        assert agenda.hour == {3, 15}, "00:00 e 12:00 em Brasília (UTC-3)"
        assert agenda.minute == {0}

    def test_backup_vai_para_fila_que_o_worker_consome(self, railway_start):
        """A regra da casa: entrada ativa só com worker na fila."""
        fila = self._entrada()["options"]["queue"]
        assert fila in railway_start.FILAS_DO_WORKER.split(",")


class TestTodoAgendamentoAtivoTemConsumidor:
    """Cross-check entre os dois arquivos — o que pegou a fila `maintenance`.

    Antes deste teste a regra existia só em prosa: test_beat_schedule.py
    conferia o nome da fila entrada a entrada, contra uma lista digitada à mão.
    Aqui ela é conferida contra a string que o worker REALMENTE passa ao
    Celery, no outro arquivo.
    """

    def test_nenhuma_entrada_ativa_cai_em_fila_sem_consumidor(self, railway_start):
        consumidas = set(railway_start.FILAS_DO_WORKER.split(","))
        orfas = {
            nome: entrada["options"]["queue"]
            for nome, entrada in celery_app.SAFE_BEAT_SCHEDULE.items()
            if entrada["options"]["queue"] not in consumidas
        }
        assert not orfas, f"agendadas para fila que ninguém lê: {orfas}"
