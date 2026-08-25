"""Repository: Alerts."""
import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class AlertRepository(BaseRepository):
    """Queries SQL para tabela alerts."""

    # Única unidade de bbox que o domínio grava (domain/detectors/base.py).
    BBOX_PIXELS = "pixels_xywh_frame_original"

    # ── Polaridade do evento (ADR-0063) ───────────────────────────────────
    #
    # CONFORMIDADE = o alerta tem ≥1 entrada E TODA classe está explicitamente
    # marcada como PRESENÇA. Tudo o mais é VIOLAÇÃO:
    #   · classe fora do catálogo (o modelo emitiu, ninguém cadastrou);
    #   · entrada sem chave `class` — os alertas `camera_gap` do liveness
    #     ({"type": "camera_gap", ...}) caem aqui e PRECISAM continuar
    #     visíveis;
    #   · is_violation NULL (ninguém decidiu ainda).
    # Sumir da tela é o erro caro; aparecer a mais é barato (ADR-0017).
    #
    # O `%s` é UMA lista de nomes (presence_class_names) — parametrizada,
    # zero f-string de input do usuário. Alias `a` é literal interno.
    _IS_COMPLIANCE_SQL = """(
        jsonb_array_length(a.violations) > 0
        AND NOT EXISTS (
            SELECT 1 FROM jsonb_array_elements(a.violations) v
             WHERE COALESCE(lower(v->>'class'), '') <> ALL(%s::text[])
        )
    )"""

    def presence_class_names(
        self, tenant_id: str, module_code: str | None = None
    ) -> list[str]:
        """Nomes (lower) das classes explicitamente de PRESENÇA do tenant.

        Catálogo global (module_classes, sem tenant_id) ∪ classes custom do
        tenant (yolo_classes). Lista vazia ⇒ nada é conformidade — o lado
        seguro: na dúvida o evento aparece.

        `module_code` ESCOPA o conjunto. Sem ele, o catálogo global devolvia
        junto as classes de `fueling` (truck, plate, pallet… todas
        `is_violation = false`, migration 009): num agregado de EPI, um alerta
        de 'truck' era lido como CONFORMIDADE de EPI. Ambas as tabelas têm
        `module_code` (009 e 093 — NOT NULL DEFAULT 'epi'), então o filtro é
        uma igualdade simples. Omitido = todos os módulos (comportamento
        anterior, mantido para quem não sabe o módulo, como `list_with_filters`).
        """
        filtro = " AND module_code = %s" if module_code else ""
        # O %s do módulo aparece DUAS vezes no texto (um por lado do UNION) e o
        # primeiro vem antes do tenant_id — a ordem dos params segue o texto.
        params: tuple[Any, ...] = (
            (module_code, str(tenant_id), module_code)
            if module_code
            else (str(tenant_id),)
        )
        rows = self._execute(
            "SELECT lower(class_name) AS n FROM module_classes "  # noqa: S608
            f" WHERE is_violation IS FALSE{filtro} "
            "UNION "
            "SELECT lower(name) AS n FROM yolo_classes "
            f" WHERE tenant_id = %s AND is_violation IS FALSE{filtro}",
            params,
        )
        return [r["n"] for r in rows]

    def create(
        self,
        camera_id: UUID,
        violations: list[dict[str, Any]],
        confidence: float,
        evidence_key: str,
        tenant_id: Optional[str] = None,
        module_code: Optional[str] = None,
    ) -> dict[str, Any]:
        """Cria alerta de violação.

        tenant_id/module_code são opcionais (retrocompat — ajuste #8): quando
        fornecidos pelo caller (derivados da câmera), o alerta nasce
        tenant-scoped; omitidos, as colunas usam os defaults do schema.
        """
        columns = ["camera_id", "violations", "confidence", "evidence_key"]
        placeholders = ["%s", "%s::jsonb", "%s", "%s"]
        values: list[Any] = [str(camera_id), json.dumps(violations), confidence, evidence_key]

        if tenant_id is not None:
            columns.append("tenant_id")
            placeholders.append("%s")
            values.append(str(tenant_id))
        if module_code is not None:
            columns.append("module_code")
            placeholders.append("%s")
            values.append(module_code)

        return self._execute_mutation(
            f"INSERT INTO alerts ({', '.join(columns)}) "  # noqa: S608
            f"VALUES ({', '.join(placeholders)}) RETURNING *",
            tuple(values),
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
        self,
        camera_id: Optional[UUID] = None,
        limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Lista alertas não reconhecidos, filtrados por tenant_id."""
        if camera_id:
            return self._execute(
                "SELECT * FROM alerts "
                "WHERE camera_id = %s AND acknowledged = FALSE AND tenant_id = %s "
                "ORDER BY timestamp DESC LIMIT %s",
                (str(camera_id), str(tenant_id), limit),
            )
        return self._execute(
            "SELECT * FROM alerts WHERE acknowledged = FALSE AND tenant_id = %s "
            "ORDER BY timestamp DESC LIMIT %s",
            (str(tenant_id), limit),
        )

    def get_evidence_key(self, alert_id: UUID, tenant_id: str) -> Optional[dict[str, Any]]:
        """Busca evidence_key de um alerta, escopado por tenant (task-074 / C-01).

        Retorna None tanto quando o alerta não existe quanto quando pertence a
        outro tenant — o endpoint de snapshot deve responder 404 nos dois
        casos, sem diferenciar (evita enumeração de alert_id de outros
        tenants via diferença de status code).
        """
        return self._execute_one(
            "SELECT evidence_key FROM alerts WHERE id = %s AND tenant_id = %s",
            (str(alert_id), str(tenant_id)),
        )

    def get_by_id(self, alert_id: UUID, tenant_id: str) -> Optional[dict[str, Any]]:
        """Um alerta por id, escopado por tenant (C-01), com o nome da câmera.

        Retorna None tanto para alerta inexistente quanto para alerta de OUTRO
        tenant — a rota responde o mesmo 404 nos dois casos, sem vazar
        existência (mesma regra do `get_evidence_key`).

        Usa o MESMO LEFT JOIN de `list_with_filters` (`cameras` sem qualificar
        schema, resolvido pelo search_path) e seleciona só `name`: a variante
        `{tenant_schema}.cameras` (migration 024) não tem coluna `channel`.
        """
        return self._execute_one(
            "SELECT a.*, COALESCE(c.name, 'Unknown') AS camera_name "
            "FROM alerts a LEFT JOIN cameras c ON a.camera_id = c.id "
            "WHERE a.id = %s AND a.tenant_id = %s",
            (str(alert_id), str(tenant_id)),
        )

    def acknowledge(self, alert_id: UUID, tenant_id: str) -> Optional[dict[str, Any]]:
        """Marca alerta como reconhecido, dentro do tenant de quem pediu.

        `tenant_id` é obrigatório de propósito: sem ele o UPDATE casava por id
        puro e qualquer sessão autenticada reconhecia alerta de OUTRO tenant
        (escrita cross-tenant, C-01). Fora do tenant o rowcount é 0 e o
        chamador devolve 404 — não 403, que confirmaria a existência.
        """
        return self._execute_mutation(
            "UPDATE alerts SET acknowledged = TRUE "
            "WHERE id = %s AND tenant_id = %s RETURNING *",
            (str(alert_id), str(tenant_id)),
        )

    def corrigir_bboxes(
        self,
        alert_id: UUID,
        tenant_id: str,
        correcoes: list[dict[str, Any]],
        por: str,
    ) -> Optional[dict[str, Any]]:
        """Reposiciona caixa(s) de um alerta preservando o valor anterior.

        Read-modify-write dentro de UMA transação com FOR UPDATE: duas
        correções simultâneas no mesmo alerta não se sobrescrevem em silêncio.

        Só o `bbox` do cliente é aplicado — `class`, `confidence`, `tipo`,
        `modo` e `ancora_pessoa` ficam como estão: corrigir POSIÇÃO não vira
        porta para reescrever CLASSE. `bbox_unidade` é carimbado pelo servidor
        (caixa gravada em outra unidade é caixa mentirosa na tela).

        None = alerta inexistente OU de outro tenant → a rota devolve o MESMO
        404 (C-01, sem vazar existência). IndexError → 400 na rota.
        """
        def _tx(conn, cur):  # type: ignore[no-untyped-def]
            cur.execute(
                "SELECT violations FROM alerts WHERE id = %s AND tenant_id = %s FOR UPDATE",
                (str(alert_id), str(tenant_id)),
            )
            row = cur.fetchone()
            if row is None:
                return None
            atuais = [dict(v) for v in (row["violations"] or [])]
            for c in correcoes:
                i = c["index"]
                if i >= len(atuais):
                    raise IndexError(i)
                atuais[i]["bbox"] = c["bbox"]
                atuais[i]["bbox_unidade"] = self.BBOX_PIXELS
                atuais[i]["bbox_corrigida"] = True
            cur.execute(
                # `violations` do lado DIREITO é o valor ANTERIOR (Postgres
                # avalia todos os SET contra a linha pré-update) — o histórico
                # sai de graça, sem segundo roundtrip e sem janela entre ler e
                # gravar. Append-only: `||` empurra no fim, nada é removido.
                "UPDATE alerts SET violations = %s::jsonb, "
                "violations_historico = violations_historico || jsonb_build_object("
                "'em', to_jsonb(NOW()), 'por', %s::text, 'tipo', 'bbox', "
                "'violations_anteriores', violations) "
                "WHERE id = %s AND tenant_id = %s "
                "RETURNING violations, violations_historico",
                (json.dumps(atuais), por, str(alert_id), str(tenant_id)),
            )
            return dict(cur.fetchone())

        return self._execute_in_transaction(_tx)

    def count_by_camera(self, camera_id: UUID, tenant_id: Optional[str] = None) -> int:
        """Conta alertas de uma câmera, filtrados por tenant_id."""
        row = self._execute_one(
            "SELECT COUNT(*) AS count FROM alerts WHERE camera_id = %s AND tenant_id = %s",
            (str(camera_id), str(tenant_id)),
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
        kind: str = None,
    ) -> dict:
        """Lista alertas com filtros e paginação, isolado por tenant (P0-03 fix).

        `kind` (ADR-0063): 'violation' | 'compliance' | None (= todos, default
        do backend — nenhum consumidor existente muda de comportamento). Cada
        item sai com a coluna derivada `event_kind`, calculada pelo MESMO
        predicado usado no filtro.
        """
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

        # ADR-0063 — filtro e coluna derivada usam o MESMO predicado, para o
        # `event_kind` mostrado nunca discordar do recorte paginado.
        presence_names = self.presence_class_names(tenant_id)
        if kind == "compliance":
            conditions.append(self._IS_COMPLIANCE_SQL)
            params.append(presence_names)
        elif kind == "violation":
            conditions.append(f"NOT {self._IS_COMPLIANCE_SQL}")
            params.append(presence_names)

        where = " AND ".join(conditions)

        # Count
        count_params = list(params)
        total_row = self._execute_one(
            f"SELECT COUNT(*) as count FROM alerts a WHERE {where}",
            tuple(count_params),
        )
        total = total_row["count"] if total_row else 0

        # Items with camera name join (best-effort — camera table may vary).
        # O %s do CASE aparece no SELECT, ANTES do WHERE, no texto da query ⇒
        # `presence_names` tem de ser o PRIMEIRO param aqui (e NÃO entra no
        # COUNT acima quando `kind` é None).
        page_params = [presence_names] + list(params) + [limit, offset]
        items = self._execute(
            f"""SELECT a.*,
               COALESCE(i.name, 'Unknown') as camera_name,
               CASE WHEN {self._IS_COMPLIANCE_SQL}
                    THEN 'compliance' ELSE 'violation' END AS event_kind
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

    def _window_conditions(
        self,
        tenant_id: str,
        from_ts: datetime,
        to_ts: datetime,
        module_code: str | None = None,
        camera_ids: list[str] | None = None,
    ) -> tuple[list[str], list[Any]]:
        """Condições comuns de janela temporal — só literais fixos no SQL, valores via %s."""
        conditions: list[str] = [
            "a.tenant_id = %s",
            "a.created_at >= %s",
            "a.created_at <= %s",
        ]
        params: list[Any] = [str(tenant_id), from_ts, to_ts]
        if module_code:
            conditions.append("a.module_code = %s")
            params.append(module_code)
        if camera_ids:
            placeholders = ",".join(["%s"] * len(camera_ids))
            conditions.append(f"a.camera_id IN ({placeholders})")
            params.extend(camera_ids)
        return conditions, params

    def count_in_window(
        self,
        tenant_id: str,
        from_ts: datetime,
        to_ts: datetime,
        module_code: str | None = None,
        camera_ids: list[str] | None = None,
    ) -> int:
        """Conta alertas do tenant em uma janela temporal (com filtros opcionais)."""
        conditions, params = self._window_conditions(
            tenant_id, from_ts, to_ts, module_code, camera_ids
        )
        where = " AND ".join(conditions)
        row = self._execute_one(
            f"SELECT COUNT(*) AS count FROM alerts a WHERE {where}",
            tuple(params),
        )
        return row["count"] if row else 0

    def distinct_cameras_in_window(
        self, tenant_id: str, from_ts: datetime, to_ts: datetime
    ) -> list[str]:
        """Câmeras com >=1 alerta na janela (drift monitor, WS-C3 — escopa o
        trabalho só a câmeras que de fato produziram alerta no período)."""
        rows = self._execute(
            "SELECT DISTINCT camera_id FROM alerts "
            "WHERE tenant_id = %s AND created_at >= %s AND created_at < %s",
            (str(tenant_id), from_ts, to_ts),
        )
        return [str(row["camera_id"]) for row in rows]

    def avg_confidence_in_window(
        self,
        tenant_id: str,
        from_ts: datetime,
        to_ts: datetime,
        module_code: str | None = None,
        camera_ids: list[str] | None = None,
    ) -> float:
        """Confiança média dos alertas do tenant numa janela (drift monitor, WS-C3)."""
        conditions, params = self._window_conditions(
            tenant_id, from_ts, to_ts, module_code, camera_ids
        )
        where = " AND ".join(conditions)
        row = self._execute_one(
            f"SELECT AVG(a.confidence) AS avg_confidence FROM alerts a WHERE {where}",  # noqa: S608
            tuple(params),
        )
        value = row["avg_confidence"] if row else None
        return float(value) if value is not None else 0.0

    def violations_by_class(
        self,
        tenant_id: str,
        from_ts: datetime,
        to_ts: datetime,
        module_code: str | None = None,
        camera_ids: list[str] | None = None,
        class_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Distribuição de VIOLAÇÕES por classe no período (server-side).

        ADR-0063: contava toda classe detectada, então "Protetor auditivo"
        (presença) aparecia como linha de violação no `by_class` de
        `/events/summary` e na distribuição do drift monitor — o MESMO defeito
        de polaridade já corrigido em `violation_hours_by_class`. Classe de
        presença não forma grupo aqui.
        """
        conditions, params = self._window_conditions(
            tenant_id, from_ts, to_ts, module_code, camera_ids
        )
        conditions.append("v->>'class' IS NOT NULL")
        conditions.append("lower(v->>'class') <> ALL(%s::text[])")
        params.append(self.presence_class_names(tenant_id, module_code))
        if class_names:
            conditions.append("v->>'class' = ANY(%s)")
            params.append(list(class_names))
        where = " AND ".join(conditions)
        return self._execute(
            f"""SELECT v->>'class' AS class, COUNT(*) AS count
            FROM alerts a, jsonb_array_elements(a.violations) v
            WHERE {where}
            GROUP BY v->>'class'
            ORDER BY count DESC""",
            tuple(params),
        )

    def top_cameras_by_alerts(
        self,
        tenant_id: str,
        from_ts: datetime,
        to_ts: datetime,
        module_code: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Top câmeras por volume de alertas no período (tenant-scoped)."""
        conditions, params = self._window_conditions(tenant_id, from_ts, to_ts, module_code)
        where = " AND ".join(conditions)
        params.append(limit)
        return self._execute(
            f"""SELECT
                a.camera_id,
                COALESCE(c.name, 'Câmera') AS camera_name,
                COUNT(*) AS count
            FROM alerts a
            LEFT JOIN cameras c ON a.camera_id = c.id AND c.tenant_id = a.tenant_id
            WHERE {where}
            GROUP BY a.camera_id, c.name
            ORDER BY count DESC
            LIMIT %s""",
            tuple(params),
        )

    def camera_hours_with_violation(
        self, tenant_id: str, module_code: str, since: datetime
    ) -> int:
        """Horas-câmera com ≥1 violação desde `since`.

        ADR-0063: contava TODO alerta, inclusive EPI PRESENTE — o que invertia
        o `compliance_rate` que se apoia neste número (quanto mais gente usava
        EPI, menor a "conformidade"). Agora só conta hora-câmera com ≥1 evento
        que NÃO é conformidade.
        """
        row = self._execute_one(
            f"""
            SELECT COUNT(DISTINCT (a.camera_id, date_trunc('hour', a.created_at))) AS count
            FROM alerts a
            WHERE a.tenant_id = %s AND a.module_code = %s AND a.created_at >= %s
              AND NOT {self._IS_COMPLIANCE_SQL}
            """,  # noqa: S608 — só literais internos; valores via %s
            (
                str(tenant_id),
                module_code,
                since,
                self.presence_class_names(tenant_id, module_code),
            ),
        )
        return row["count"] if row else 0

    def violation_hours_by_class(
        self, tenant_id: str, module_code: str, since: datetime
    ) -> list[dict[str, Any]]:
        """Horas-câmera com violação por classe desde `since`.

        ADR-0063: agrupava por TODA classe detectada, então "Protetor
        auditivo" (presença) virava uma linha de "violação por classe" no
        `compliance_by_class`. Classes de presença agora não formam grupo.
        """
        return self._execute(
            """
            SELECT
                v->>'class' AS class,
                COUNT(DISTINCT (a.camera_id, date_trunc('hour', a.created_at))) AS hours
            FROM alerts a, jsonb_array_elements(a.violations) v
            WHERE a.tenant_id = %s AND a.module_code = %s AND a.created_at >= %s
              AND v->>'class' IS NOT NULL
              AND lower(v->>'class') <> ALL(%s::text[])
            GROUP BY v->>'class'
            ORDER BY hours DESC
            """,
            (
                str(tenant_id),
                module_code,
                since,
                self.presence_class_names(tenant_id, module_code),
            ),
        )

    def usage_rate_by_area(
        self,
        tenant_id: str,
        from_ts: datetime,
        to_ts: datetime,
        module_code: str | None = None,
    ) -> list[dict[str, Any]]:
        """Conformidades × violações por ÁREA (ADR-0063) — painel de taxa de uso.

        Área = `cameras.location`; sem location, o nome da câmera. Não existe
        tabela de áreas — a câmera é a proxy de hoje, e inventar uma seria
        escopo de outra decisão. A DIVISÃO fica na tela: aqui só saem
        contagens, para o painel mostrar "3 de 4" junto do percentual sem uma
        segunda chamada.
        """
        presence_names = self.presence_class_names(tenant_id, module_code)
        conditions = ["a.tenant_id = %s", "a.created_at >= %s", "a.created_at <= %s"]
        # Os dois %s do predicado aparecem no SELECT, antes do WHERE.
        params: list[Any] = [presence_names, presence_names, str(tenant_id), from_ts, to_ts]
        if module_code:
            conditions.append("a.module_code = %s")
            params.append(module_code)
        where = " AND ".join(conditions)
        return self._execute(
            f"""SELECT
                COALESCE(NULLIF(c.location, ''), c.name, 'Sem área') AS area,
                COUNT(*) FILTER (WHERE {self._IS_COMPLIANCE_SQL})     AS compliance,
                COUNT(*) FILTER (WHERE NOT {self._IS_COMPLIANCE_SQL}) AS violation
            FROM alerts a
            LEFT JOIN cameras c ON a.camera_id = c.id AND c.tenant_id = a.tenant_id
            WHERE {where}
            GROUP BY 1
            ORDER BY 1""",  # noqa: S608 — só literais internos; valores via %s
            tuple(params),
        )
