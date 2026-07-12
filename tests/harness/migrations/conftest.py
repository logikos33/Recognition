"""
Fixtures do harness de migrations.

Isolado de services/api/tests/conftest.py (que importa Flask via `from app import create_app`).
Este conftest não tem dependência de Flask, boto3, opencv ou qualquer lib de app.
"""

import os

import psycopg2
import psycopg2.extras
import pytest


@pytest.fixture(scope="session")
def pg_conn():
    """Conexão ao banco já migrado duas vezes pelo runner (via run.sh ou CI)."""
    dsn = os.environ.get("HARNESS_DATABASE_URL", "")
    if not dsn:
        pytest.fail("HARNESS_DATABASE_URL não definida — execute via run.sh ou defina a variável.")
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    yield conn
    conn.close()
