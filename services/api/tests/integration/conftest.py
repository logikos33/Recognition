"""
Fixtures de integração: Postgres real para testes de contagem edge (task-016).

Reusa a mesma variável INTEGRATION_DATABASE_URL (ou HARNESS_DATABASE_URL) do harness
de migrations. Testes são automaticamente pulados se a variável não estiver definida
(ambiente dev sem DB de teste), mas rodam em CI onde a variável é injetada.

NÃO usa mock de repositório — valida SQL real (FILTER/DISTINCT ON).
"""
from __future__ import annotations

import os
from uuid import uuid4

import psycopg2
import psycopg2.extras
import pytest

from app.infrastructure.database.connection import DatabasePool


def _integration_dsn() -> str:
    return (
        os.environ.get("INTEGRATION_DATABASE_URL")
        or os.environ.get("HARNESS_DATABASE_URL")
        or ""
    )


@pytest.fixture(scope="session")
def integration_dsn() -> str:
    dsn = _integration_dsn()
    if not dsn:
        pytest.skip(
            "INTEGRATION_DATABASE_URL (ou HARNESS_DATABASE_URL) não definida "
            "— pulando testes de integração edge"
        )
    return dsn


@pytest.fixture(scope="session")
def pg_pool(integration_dsn: str) -> DatabasePool:  # type: ignore[return]
    """DatabasePool real (sessão) para repositórios de integração."""
    DatabasePool.reset()
    pool = DatabasePool.initialize(integration_dsn, min_conn=1, max_conn=3)
    yield pool  # type: ignore[misc]
    DatabasePool.reset()


@pytest.fixture
def pg_raw(integration_dsn: str):
    """Conexão psycopg2 direta com autocommit para seed e cleanup."""
    conn = psycopg2.connect(
        integration_dsn, cursor_factory=psycopg2.extras.RealDictCursor
    )
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture
def tenant_id(pg_raw) -> str:  # type: ignore[return]
    """Cria tenant efêmero e remove tudo via CASCADE no final do teste."""
    tid = str(uuid4())
    slug = f"inttest-{tid[:8]}"
    with pg_raw.cursor() as cur:
        cur.execute(
            "INSERT INTO public.tenants (id, name, slug) VALUES (%s, %s, %s)",
            (tid, f"IntTest {slug}", slug),
        )
    yield tid
    with pg_raw.cursor() as cur:
        cur.execute("DELETE FROM public.tenants WHERE id = %s", (tid,))
