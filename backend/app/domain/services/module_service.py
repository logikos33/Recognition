"""
EPI Monitor V2 — Module Service.

Gerencia módulos por tenant: listing, stats e verificação de acesso.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.module_repository import ModuleRepository
from app.infrastructure.database.repositories.camera_repository import CameraRepository
from app.infrastructure.database.repositories.alert_repository import AlertRepository

logger = logging.getLogger(__name__)


def _get_module_repo() -> ModuleRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return ModuleRepository(pool)


def _get_camera_repo() -> CameraRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return CameraRepository(pool)


def _get_alert_repo() -> AlertRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return AlertRepository(pool)


class ModuleService:
    """Lógica de negócio para módulos multi-tenant."""

    def list_tenant_modules(self, tenant_id: str) -> list:
        """Lista módulos do tenant com stats básicas."""
        modules = _get_module_repo().get_by_tenant(tenant_id)
        result = []
        for mod in modules:
            try:
                stats = self.get_stats(tenant_id, mod["module_code"])
            except Exception as exc:
                logger.warning("module_stats_error: module=%s err=%s", mod["module_code"], exc)
                stats = {}
            result.append({
                **mod,
                "cameras_count": stats.get("cameras_active", 0),
                "alerts_today": stats.get("alerts_today", 0),
            })
        return result

    def get_module(self, tenant_id: str, module_code: str) -> Optional[dict]:
        """Retorna módulo específico do tenant."""
        return _get_module_repo().get_tenant_module(tenant_id, module_code)

    def tenant_has_module(self, tenant_id: str, module_code: str) -> bool:
        """Verifica se tenant tem acesso ao módulo."""
        module = _get_module_repo().get_tenant_module(tenant_id, module_code)
        return module is not None and bool(module.get("enabled"))

    def get_classes(self, module_code: str) -> list:
        """Lista classes YOLO do módulo."""
        return _get_module_repo().get_classes(module_code)

    def get_stats(self, tenant_id: str, module_code: str) -> dict:
        """Estatísticas do módulo para o tenant."""
        now = datetime.now(tz=timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        camera_repo = _get_camera_repo()
        alert_repo = _get_alert_repo()

        return {
            "cameras_active": camera_repo.count_by_status(tenant_id, module_code, "active"),
            "cameras_total": camera_repo.count_by_module(tenant_id, module_code),
            "alerts_today": alert_repo.count_since(tenant_id, module_code, today_start),
            "alerts_week": alert_repo.count_since(tenant_id, module_code, week_start),
        }


module_service = ModuleService()
