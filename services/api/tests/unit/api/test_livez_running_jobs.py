"""O /livez precisa responder "há pod em voo?" sem perguntar a ninguém.

A regra de convivência entre sessões é: merge na develop redeploya API e worker,
e o deploy do worker MATA o vigia de um pod em voo. A pergunta ficou TRÊS vezes
sem resposta numa rodada só, e a alternativa à mão (consultar o banco local)
devolveu "zero pods" porque a tabela estava vazia — zero pelo motivo errado.

Dois invariantes, e o segundo é o que importa:

1. `running_jobs` sai no /livez.
2. ⚠️ `null` NUNCA vira 0. "Não sei" e "não tem" são respostas diferentes. A
   regra é `running_jobs == 0`, então `null` BLOQUEIA o merge.

E um terceiro, estrutural: o /livez ⛔ NÃO pode tocar o banco. Ele é o probe que
o Railway usa para reiniciar processo travado — consultar banco ali vira loop de
restart na primeira queda de banco.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from app.api.v1.health import routes as health_routes
from app.api.v1.health.readiness import (
    STALE_AFTER_SECONDS,
    ReadinessCache,
    ReadinessState,
)


@pytest.fixture
def cliente():
    app = Flask(__name__)
    app.register_blueprint(health_routes.health_bp)
    return app.test_client()


def _cache_com(running_jobs, idade_segundos=0.0):
    cache = ReadinessCache()
    cache._state = ReadinessState(
        checked_at=time.monotonic() - idade_segundos,
        ready=True,
        running_jobs=running_jobs,
    )
    return cache


class TestLivezExpoeJobsEmVoo:
    def test_zero_jobs_sai_como_zero(self, cliente, monkeypatch):
        monkeypatch.setattr(health_routes, "_readiness_cache", _cache_com(0))
        assert cliente.get("/livez").get_json()["running_jobs"] == 0

    def test_jobs_em_voo_saem_contados(self, cliente, monkeypatch):
        monkeypatch.setattr(health_routes, "_readiness_cache", _cache_com(2))
        assert cliente.get("/livez").get_json()["running_jobs"] == 2

    def test_sem_ciclo_do_refresher_e_null_nao_zero(self, cliente, monkeypatch):
        """Boot recém-feito: ninguém contou ainda. Não sei ≠ não tem."""
        cache = ReadinessCache()
        cache._state = None
        monkeypatch.setattr(health_routes, "_readiness_cache", cache)
        assert cliente.get("/livez").get_json()["running_jobs"] is None

    def test_snapshot_velho_e_null_nao_o_numero_congelado(self, cliente, monkeypatch):
        """Refresher morto devolveria para sempre o último número. Mentira congelada."""
        monkeypatch.setattr(
            health_routes, "_readiness_cache",
            _cache_com(0, idade_segundos=STALE_AFTER_SECONDS + 5),
        )
        assert cliente.get("/livez").get_json()["running_jobs"] is None

    def test_ciclo_que_nao_conseguiu_contar_e_null(self, cliente, monkeypatch):
        monkeypatch.setattr(health_routes, "_readiness_cache", _cache_com(None))
        assert cliente.get("/livez").get_json()["running_jobs"] is None

    def test_livez_nao_toca_o_banco(self, cliente, monkeypatch):
        """O contrato do /livez: NUNCA DB/Redis/R2. Senão vira loop de restart."""
        cache = ReadinessCache()
        cache._state = None  # pior caso: sem snapshot, tentado a computar
        monkeypatch.setattr(health_routes, "_readiness_cache", cache)
        with patch.object(health_routes, "_contar_jobs_em_voo") as contou, \
             patch.object(health_routes, "_check_database") as checou:
            resp = cliente.get("/livez")
        assert resp.status_code == 200
        contou.assert_not_called()
        checou.assert_not_called()

    def test_commit_continua_saindo(self, cliente, monkeypatch):
        """A adição não pode comer o campo que já existia."""
        monkeypatch.setattr(health_routes, "_readiness_cache", _cache_com(0))
        corpo = cliente.get("/livez").get_json()
        assert "commit" in corpo and corpo["status"] == "alive"


class TestContagemNoRefresher:
    def test_banco_fora_devolve_null_em_todo_ciclo(self):
        """⚠️ `database.ok` só vira False depois de FAILURE_THRESHOLD falhas
        consecutivas — é tolerância deliberada a piscada de rede, e o guard da
        contagem herda essa tolerância.

        Nos primeiros ciclos o `ok` ainda é True e a contagem É tentada; ela
        devolve None por conta própria porque o banco está fora. Depois do
        limiar, nem tenta. O que precisa valer SEMPRE é o resultado:
        banco fora ⇒ `running_jobs is None`, nunca 0.
        """
        cache = ReadinessCache()
        with patch("app.api.v1.health.routes._check_database", return_value=False), \
             patch("app.api.v1.health.routes._check_redis", return_value=True), \
             patch(
                 "app.api.v1.health.routes._contar_jobs_em_voo", return_value=None
             ) as contou:
            estados = [cache.refresh() for _ in range(5)]

        assert all(e.running_jobs is None for e in estados), (
            "banco fora nunca pode virar 'zero jobs' — é o zero pelo motivo errado"
        )
        assert not estados[-1].dependencies["database"]["ok"], "deveria ter flipado"
        chamadas_antes = contou.call_count
        with patch("app.api.v1.health.routes._check_database", return_value=False), \
             patch("app.api.v1.health.routes._check_redis", return_value=True), \
             patch(
                 "app.api.v1.health.routes._contar_jobs_em_voo", return_value=None
             ) as contou_depois:
            cache.refresh()
        assert contou_depois.call_count == 0, (
            "com o banco já reprovado, o ciclo não gasta timeout tentando contar"
        )
        assert chamadas_antes < 5, "depois do limiar deve parar de tentar"

    def test_banco_ok_conta(self):
        cache = ReadinessCache()
        with patch("app.api.v1.health.routes._check_database", return_value=True), \
             patch("app.api.v1.health.routes._check_redis", return_value=True), \
             patch("app.api.v1.health.routes._contar_jobs_em_voo", return_value=3):
            estado = cache.refresh()
        assert estado.running_jobs == 3

    def test_probe_devolve_none_quando_o_pool_nao_existe(self):
        with patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            return_value=None,
        ):
            assert health_routes._contar_jobs_em_voo() is None

    def test_probe_devolve_none_e_nao_levanta_quando_a_query_falha(self):
        pool = MagicMock()
        pool.get_connection.side_effect = RuntimeError("db fora")
        with patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            return_value=pool,
        ):
            assert health_routes._contar_jobs_em_voo() is None
