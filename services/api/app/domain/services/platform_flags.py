"""
DOMAIN platform_flags.py — Leitura de feature flags globais da plataforma.

Layer: domain
Pattern: Helper function (framework-agnostic)

Key exports:
  - platform_flag_enabled(key) -> bool:
      Lê public.platform_feature_flags (migration 029). Fail-open: qualquer
      erro de leitura (pool indisponível, tabela ausente) retorna False com
      logger.warning — flags de enforcement nunca derrubam o fluxo normal.

Flags conhecidas:
  - enforce_plan_limits (seed 087, default false): aplica limites do plano
    (módulos e câmeras) em runtime.

Related: app/api/v1/admin/routes.py (GET/PATCH /v1/admin/feature-flags),
         app/domain/services/module_service.py,
         app/api/v1/cameras/crud_handlers.py
"""
import logging

from app.infrastructure.database.connection import DatabasePool

logger = logging.getLogger(__name__)


def platform_flag_enabled(key: str) -> bool:
    """Retorna True se a feature flag global `key` está ligada."""
    try:
        pool = DatabasePool.get_instance()
        if pool is None:
            return False
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT flag_value FROM public.platform_feature_flags WHERE flag_key = %s",
                (key,),
            )
            row = cur.fetchone()
            return bool(row["flag_value"]) if row else False
    except Exception as exc:
        logger.warning("platform_flag_read_error: key=%s err=%s", key, exc)
        return False
