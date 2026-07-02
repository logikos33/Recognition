"""Repository: Alerts."""
import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class AlertRepository(BaseRepository):
    """Queries SQL para tabela alerts."""

    def create(
        self,
        camera_id: UUID,
        violations: list[dict[str, Any]],
        confidence: float,
        evidence_key: str,
    ) -> dict[str, Any]:
        """Cria alerta de violação."""
        return self._execute_mutation(
            "INSERT INTO alerts (camera_id, violations, confidence, evidence_key) "
            "VALUES (%s, %s::jsonb, %s, %s) RETURNING *",
            (str(camera_id), json.dumps(violations), confidence, evidence_key),
        )  # type: ignore[return-value]

    def get_by_camera(
        self,
        camera_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Lista alertas de uma câmera com paginação."""
        return self._execute(
            "SELECT * FROM alerts WHERE camera_id = %s "
            "ORDER BY timestamp DESC LIMIT %s OFFSET %s",
            (str(camera_id), limit, offset),
        )

    def get_unacknowledged(
        self, camera_id: Optional[UUID] = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Lista alertas não reconhecidos."""
        if camera_id:
            return self._execute(
                "SELECT * FROM alerts "
                "WHERE camera_id = %s AND acknowledged = FALSE "
                "ORDER BY timestamp DESC LIMIT %s",
                (str(camera_id), limit),
            )
        return self._execute(
            "SELECT * FROM alerts WHERE acknowledged = FALSE "
            "ORDER BY timestamp DESC LIMIT %s",
            (limit,),
        )

    def acknowledge(self, alert_id: UUID) -> Optional[dict[str, Any]]:
        """Marca alerta como reconhecido."""
        return self._execute_mutation(
            "UPDATE alerts SET acknowledged = TRUE "
            "WHERE id = %s RETURNING *",
            (str(alert_id),),
        )

    def count_by_camera(self, camera_id: UUID) -> int:
        """Conta alertas de uma câmera."""
        row = self._execute_one(
            "SELECT COUNT(*) AS count FROM alerts WHERE camera_id = %s",
            (str(camera_id),),
        )
        return row["count"] if row else 0

    def list_with_filters(
        self,
        tenant_id: str,
        limit: int = 20,
        offset: int = 0,
        camera_id: str = None,
        start_date=None,
        end_date=None,
        violation_type: str = None,
        acknowledged: bool = None,
    ) -> dict:
        """Lista alertas com filtros e paginação, isolado por tenant (P0-03 fix)."""
        conditions = ["1=1", "a.tenant_id = %s"]
        params: list = [tenant_id]

        if camera_id:
            conditions.append("a.camera_id = %s")
            params.append(camera_id)
        if start_date:
            conditions.append("a.created_at >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("a.created_at <= %s")
            params.append(end_date)
        if violation_type:
            conditions.append("a.violations::text LIKE %s")
            params.append(f'%{violation_type}%')
        if acknowledged is not None:
            conditions.append("a.acknowledged = %s")
            params.append(acknowledged)

        where = " AND ".join(conditions)

        # Count
        count_params = list(params)
        total_row = self._execute_one(
            f"SELECT COUNT(*) as count FROM alerts a WHERE {where}",
            tuple(count_params),
        )
        total = total_row["count"] if total_row else 0

        # Items with camera name join (best-effort — camera table may vary)
        page_params = list(params) + [limit, offset]
        items = self._execute(
            f"""SELECT a.*,
               COALESCE(i.name, 'Unknown') as camera_name
            FROM alerts a
            LEFT JOIN cameras i ON a.camera_id = i.id
            WHERE {where}
            ORDER BY a.created_at DESC
            LIMIT %s OFFSET %s""",
            tuple(page_params),
        )

        return {"items": items, "total": total}

    def list_for_camera_scenario(self, tenant_id: str, camera_id: str) -> list[dict[str, Any]]:
        """Lista regras de alerta aplicáveis a uma câmera: específicas + globais do tenant.

        Retorna regras onde camera_id = camera_id (específica) OU camera_id IS NULL (tenant-wide),
        filtrando por tenant_id e enabled=true (C-01).
        """
        return self._execute(
            """
            SELECT id, tenant_id, camera_id, violation_type,
                   min_duration_seconds, min_occurrences, time_window_seconds,
                   create_alert, enabled, created_at, updated_at
            FROM alert_rules
            WHERE tenant_id = %s
              AND enabled = true
              AND (camera_id = %s OR camera_id IS NULL)
            ORDER BY created_at ASC
            """,
            (tenant_id, camera_id),
        )

    def count_since(self, tenant_id: str, module_code: str, since: datetime) -> int:
        """Conta alertas de um tenant/módulo desde uma data."""
        row = self._execute_one(
            "SELECT COUNT(*) AS count FROM alerts WHERE tenant_id = %s AND module_code = %s AND created_at >= %s",
            (tenant_id, module_code, since),
        )
        return row["count"] if row else 0

    def count_all_since(self, tenant_id: str, since: datetime) -> int:
        """Conta todos alertas do tenant desde uma data (todos os módulos)."""
        row = self._execute_one(
            "SELECT COUNT(*) AS count FROM alerts WHERE tenant_id = %s AND created_at >= %s",
            (tenant_id, since),
        )
        return row["count"] if row else 0

    def count_by_hour(self, tenant_id: str, start: datetime, end: datetime) -> list:
        """Conta alertas por hora do tenant em um intervalo."""
        return self._execute(
            """
            SELECT
                date_trunc('hour', created_at) AS hour,
                COUNT(*) AS count
            FROM alerts
            WHERE tenant_id = %s AND created_at BETWEEN %s AND %s
            GROUP BY date_trunc('hour', created_at)
            ORDER BY hour
            """,
            (tenant_id, start, end),
        )

    @staticmethod
    def _event_filters(
        alias: str,
        tenant_id: str,
        module_code: str | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        min_confidence: float | None = None,
        camera_ids: list[str] | None = None,
        class_names: list[str] | None = None,
    ) -> tuple[str, list[Any]]:
        """Gera WHERE + params para um branch de eventos (alerts ou demo_events).

        `alias` é literal interno ('a'/'d'), nunca input do usuário.
        Todos os VALORES são parametrizados via %s — zero f-string de input.
        """
        conditions: list[str] = [f"{alias}.tenant_id = %s"]
        params: list[Any] = [tenant_id]

        if module_code:
            conditions.append(f"{alias}.module_code = %s")
            params.append(module_code)
        if from_ts:
            conditions.append(f"{alias}.created_at >= %s")
            params.append(from_ts)
        if to_ts:
            conditions.append(f"{alias}.created_at <= %s")
            params.append(to_ts)
        if min_confidence is not None:
            conditions.append(f"{alias}.confidence >= %s")
            params.append(min_confidence)
        if camera_ids:
            placeholders = ",".join(["%s"] * len(camera_ids))
            conditions.append(f"{alias}.camera_id IN ({placeholders})")
            params.extend(camera_ids)
        if class_names:
            # class_name match: violations JSONB array contains objects with "class" key
            # Use text search over JSONB — still parametrized
            class_conditions = []
            for cn in class_names:
                class_conditions.append(f"{alias}.violations::text LIKE %s")
                params.append(f'%"class": "{cn}"%')
            conditions.append(f"({' OR '.join(class_conditions)})")

        return " AND ".join(conditions), params

    def search_events(
        self,
        tenant_id: str,
        limit: int = 20,
        offset: int = 0,
        camera_ids: list[str] | None = None,
        class_names: list[str] | None = None,
        module_code: str | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        min_confidence: float | None = None,
        include_demo: bool = True,
    ) -> dict[str, Any]:
        """Busca investigativa de eventos com filtros combinados e tenant isolation.

        include_demo=True (default) une alerts + demo_events via UNION ALL explícita,
        cada branch com o MESMO where tenant-scoped; eventos demo saem com is_demo=TRUE.
        Todos os parâmetros de lista (camera_ids, class_names) são passados como
        params parametrizados — zero f-string de input do usuário.
        """
        where_a, params_a = self._event_filters(
            "a", tenant_id, module_code, from_ts, to_ts,
            min_confidence, camera_ids, class_names,
        )

        alerts_select = f"""SELECT
                a.id,
                a.camera_id,
                a.tenant_id,
                a.module_code,
                a.violations,
                a.confidence,
                a.evidence_key,
                a.acknowledged,
                a.created_at,
                COALESCE(c.name, 'Câmera') AS camera_name,
                FALSE AS is_demo
            FROM alerts a
            LEFT JOIN cameras c ON a.camera_id = c.id AND c.tenant_id = a.tenant_id
            WHERE {where_a}"""

        if include_demo:
            where_d, params_d = self._event_filters(
                "d", tenant_id, module_code, from_ts, to_ts,
                min_confidence, camera_ids, class_names,
            )
            demo_select = f"""SELECT
                d.id,
                d.camera_id,
                d.tenant_id,
                d.module_code,
                d.violations,
                d.confidence,
                d.evidence_key,
                d.acknowledged,
                d.created_at,
                d.camera_label AS camera_name,
                TRUE AS is_demo
            FROM demo_events d
            WHERE {where_d}"""

            count_row = self._execute_one(
                f"SELECT ((SELECT COUNT(*) FROM alerts a WHERE {where_a}) "
                f"+ (SELECT COUNT(*) FROM demo_events d WHERE {where_d})) AS count",
                tuple(params_a + params_d),
            )
            total = count_row["count"] if count_row else 0

            items = self._execute(
                f"""SELECT * FROM (
                {alerts_select}
                UNION ALL
                {demo_select}
                ) ev
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s""",
                tuple(params_a + params_d + [limit, offset]),
            )
            return {"items": items, "total": total}

        count_row = self._execute_one(
            f"SELECT COUNT(*) AS count FROM alerts a WHERE {where_a}",
            tuple(params_a),
        )
        total = count_row["count"] if count_row else 0

        items = self._execute(
            f"""{alerts_select}
            ORDER BY a.created_at DESC
            LIMIT %s OFFSET %s""",
            tuple(params_a + [limit, offset]),
        )

        return {"items": items, "total": total}

    def timeline_by_bucket(
        self,
        tenant_id: str,
        from_ts: datetime,
        to_ts: datetime,
        bucket: str = "hour",
        camera_ids: list[str] | None = None,
        class_names: list[str] | None = None,
        module_code: str | None = None,
        include_demo: bool = True,
    ) -> list[dict[str, Any]]:
        """Agrega contagem de eventos por bucket de tempo (sem N+1).

        bucket: 'hour' | 'day' | 'week' — passado como literal validado, não f-string de input.
        include_demo=True (default) agrega alerts + demo_events via UNION ALL explícita,
        cada branch com o MESMO where tenant-scoped.
        """
        # Validate bucket to prevent SQL injection (only accepted literals)
        valid_buckets = {"hour", "day", "week", "minute"}
        safe_bucket = bucket if bucket in valid_buckets else "hour"

        where_a, params_a = self._event_filters(
            "a", tenant_id, module_code, from_ts, to_ts,
            None, camera_ids, class_names,
        )

        if include_demo:
            where_d, params_d = self._event_filters(
                "d", tenant_id, module_code, from_ts, to_ts,
                None, camera_ids, class_names,
            )
            return self._execute(
                f"""SELECT
                    date_trunc('{safe_bucket}', ev.created_at) AS bucket,
                    COUNT(*) AS count
                FROM (
                    SELECT a.created_at FROM alerts a WHERE {where_a}
                    UNION ALL
                    SELECT d.created_at FROM demo_events d WHERE {where_d}
                ) ev
                GROUP BY date_trunc('{safe_bucket}', ev.created_at)
                ORDER BY bucket""",
                tuple(params_a + params_d),
            )

        return self._execute(
            f"""SELECT
                date_trunc('{safe_bucket}', a.created_at) AS bucket,
                COUNT(*) AS count
            FROM alerts a
            WHERE {where_a}
            GROUP BY date_trunc('{safe_bucket}', a.created_at)
            ORDER BY bucket""",
            tuple(params_a),
        )
