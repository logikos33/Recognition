"""
Recognition — Readiness cache (item 2.3 do mutirão — health honesto).

Por que existe um módulo separado (e não tudo dentro de routes.py):
Railway só chama o healthcheck NA PROMOÇÃO do deploy (start de container novo)
— depois disso ninguém mais bate nele de forma automática (não há monitor
contínuo; ver docs/runbooks/SINAIS_DEGRADACAO.md). Isso faz do handler de
/readyz a ÚNICA barreira contra promover um deploy degradado no ar. Duas
consequências de design:

1. O handler HTTP nunca deve tocar dependência diretamente (Redis, DB) — quem
   faz isso é um refresher de fundo (greenlet gevent em produção; thread
   daemon como fallback — ver `ReadinessCache.start_background_refresh`).
   O handler só LÊ o último snapshot cacheado.
2. Se o refresher morre, o cache para de ser atualizado. Sem um relógio,
   `/readyz` continuaria devolvendo o último "ready: true" para sempre — uma
   mentira congelada. Por isso todo snapshot carrega `checked_at`, e o
   handler recusa (503 + stale=true) qualquer leitura com mais de
   STALE_AFTER_SECONDS de idade, mesmo que o conteúdo cacheado diga "tudo
   bem". Fail closed.

Duas categorias de checagem, com políticas diferentes:

- Invariantes de config determinísticos (worker_class, storage_backend):
  reprovam DURO na primeira leitura ruim. Não existe "mais sorte na próxima
  tentativa" — ou o processo subiu com o worker certo/storage durável, ou
  não subiu. Dar benefício da dúvida aqui é exatamente o tipo de fallback
  silencioso que este mutirão está removendo (ver item 2.2).
- Dependências transitórias (DB, Redis): só reprovam depois de
  FAILURE_THRESHOLD falhas consecutivas do refresher — uma piscada de rede
  não pode travar a promoção de um deploy saudável.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SECONDS = 10
STALE_AFTER_SECONDS = 30
FAILURE_THRESHOLD = 3  # falhas consecutivas antes de flipar dependência p/ "down"


@dataclass
class ReadinessState:
    checked_at: float  # time.monotonic() — imune a ajuste de relógio
    ready: bool
    invariants: dict[str, dict[str, object]] = field(default_factory=dict)
    dependencies: dict[str, dict[str, object]] = field(default_factory=dict)
    # Jobs de treino em voo (queued|running). None = não deu para saber —
    # NUNCA 0. Ver ReadinessCache.peek_running_jobs.
    running_jobs: int | None = None


class ReadinessCache:
    """Singleton por processo — dono do último snapshot de /readyz."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: ReadinessState | None = None
        self._fail_counts: dict[str, int] = {"database": 0, "redis": 0}
        self._last_ok: dict[str, bool] = {"database": True, "redis": True}
        self._bg_started = False

    # -- invariantes determinísticos (zero I/O) ------------------------------

    @staticmethod
    def check_worker_class() -> dict[str, object]:
        """gevent ausente com SERVICE_TYPE=api = WebSocket morto (item 2.2).

        Detecção robusta: "gevent" só entra em sys.modules se alguém o
        importou de fato (railway_start.py faz isso antes do gunicorn subir
        com GeventWebSocketWorker). Não depende de introspecção do gunicorn.
        """
        service_type = os.environ.get("SERVICE_TYPE", "api")
        if service_type != "api":
            return {"ok": True, "detail": f"service_type={service_type} (fora do escopo deste invariante)"}
        gevent_active = "gevent" in sys.modules
        return {
            "ok": gevent_active,
            "detail": "gevent ativo (GeventWebSocketWorker)"
            if gevent_active
            else "gevent AUSENTE — worker teria caído em 'sync' (sem WebSocket; ver item 2.2)",
        }

    @staticmethod
    def check_storage_backend() -> dict[str, object]:
        """Storage local sem ALLOW_EPHEMERAL_STORAGE=1 = disco efêmero em prod.

        Checagem de CONFIG (env de plataforma), não round-trip de rede — não
        resolve credencial por tenant (isso é DB, e /readyz não toca DB aqui).
        Mesmo critério de `local_storage.get_storage`: as 3 credenciais R2
        presentes -> backend é r2; senão, seria LocalStorage.
        """
        required = ("R2_ENDPOINT", "R2_KEY", "R2_SECRET")
        r2_configured = all(os.environ.get(name) for name in required)
        allow_ephemeral = os.environ.get("ALLOW_EPHEMERAL_STORAGE") == "1"
        ok = r2_configured or allow_ephemeral
        if r2_configured:
            detail = "r2"
        elif allow_ephemeral:
            detail = "local (ALLOW_EPHEMERAL_STORAGE=1 — aceito explicitamente)"
        else:
            detail = "local SEM ALLOW_EPHEMERAL_STORAGE=1 — disco efêmero em prod"
        return {"ok": ok, "detail": detail}

    # -- dependências transitórias (com backoff) -----------------------------

    def _check_dependency(self, name: str, probe: Callable[[], bool]) -> dict[str, object]:
        try:
            ok_now = bool(probe())
        except Exception as exc:  # defensivo: probe nunca deve derrubar o refresher
            logger.warning("readiness_probe_failed: dep=%s err=%s", name, exc)
            ok_now = False

        if ok_now:
            self._fail_counts[name] = 0
            self._last_ok[name] = True
        else:
            self._fail_counts[name] += 1
            if self._fail_counts[name] >= FAILURE_THRESHOLD:
                self._last_ok[name] = False
            # senão: mantém o último status conhecido (retry com backoff —
            # piscada isolada não derruba o readiness)

        return {
            "ok": self._last_ok[name],
            "raw_ok": ok_now,
            "consecutive_failures": self._fail_counts[name],
        }

    # -- refresh (única função que toca dependência) -------------------------

    def refresh(self) -> ReadinessState:
        from app.api.v1.health.routes import (
            _check_database,
            _check_redis,
            _contar_jobs_em_voo,
        )

        invariants = {
            "worker_class": self.check_worker_class(),
            "storage_backend": self.check_storage_backend(),
        }
        dependencies = {
            "database": self._check_dependency("database", _check_database),
            "redis": self._check_dependency("redis", _check_redis),
        }
        ready = all(c["ok"] for c in invariants.values()) and all(
            c["ok"] for c in dependencies.values()
        )
        # Só conta se o banco respondeu neste ciclo. Contar com o banco caído
        # devolveria None de qualquer jeito, mas evitar a query poupa o timeout
        # e mantém o refresher no seu intervalo.
        running_jobs = (
            _contar_jobs_em_voo() if dependencies["database"]["ok"] else None
        )
        state = ReadinessState(
            checked_at=time.monotonic(),
            ready=ready,
            invariants=invariants,
            dependencies=dependencies,
            running_jobs=running_jobs,
        )
        with self._lock:
            self._state = state
        return state

    def get_state(self) -> ReadinessState:
        """Lido pelo handler HTTP. NUNCA toca dependência — só o cache.

        Exceção: bootstrap. Se o processo nunca teve um ciclo do refresher
        (primeira request logo após o boot, ou ambiente sem loop de fundo —
        ver `start_background_refresh`/pytest), computa uma vez inline com o
        MESMO `refresh()` usado pelo loop. É o fallback "refresh on-demand"
        documentado no relatório do item 2.3 — não é o caminho normal em
        produção contínua, só cobre o instante antes do primeiro tick.
        """
        with self._lock:
            state = self._state
        if state is None:
            return self.refresh()
        return state

    def peek_running_jobs(self) -> int | None:
        """Jobs de treino em voo, ⛔ SEM tocar dependência nenhuma.

        Diferente de `get_state()`, que computa inline quando ainda não houve
        ciclo do refresher: quem chama isto é o `/livez`, que promete NUNCA
        tocar DB/Redis. Um `/livez` que consulta banco vira loop de restart do
        Railway na primeira queda de banco — o oposto do que liveness serve.

        Devolve None quando não há snapshot ainda, quando o snapshot está velho
        (o refresher pode ter morrido — número congelado é mentira), ou quando o
        ciclo não conseguiu contar.

        ⚠️ None NUNCA vira 0: "não sei" e "não tem" são respostas diferentes, e
        confundi-las foi exatamente como a checagem de pod em voo falhou.
        """
        with self._lock:
            state = self._state
        if state is None:
            return None
        if time.monotonic() - state.checked_at > STALE_AFTER_SECONDS:
            return None
        return state.running_jobs

    def reset_for_tests(self) -> None:
        """Só para testes: limpa cache e contadores entre casos."""
        with self._lock:
            self._state = None
        self._fail_counts = {"database": 0, "redis": 0}
        self._last_ok = {"database": True, "redis": True}

    # -- loop de fundo --------------------------------------------------------

    def start_background_refresh(self) -> None:
        """Spawna o refresher periódico. Idempotente (1x por processo).

        Mecanismo primário: gevent.spawn — o processo roda sob o
        GeventWebSocketWorker em produção, então o loop é um greenlet
        cooperativo de baixo custo, coerente com o resto do app.
        Fallback: threading.Thread(daemon=True) se gevent não puder ser
        importado. Não é degradação silenciosa do contrato: o loop entrega
        exatamente o mesmo refresh() no mesmo intervalo, só trocando o
        mecanismo de agendamento — e fica logado em warning.
        """
        with self._lock:
            if self._bg_started:
                return
            self._bg_started = True

        def _loop() -> None:
            while True:
                try:
                    self.refresh()
                except Exception:
                    logger.exception("readiness_refresh_loop_error")
                _cooperative_sleep(REFRESH_INTERVAL_SECONDS)

        try:
            import gevent

            gevent.spawn(_loop)
            logger.info(
                "readiness_refresh: gevent.spawn OK (ciclo a cada %ss)",
                REFRESH_INTERVAL_SECONDS,
            )
        except Exception as exc:
            logger.warning(
                "readiness_refresh: gevent indisponível (%s) — fallback thread daemon "
                "(mesmo contrato, mecanismo diferente)",
                exc,
            )
            threading.Thread(target=_loop, daemon=True, name="readyz-refresh").start()


def _cooperative_sleep(seconds: float) -> None:
    """gevent.sleep quando disponível (cede o hub); senão time.sleep real."""
    try:
        import gevent

        gevent.sleep(seconds)
    except Exception:
        time.sleep(seconds)


# Singleton — um por processo, importado por routes.py e por app/__init__.py
cache = ReadinessCache()
