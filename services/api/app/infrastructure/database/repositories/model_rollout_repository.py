"""
Model Rollout Repository — manifesto de modelo ativo e operação de pin.

Tabelas:
  {tenant_schema}.models  — modelos por tenant (module, version, r2_key, active, metrics JSONB)
  public.model_activation_log — auditoria de ativações (model_id, activated_by, activated_at)

Todas as referências de schema usam psycopg2.sql.Identifier (proteção contra SQL injection).
"""
import json
import logging
from typing import Any

from psycopg2 import sql as _sql

from app.infrastructure.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

_COLS = (
    "id, name, module, version, r2_key, hub_model_id, metrics, active, created_at"
)


def _to_manifest(row: dict[str, Any]) -> dict[str, Any]:
    """Converte row de {schema}.models para o formato de manifesto público."""
    metrics = row.get("metrics") or {}
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except Exception:
            metrics = {}
    created = row.get("created_at")
    return {
        "id": str(row["id"]),
        "module": row["module"],
        "name": row["name"],
        "version": row.get("version"),
        "checksum": row.get("r2_key"),
        "git_sha": metrics.get("git_sha"),
        "canary": bool(metrics.get("canary", False)),
        "active": bool(row.get("active", False)),
        "created_at": created.isoformat() if created else None,
    }


class ModelRolloutRepository(BaseRepository):
    """Repositório para manifesto e pin de modelos por tenant×módulo."""

    def get_active_model(self, schema: str, module: str) -> dict[str, Any] | None:
        """Retorna o manifesto do modelo ativo para tenant_schema + módulo."""
        query = _sql.SQL(
            "SELECT " + _COLS + " FROM {}.models "
            "WHERE module = %s AND active = TRUE "
            "ORDER BY created_at DESC LIMIT 1"
        ).format(_sql.Identifier(schema))
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (module,))
            row = cur.fetchone()
            return _to_manifest(dict(row)) if row else None

    def get_model_by_id(self, schema: str, model_id: str) -> dict[str, Any] | None:
        """Retorna row bruto do modelo por ID no schema do tenant. None → não existe."""
        query = _sql.SQL(
            "SELECT " + _COLS + " FROM {}.models WHERE id = %s"
        ).format(_sql.Identifier(schema))
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (model_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def mark_canary(self, schema: str, model_id: str) -> dict[str, Any] | None:
        """Marca modelo como canário sem ativá-lo (active permanece inalterado)."""
        query = _sql.SQL(
            "UPDATE {}.models "
            "SET metrics = COALESCE(metrics, %s::jsonb) || %s::jsonb "
            "WHERE id = %s "
            "RETURNING " + _COLS
        ).format(_sql.Identifier(schema))
        with self._db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, ("{}", json.dumps({"canary": True}), model_id))
            row = cur.fetchone()
            return _to_manifest(dict(row)) if row else None

    def pin_model(
        self, schema: str, model_id: str, module: str
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Ativa atomicamente o modelo para o módulo, desativando o anterior.

        Returns:
            (new_manifest, previous_manifest) — previous é None se não havia ativo.
        """

        def _txn(conn, cur):
            # Modelo atualmente ativo (para audit log)
            cur.execute(
                _sql.SQL(
                    "SELECT " + _COLS + " FROM {}.models "
                    "WHERE module = %s AND active = TRUE LIMIT 1"
                ).format(_sql.Identifier(schema)),
                (module,),
            )
            prev_row = cur.fetchone()
            previous = _to_manifest(dict(prev_row)) if prev_row else None

            # Desativa todos do módulo
            cur.execute(
                _sql.SQL(
                    "UPDATE {}.models SET active = FALSE WHERE module = %s"
                ).format(_sql.Identifier(schema)),
                (module,),
            )

            # Ativa o alvo e remove flag canary dos metrics
            cur.execute(
                _sql.SQL(
                    "UPDATE {}.models "
                    "SET active = TRUE, "
                    "    metrics = (COALESCE(metrics, %s::jsonb)) - 'canary' "
                    "WHERE id = %s "
                    "RETURNING " + _COLS
                ).format(_sql.Identifier(schema)),
                ("{}", model_id),
            )
            new_row = cur.fetchone()
            new_manifest = _to_manifest(dict(new_row)) if new_row else None
            return new_manifest, previous

        return self._execute_in_transaction(_txn)

    def record_activation_log(
        self,
        model_id: str,
        activated_by: str,
        previous_model_id: str | None,
    ) -> None:
        """Insere entrada de auditoria em public.model_activation_log."""
        self._execute_mutation_no_return(
            "INSERT INTO public.model_activation_log "
            "(model_id, activated_by, previous_model_id) "
            "VALUES (%s, %s, %s)",
            (model_id, activated_by, previous_model_id),
        )

    def get_last_activation_log(self, model_id: str) -> dict[str, Any] | None:
        """Retorna o registro mais recente de ativação para um modelo."""
        return self._execute_one(
            "SELECT id, model_id, activated_by, activated_at, previous_model_id "
            "FROM public.model_activation_log "
            "WHERE model_id = %s "
            "ORDER BY activated_at DESC LIMIT 1",
            (model_id,),
        )
