"""
Repository: Inspection Sessions — integração monofatura (task-108, ADR-0053).

Tabela gerenciada: {tenant_schema}.inspection_sessions (schema-per-tenant,
SEM tenant_id — ADR-0004/0016: o schema É o isolamento; criada na migration 104).

Padrão obrigatório (mesmo do GateRepository):
  - psycopg2 direto, cursor() em DatabasePool.get_connection()
  - SET search_path TO %s, public — SEMPRE parametrizado, nunca f-string
  - RealDictCursor → rows são dicts → acesso por nome: row["id"]
  - RETURNING * em todos os INSERT/UPDATE
  - UUIDs convertidos para str ao retornar

Idempotência do inbound (bipagem): UNIQUE (piece_id, stage) +
INSERT ... ON CONFLICT DO UPDATE ... RETURNING * — a segunda bipagem da
mesma peça×etapa devolve a MESMA sessão, sem duplicar nem resetar estado.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


class InspectionSessionRepository:
    """Repository para {tenant_schema}.inspection_sessions.

    Args:
        pool: Instância do DatabasePool (DatabasePool.get_instance()).
    """

    def __init__(self, pool) -> None:
        self._pool = pool

    # ------------------------------------------------------------------ #
    # Helpers internos                                                    #
    # ------------------------------------------------------------------ #

    def _set_schema(self, cur, schema: str) -> None:
        """Aplica search_path para isolamento por tenant (parametrizado)."""
        cur.execute("SET search_path TO %s, public", (schema,))

    def _row_to_dict(self, row) -> dict[str, Any] | None:
        """Converte row do RealDictCursor em dict com UUIDs serializados."""
        if row is None:
            return None
        return {
            key: str(value) if hasattr(value, "hex") else value
            for key, value in row.items()
        }

    # ------------------------------------------------------------------ #
    # Queries                                                             #
    # ------------------------------------------------------------------ #

    def open_session(
        self,
        schema: str,
        piece_id: str,
        stage: str,
        camera_id: str | None = None,
    ) -> dict[str, Any]:
        """Abre (ou retorna) a sessão de inspeção da peça×etapa — idempotente.

        ON CONFLICT (piece_id, stage) DO UPDATE no-op (reatribui piece_id)
        apenas para o RETURNING * devolver a linha existente. Bipagem
        repetida NÃO duplica sessão nem reabre uma sessão já concluída.
        """
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                """
                INSERT INTO inspection_sessions (piece_id, stage, camera_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (piece_id, stage)
                DO UPDATE SET piece_id = EXCLUDED.piece_id
                RETURNING *
                """,
                (piece_id, stage, camera_id),
            )
            return self._row_to_dict(cur.fetchone())  # type: ignore[return-value]

    def get_session(
        self, schema: str, piece_id: str, stage: str
    ) -> dict[str, Any] | None:
        """Busca sessão por peça×etapa. None se não existir (→ 404 na rota)."""
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                "SELECT * FROM inspection_sessions WHERE piece_id = %s AND stage = %s",
                (piece_id, stage),
            )
            return self._row_to_dict(cur.fetchone())

    def complete_session(
        self,
        schema: str,
        piece_id: str,
        stage: str,
        result_json: str,
        evidence_r2_key: str | None = None,
    ) -> dict[str, Any] | None:
        """Fecha a sessão da peça×etapa e grava result JSONB + evidência.

        Retorna a sessão atualizada ou None se não existir (→ 404 na rota).
        """
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                """
                UPDATE inspection_sessions
                SET status = 'completed',
                    finished_at = NOW(),
                    result = %s::jsonb,
                    evidence_r2_key = COALESCE(%s, evidence_r2_key)
                WHERE piece_id = %s AND stage = %s
                RETURNING *
                """,
                (result_json, evidence_r2_key, piece_id, stage),
            )
            return self._row_to_dict(cur.fetchone())

    def list_sessions(
        self,
        schema: str,
        piece_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Lista sessões do tenant, opcionalmente filtradas por piece_id."""
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            if piece_id:
                cur.execute(
                    "SELECT * FROM inspection_sessions WHERE piece_id = %s "
                    "ORDER BY created_at DESC LIMIT %s",
                    (piece_id, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM inspection_sessions "
                    "ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
            return [self._row_to_dict(r) for r in cur.fetchall()]  # type: ignore[misc]
