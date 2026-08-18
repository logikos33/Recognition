"""
D-166 — o bootstrap de admin e a migration 046 se desfaziam a cada deploy.

`railway_start.create_admin()` rodava a cada boot e inseria em `users` **sem
`tenant_id`**. A migration `046_deactivate_default_tenant.sql` (ADR-0017)
desativa justamente os usuários do tenant `default`. Os dois rodavam todo
deploy, um desfazendo o outro — foi assim que `ADMIN_EMAIL` acabou apontando
para conta inativa em tenant errado (D-161).

O bootstrap foi escrito para a instalação virgem. Estes testes fixam que é só
nela que ele roda.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parents[5]


@pytest.fixture(scope="module")
def railway_start():
    spec = importlib.util.spec_from_file_location(
        "railway_start_sob_teste", _RAIZ / "railway_start.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class _CursorFake:
    """Devolve, em ordem, as respostas de cada `fetchone()`."""

    def __init__(self, respostas):
        self._respostas = list(respostas)
        self.sqls: list[str] = []

    def execute(self, sql, params=None):
        self.sqls.append(" ".join(sql.split()))

    def fetchone(self):
        return self._respostas.pop(0)


class TestInstalacaoVirgem:
    def test_sem_tabela_tenants_e_virgem(self, railway_start):
        """Schema anterior à tabela: não há tenant que possa ser desfeito."""
        cur = _CursorFake([(False,)])
        assert railway_start._instalacao_virgem(cur) is True
        assert len(cur.sqls) == 1, "não deve consultar tenants que não existe"

    def test_tabela_vazia_e_virgem(self, railway_start):
        cur = _CursorFake([(True,), (False,)])
        assert railway_start._instalacao_virgem(cur) is True

    def test_com_tenant_nao_e_virgem(self, railway_start):
        """⚠️ O caso real: DEV e produção têm tenant. O bootstrap não roda."""
        cur = _CursorFake([(True,), (True,)])
        assert railway_start._instalacao_virgem(cur) is False
        assert any("FROM public.tenants" in s for s in cur.sqls)
