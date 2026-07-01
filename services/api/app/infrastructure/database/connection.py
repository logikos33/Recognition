"""
INFRASTRUCTURE connection.py — PostgreSQL connection pool singleton for all repositories.

Layer: infrastructure
Pattern: Singleton, Context Manager

Key exports:
  - DatabasePool.initialize(database_url, min_conn, max_conn): called once in create_app();
    builds psycopg2.pool.ThreadedConnectionPool with RealDictCursor as default cursor factory
  - DatabasePool.get_instance(): returns existing singleton or None; used by repositories
  - DatabasePool.get_connection(): context manager — acquires connection, auto-commits on success,
    auto-rollbacks and re-raises on psycopg2.Error (wrapped as DatabaseError), always returns to pool
  - DatabasePool.reset(): closes all connections and clears singleton — test teardown only
  - get_database_url(): normalizes postgres:// to postgresql:// for SQLAlchemy/psycopg2 compatibility

Constraints:
  - NEVER call psycopg2.connect() directly — always use DatabasePool.get_connection()
  - All queries run through BaseRepository which uses this pool internally
  - Default pool: min=1, max=10 connections; tune via initialize() args if needed

Related: app/infrastructure/database/repositories/ (all use DatabasePool.get_instance())
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
                # Higieniza a conexão antes de devolver ao pool: reset() faz
                # ROLLBACK + RESET ALL, limpando qualquer `SET search_path TO
                # <tenant>` deixado pelo handler anterior. Sem isso, a próxima
                # request que reusar esta conexão herdaria o schema do tenant
                # anterior (risco latente de leak cross-tenant). Best-effort —
                # nunca impede putconn nem mascara o erro original.
                try:
                    conn.reset()
                except Exception:  # noqa: S110
                    pass
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
