"""
EPI Monitor V2 — Base Repository.

Abstract base para todos os repositories.
Repositories recebem DatabasePool via __init__ (DI).
Nenhuma query SQL fora dos repositories — regra inviolável.
"""
import logging
from abc import ABC
from typing import Any

from app.infrastructure.database.connection import DatabasePool

logger = logging.getLogger(__name__)


class BaseRepository(ABC):  # noqa: B024
    """Abstract base com métodos comuns de execução SQL."""

    def __init__(self, db_pool: DatabasePool) -> None:
        self._db = db_pool

    def _execute(
        self, query: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        """Executa query SELECT, retorna lista de dicts."""
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def _execute_one(
        self, query: str, params: tuple[Any, ...] = ()
    ) -> dict[str, Any] | None:
        """Executa query SELECT, retorna um dict ou None."""
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def _execute_mutation(
        self, query: str, params: tuple[Any, ...] = ()
    ) -> dict[str, Any] | None:
        """Executa INSERT/UPDATE/DELETE com RETURNING, commita, retorna row."""
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def _execute_mutation_no_return(
        self, query: str, params: tuple[Any, ...] = ()
    ) -> int:
        """Executa INSERT/UPDATE/DELETE sem RETURNING. Retorna rowcount."""
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return cur.rowcount

    def _execute_many(
        self, query: str, params_list: list[tuple[Any, ...]]
    ) -> int:
        """executemany para bulk operations. Retorna total de rows."""
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.executemany(query, params_list)
            return cur.rowcount

    def _execute_in_transaction(self, fn) -> Any:
        """Executa fn(conn, cur) em transação única (BEGIN/COMMIT/ROLLBACK).

        Usar quando múltiplas operações devem ser atômicas.
        fn recebe (conn, cur) e deve retornar o resultado desejado.
        """
        with self._db.get_connection() as conn:
            conn.autocommit = False
            try:
                cur = conn.cursor()
                result = fn(conn, cur)
                conn.commit()
                return result
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.autocommit = True
