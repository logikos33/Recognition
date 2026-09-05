"""Guarda de saldo e cotação por tier — as duas coisas que deixaram passar
gasto acima do autorizado em 02/09."""
from __future__ import annotations

import math

import pytest

from app.infrastructure.gpu.runpod_runner import (
    JobKind,
    SaldoInsuficienteError,
    check_saldo,
)


class _Cliente:
    def __init__(self, saldo=None, erro=None):
        self._saldo, self._erro = saldo, erro

    def get_saldo(self):
        if self._erro:
            raise self._erro
        return self._saldo


class TestGuardaDeSaldo:
    def test_saldo_folgado_passa(self):
        assert check_saldo(_Cliente(saldo=100.0), 8.93, kind=JobKind.TRAIN) == 100.0

    def test_saldo_menor_que_o_job_bloqueia(self):
        """O caso real: teto autorizado $40, saldo $20,30, três pods de $8,93."""
        with pytest.raises(SaldoInsuficienteError) as exc:
            check_saldo(_Cliente(saldo=5.0), 8.93, kind=JobKind.TRAIN)
        assert "5.00" in str(exc.value) and "8.93" in str(exc.value)

    def test_margem_bloqueia_o_que_cabe_no_fio(self):
        """Saldo 10 e custo 8,93 'cabe', mas sem folga: 8,93 × 1,25 = 11,16."""
        with pytest.raises(SaldoInsuficienteError):
            check_saldo(_Cliente(saldo=10.0), 8.93, kind=JobKind.TRAIN)

    def test_saldo_ilegivel_nao_bloqueia(self, caplog):
        """Billing fora do ar não pode impedir treino autorizado — o teto guarda."""
        r = check_saldo(_Cliente(erro=RuntimeError("api down")), 8.93, kind=JobKind.TRAIN)
        assert math.isnan(r)
        assert "saldo ilegível" in caplog.text

    def test_alerta_quando_folga_e_curta(self, caplog):
        """Passa, mas grita — é o alerta que o dono pediu, antes do bloqueio."""
        check_saldo(_Cliente(saldo=20.30), 8.93, kind=JobKind.TRAIN)
        assert "runpod_saldo_baixo" in caplog.text
