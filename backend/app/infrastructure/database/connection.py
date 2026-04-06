"""
EPI Monitor V2 — Database Connection Pool.

ThreadedConnectionPool do psycopg2 com Singleton pattern.
REGRA ABSOLUTA: usar get_connection() context manager — NUNCA conexão avulsa.
"""
import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool

from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class DatabasePool:
    """Singleton wrapper para psycopg2.pool.ThreadedConnectionPool.

    Usage:
        pool = DatabasePool.initialize(database_url)
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT ...")
    """

    _instance: Optional["DatabasePool"] = None

    def __init__(
        self,
        database_url: str,
        min_conn: int = 1,
        max_conn: int = 10,
    ) -> None:
        self._database_url = database_url
        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=min_conn,
                maxconn=max_conn,
                dsn=database_url,
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
            logger.info(
                "db_pool_created: min=%d, max=%d",
                min_conn,
                max_conn,
            )
        except psycopg2.Error as exc:
            logger.error("db_pool_creation_failed: %s", exc)
            raise DatabaseError(f"Falha ao criar pool de conexões: {exc}") from exc

    @classmethod
    def initialize(
        cls,
        database_url: str,
        min_conn: int = 1,
        max_conn: int = 10,
    ) -> "DatabasePool":
        """Inicializa o singleton do pool. Chamado no create_app()."""
        if cls._instance is not None:
            logger.warning("db_pool_already_initialized — reusing")
            return cls._instance
        cls._instance = cls(database_url, min_conn, max_conn)
        return cls._instance

    @classmethod
    def get_instance(cls) -> Optional["DatabasePool"]:
        """Retorna instância existente ou None."""
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton — usado em testes."""
        if cls._instance is not None:
            cls._instance.close_all()
            cls._instance = None

    @contextmanager
    def get_connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """Context manager: pega conexão do pool, devolve ao final.

        Auto-commit em sucesso, rollback em erro.
        Conexão SEMPRE retorna ao pool.
        """
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
            conn.commit()
        except psycopg2.Error as exc:
            if conn:
                conn.rollback()
            logger.error("db_query_error: %s", exc)
            raise DatabaseError(str(exc)) from exc
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self._pool.putconn(conn)

    def close_all(self) -> None:
        """Fecha todas as conexões. Chamar no shutdown da app."""
        if hasattr(self, "_pool") and not self._pool.closed:
            self._pool.closeall()
            logger.info("db_pool_closed")


def get_database_url() -> str:
    """Retorna DATABASE_URL corrigida (postgres:// → postgresql://)."""
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url
