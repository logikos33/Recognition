"""
Conexão PostgreSQL compartilhada — API e Worker.

REGRA ABSOLUTA: NUNCA usar next(get_db()).
SEMPRE usar: with get_db_connection() as conn:

Esta foi a causa de 90% dos crashes da V1.
O context manager garante que a conexão SEMPRE fecha,
mesmo em caso de exceção, evitando pool exhaustion.
"""
import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager


def get_database_url() -> str:
    url = os.environ.get('DATABASE_URL', '')
    # Railway usa postgres:// — psycopg2 precisa postgresql://
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


@contextmanager
def get_db_connection():
    """
    ÚNICA forma permitida de conectar ao banco.
    Fecha sempre. Rollback automático em erro.
    """
    conn = None
    try:
        conn = psycopg2.connect(
            get_database_url(),
            connect_timeout=15,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn and not conn.closed:
            conn.close()


def test_connection() -> bool:
    try:
        with get_db_connection() as conn:
            conn.cursor().execute("SELECT 1")
        return True
    except Exception:
        return False
