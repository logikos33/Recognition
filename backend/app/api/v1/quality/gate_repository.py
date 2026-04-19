"""
Gate Repository — acesso às tabelas do quality gate.

Tabelas gerenciadas:
  - quality_pieces       : peças rastreadas, status e histórico
  - quality_reworks      : registros de retrabalho por peça
  - quality_wiser_exports: log de exportações para o Wiser
  - quality_stations     : bancadas de inspeção (metadados e config)

Padrão obrigatório:
  - psycopg2 direto, cursor() em DatabasePool.get_connection()
  - SET search_path TO {schema}, public antes de toda query
  - RealDictCursor → rows são dicts → acesso por nome: row["id"]
  - RETURNING * em todos os INSERT/UPDATE
  - UUIDs convertidos para str ao retornar JSON
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


class GateRepository:
    """Repository para as tabelas do quality gate.

    Arg:
        pool: Instância do DatabasePool (já inicializado em create_app()).
    """

    def __init__(self, pool):
        """Inicializa o repositório com o pool de conexões.

        Args:
            pool: DatabasePool.get_instance() — nunca None quando chamado em runtime.
        """
        self._pool = pool

    # ------------------------------------------------------------------ #
    # Helpers internos                                                     #
    # ------------------------------------------------------------------ #

    def _set_schema(self, cur, schema: str) -> None:
        """Aplica search_path para isolamento por tenant."""
        cur.execute("SET search_path TO %s, public", (schema,))

    def _row_to_dict(self, row) -> dict:
        """Converte row do RealDictCursor para dict com UUIDs serializados."""
        if row is None:
            return {}
        result = {}
        for key, value in row.items():
            # Converte UUID para str para compatibilidade JSON
            result[key] = str(value) if hasattr(value, "hex") else value
        return result

    def _rows_to_list(self, rows) -> list[dict]:
        """Converte lista de rows para lista de dicts."""
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # quality_pieces                                                       #
    # ------------------------------------------------------------------ #

    def create_piece(self, schema: str, data: dict) -> dict:
        """Cria nova peça no estado inicial.

        Args:
            schema: Schema do tenant.
            data: Dict com campos da peça (piece_number, work_order, product_type, etc.).

        Returns:
            Dict com os campos da peça criada (RETURNING *).
        """
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                """
                INSERT INTO quality_pieces (
                    id, piece_number, work_order, product_type,
                    status, operator_id, tenant_id,
                    total_rework_count, total_rework_time_seconds,
                    wiser_exported, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    %(piece_number)s, %(work_order)s, %(product_type)s,
                    %(status)s, %(operator_id)s, %(tenant_id)s,
                    0, 0,
                    false, NOW(), NOW()
                ) RETURNING *
                """,
                data,
            )
            row = cur.fetchone()
            return self._row_to_dict(row)

    def get_piece(self, schema: str, piece_id: str) -> dict | None:
        """Busca peça por ID.

        Args:
            schema: Schema do tenant.
            piece_id: UUID da peça (string).

        Returns:
            Dict com os campos da peça, ou None se não encontrada.
        """
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                "SELECT * FROM quality_pieces WHERE id = %s",
                (piece_id,),
            )
            row = cur.fetchone()
            return self._row_to_dict(row) if row else None

    def get_pieces(
        self,
        schema: str,
        filters: dict | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Lista peças com filtros opcionais.

        Args:
            schema: Schema do tenant.
            filters: Dict com filtros opcionais (status, work_order, product_type,
                     date_from, date_to).
            limit: Número máximo de registros retornados.
            offset: Offset para paginação.

        Returns:
            Lista de dicts representando as peças.
        """
        filters = filters or {}
        conditions = ["1=1"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if "status" in filters and filters["status"]:
            conditions.append("status = %(status)s")
            params["status"] = filters["status"]

        if "work_order" in filters and filters["work_order"]:
            conditions.append("work_order = %(work_order)s")
            params["work_order"] = filters["work_order"]

        if "product_type" in filters and filters["product_type"]:
            conditions.append("product_type = %(product_type)s")
            params["product_type"] = filters["product_type"]

        if "date_from" in filters and filters["date_from"]:
            conditions.append("created_at >= %(date_from)s")
            params["date_from"] = filters["date_from"]

        if "date_to" in filters and filters["date_to"]:
            conditions.append("created_at <= %(date_to)s")
            params["date_to"] = filters["date_to"]

        where_clause = " AND ".join(conditions)

        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                f"SELECT * FROM quality_pieces WHERE {where_clause} "  # noqa: S608
                "ORDER BY created_at DESC LIMIT %(limit)s OFFSET %(offset)s",
                params,
            )
            return self._rows_to_list(cur.fetchall())

    def update_piece_status(
        self,
        schema: str,
        piece_id: str,
        new_status: str,
        extra_fields: dict | None = None,
    ) -> dict:
        """Atualiza status da peça e campos extras opcionais.

        Args:
            schema: Schema do tenant.
            piece_id: UUID da peça.
            new_status: Novo status conforme state_machine.VALID_TRANSITIONS.
            extra_fields: Dict com campos adicionais a atualizar (ex: photo_quality_path).

        Returns:
            Dict com os campos atualizados da peça (RETURNING *).
        """
        extra_fields = extra_fields or {}
        set_parts = ["status = %(status)s", "updated_at = NOW()"]
        params: dict[str, Any] = {"status": new_status, "piece_id": piece_id}

        for field, value in extra_fields.items():
            set_parts.append(f"{field} = %({field})s")
            params[field] = value

        set_clause = ", ".join(set_parts)

        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                f"UPDATE quality_pieces SET {set_clause} WHERE id = %(piece_id)s RETURNING *",  # noqa: S608
                params,
            )
            row = cur.fetchone()
            return self._row_to_dict(row) if row else {}

    def update_piece(self, schema: str, piece_id: str, data: dict) -> dict:
        """Atualiza campos arbitrários de uma peça.

        Args:
            schema: Schema do tenant.
            piece_id: UUID da peça.
            data: Dict com campos a atualizar.

        Returns:
            Dict com os campos atualizados da peça (RETURNING *).
        """
        if not data:
            return self.get_piece(schema, piece_id) or {}

        set_parts = [f"{key} = %({key})s" for key in data]
        set_parts.append("updated_at = NOW()")
        set_clause = ", ".join(set_parts)
        params = dict(data)
        params["piece_id"] = piece_id

        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                f"UPDATE quality_pieces SET {set_clause} WHERE id = %(piece_id)s RETURNING *",  # noqa: S608
                params,
            )
            row = cur.fetchone()
            return self._row_to_dict(row) if row else {}

    # ------------------------------------------------------------------ #
    # quality_reworks                                                      #
    # ------------------------------------------------------------------ #

    def create_rework(self, schema: str, data: dict) -> dict:
        """Registra início de retrabalho.

        Args:
            schema: Schema do tenant.
            data: Dict com piece_id, validation_type, defect_type, defect_description,
                  photo_before_path, photo_before_r2_key, operator_id, tenant_id.

        Returns:
            Dict com os campos do retrabalho criado (RETURNING *).
        """
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                """
                INSERT INTO quality_reworks (
                    id, piece_id, validation_type,
                    defect_type, defect_description,
                    photo_before_path, photo_before_r2_key,
                    operator_id, tenant_id,
                    started_at, created_at
                ) VALUES (
                    gen_random_uuid(),
                    %(piece_id)s, %(validation_type)s,
                    %(defect_type)s, %(defect_description)s,
                    %(photo_before_path)s, %(photo_before_r2_key)s,
                    %(operator_id)s, %(tenant_id)s,
                    NOW(), NOW()
                ) RETURNING *
                """,
                data,
            )
            row = cur.fetchone()
            return self._row_to_dict(row)

    def complete_rework(
        self,
        schema: str,
        rework_id: str,
        completed_at,
        duration_seconds: int,
        photo_after_path: str | None = None,
        photo_after_r2_key: str | None = None,
    ) -> dict:
        """Registra conclusão do retrabalho com duração e foto final.

        Args:
            schema: Schema do tenant.
            rework_id: UUID do registro de retrabalho.
            completed_at: Timestamp de conclusão (datetime ou ISO string).
            duration_seconds: Duração total do retrabalho em segundos.
            photo_after_path: Caminho local da foto após retrabalho (opcional).
            photo_after_r2_key: Chave R2 da foto após retrabalho (opcional).

        Returns:
            Dict com os campos atualizados do retrabalho (RETURNING *).
        """
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                """
                UPDATE quality_reworks
                SET completed_at = %(completed_at)s,
                    duration_seconds = %(duration_seconds)s,
                    photo_after_path = %(photo_after_path)s,
                    photo_after_r2_key = %(photo_after_r2_key)s
                WHERE id = %(rework_id)s
                RETURNING *
                """,
                {
                    "rework_id": rework_id,
                    "completed_at": completed_at,
                    "duration_seconds": duration_seconds,
                    "photo_after_path": photo_after_path,
                    "photo_after_r2_key": photo_after_r2_key,
                },
            )
            row = cur.fetchone()
            return self._row_to_dict(row) if row else {}

    def get_reworks_for_piece(self, schema: str, piece_id: str) -> list[dict]:
        """Retorna todos os retrabalhos de uma peça específica.

        Args:
            schema: Schema do tenant.
            piece_id: UUID da peça.

        Returns:
            Lista de dicts de retrabalho, ordenados por started_at ASC.
        """
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                "SELECT * FROM quality_reworks WHERE piece_id = %s ORDER BY started_at ASC",
                (piece_id,),
            )
            return self._rows_to_list(cur.fetchall())

    def get_reworks(
        self,
        schema: str,
        filters: dict | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Lista retrabalhos com filtros opcionais.

        Args:
            schema: Schema do tenant.
            filters: Dict com filtros opcionais (piece_id, validation_type, date_from, date_to).
            limit: Número máximo de registros.
            offset: Offset para paginação.

        Returns:
            Lista de dicts de retrabalho ordenados por started_at DESC.
        """
        filters = filters or {}
        conditions = ["1=1"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if "piece_id" in filters and filters["piece_id"]:
            conditions.append("piece_id = %(piece_id)s")
            params["piece_id"] = filters["piece_id"]

        if "validation_type" in filters and filters["validation_type"]:
            conditions.append("validation_type = %(validation_type)s")
            params["validation_type"] = filters["validation_type"]

        if "date_from" in filters and filters["date_from"]:
            conditions.append("started_at >= %(date_from)s")
            params["date_from"] = filters["date_from"]

        if "date_to" in filters and filters["date_to"]:
            conditions.append("started_at <= %(date_to)s")
            params["date_to"] = filters["date_to"]

        where_clause = " AND ".join(conditions)

        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                f"SELECT * FROM quality_reworks WHERE {where_clause} "  # noqa: S608
                "ORDER BY started_at DESC LIMIT %(limit)s OFFSET %(offset)s",
                params,
            )
            return self._rows_to_list(cur.fetchall())

    # ------------------------------------------------------------------ #
    # quality_wiser_exports                                                #
    # ------------------------------------------------------------------ #

    def create_export_log(self, schema: str, data: dict) -> dict:
        """Registra log de exportação para o Wiser.

        Args:
            schema: Schema do tenant.
            data: Dict com piece_id, method, path, success, error, tenant_id.

        Returns:
            Dict com os campos do log criado (RETURNING *).
        """
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                """
                INSERT INTO quality_wiser_exports (
                    id, piece_id, method, path,
                    success, error, tenant_id, created_at
                ) VALUES (
                    gen_random_uuid(),
                    %(piece_id)s, %(method)s, %(path)s,
                    %(success)s, %(error)s, %(tenant_id)s,
                    NOW()
                ) RETURNING *
                """,
                data,
            )
            row = cur.fetchone()
            return self._row_to_dict(row)

    def get_exports_for_piece(self, schema: str, piece_id: str) -> list[dict]:
        """Retorna todos os logs de exportação de uma peça.

        Args:
            schema: Schema do tenant.
            piece_id: UUID da peça.

        Returns:
            Lista de dicts de exportação, ordenados por created_at DESC.
        """
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                "SELECT * FROM quality_wiser_exports WHERE piece_id = %s ORDER BY created_at DESC",
                (piece_id,),
            )
            return self._rows_to_list(cur.fetchall())

    # ------------------------------------------------------------------ #
    # quality_stations                                                     #
    # ------------------------------------------------------------------ #

    def create_or_update_station(self, schema: str, data: dict) -> dict:
        """Cria ou atualiza uma bancada de inspeção (upsert por station_code).

        Args:
            schema: Schema do tenant.
            data: Dict com station_code, name, description, current_piece_id,
                  camera_ids, tenant_id.

        Returns:
            Dict com os campos da bancada (RETURNING *).
        """
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                """
                INSERT INTO quality_stations (
                    id, station_code, name, description,
                    current_piece_id, camera_ids, tenant_id,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    %(station_code)s, %(name)s, %(description)s,
                    %(current_piece_id)s, %(camera_ids)s, %(tenant_id)s,
                    NOW(), NOW()
                )
                ON CONFLICT (station_code) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    current_piece_id = EXCLUDED.current_piece_id,
                    camera_ids = EXCLUDED.camera_ids,
                    updated_at = NOW()
                RETURNING *
                """,
                data,
            )
            row = cur.fetchone()
            return self._row_to_dict(row)

    def get_station(self, schema: str, station_code: str) -> dict | None:
        """Busca bancada de inspeção pelo código.

        Args:
            schema: Schema do tenant.
            station_code: Código único da bancada (ex: "BANCADA_A").

        Returns:
            Dict com os campos da bancada, ou None se não encontrada.
        """
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                "SELECT * FROM quality_stations WHERE station_code = %s",
                (station_code,),
            )
            row = cur.fetchone()
            return self._row_to_dict(row) if row else None

    def get_all_stations(self, schema: str) -> list[dict]:
        """Retorna todas as bancadas de inspeção do tenant.

        Args:
            schema: Schema do tenant.

        Returns:
            Lista de dicts de bancadas, ordenadas por station_code ASC.
        """
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute("SELECT * FROM quality_stations ORDER BY station_code ASC")
            return self._rows_to_list(cur.fetchall())

    # ------------------------------------------------------------------ #
    # Queries de estatísticas                                              #
    # ------------------------------------------------------------------ #

    def get_overview_stats(self, schema: str) -> dict:
        """Retorna estatísticas gerais do quality gate para o dia atual.

        Métricas:
          - pieces_today: total de peças criadas hoje
          - pieces_approved: total de peças aprovadas hoje
          - pieces_nok: total de peças com retrabalho hoje
          - nok_rate: taxa de NOK (%)
          - rework_count: total de retrabalhos hoje

        Args:
            schema: Schema do tenant.

        Returns:
            Dict com as métricas calculadas.
        """
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE)
                        AS pieces_today,
                    COUNT(*) FILTER (
                        WHERE status = 'approved' AND created_at >= CURRENT_DATE
                    ) AS pieces_approved,
                    COUNT(*) FILTER (
                        WHERE total_rework_count > 0 AND created_at >= CURRENT_DATE
                    ) AS pieces_nok,
                    ROUND(
                        100.0 * COUNT(*) FILTER (
                            WHERE total_rework_count > 0
                            AND created_at >= CURRENT_DATE
                        ) / NULLIF(
                            COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE), 0
                        ),
                        2
                    ) AS nok_rate
                FROM quality_pieces
                """
            )
            row = cur.fetchone()
            stats = self._row_to_dict(row) if row else {}

            # Total de retrabalhos hoje
            cur.execute(
                "SELECT COUNT(*) AS rework_count "
                "FROM quality_reworks WHERE started_at >= CURRENT_DATE"
            )
            rework_row = cur.fetchone()
            stats["rework_count"] = rework_row["rework_count"] if rework_row else 0

            return stats

    def get_rework_stats(self, schema: str) -> dict:
        """Retorna estatísticas detalhadas de retrabalho.

        Métricas:
          - by_validation: contagem de NOKs por tipo de validação (v1/v2/v3)
          - avg_rework_duration_seconds: tempo médio de retrabalho em segundos
          - most_common_defect: tipo de defeito mais frequente

        Args:
            schema: Schema do tenant.

        Returns:
            Dict com as métricas de retrabalho.
        """
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            self._set_schema(cur, schema)

            # Contagem por tipo de validação
            cur.execute(
                """
                SELECT validation_type, COUNT(*) AS count
                FROM quality_reworks
                GROUP BY validation_type
                ORDER BY count DESC
                """
            )
            by_validation = {row["validation_type"]: row["count"] for row in cur.fetchall()}

            # Tempo médio de retrabalho (apenas concluídos)
            cur.execute(
                """
                SELECT ROUND(AVG(duration_seconds), 2) AS avg_duration
                FROM quality_reworks
                WHERE completed_at IS NOT NULL AND duration_seconds IS NOT NULL
                """
            )
            avg_row = cur.fetchone()
            avg_duration = (
                float(avg_row["avg_duration"]) if avg_row and avg_row["avg_duration"] else 0.0
            )

            # Defeito mais comum
            cur.execute(
                """
                SELECT defect_type, COUNT(*) AS count
                FROM quality_reworks
                WHERE defect_type IS NOT NULL
                GROUP BY defect_type
                ORDER BY count DESC
                LIMIT 1
                """
            )
            defect_row = cur.fetchone()
            most_common_defect = defect_row["defect_type"] if defect_row else None

            return {
                "by_validation": by_validation,
                "avg_rework_duration_seconds": avg_duration,
                "most_common_defect": most_common_defect,
            }
