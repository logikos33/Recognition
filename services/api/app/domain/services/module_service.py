"""
Recognition — Module Service.

Gerencia módulos por tenant: listing, stats e verificação de acesso.
"""
import logging
from datetime import UTC, datetime, timedelta

from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.alert_repository import AlertRepository
from app.infrastructure.database.repositories.camera_repository import CameraRepository
from app.infrastructure.database.repositories.module_repository import ModuleRepository
from app.infrastructure.database.repositories.training_repository import TrainingRepository

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


def _get_training_repo() -> TrainingRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return TrainingRepository(pool)


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

    def get_module(self, tenant_id: str, module_code: str) -> dict | None:
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
        """Estatísticas do módulo para o tenant. Cada contagem é isolada — falha individual retorna 0/None.

        Além das 4 chaves originais (mantidas — aditivo), retorna os KPIs de BI (WS3):
          - alerts_last_hour / alerts_prev_hour: alertas na hora corrente vs hora anterior
          - active_model_name / active_model_map50: modelo is_active do tenant (None se ausente)
          - compliance_rate: proxy honesto — 100*(1 - horas-câmera-com-violação /
            (cameras_active*24)) nas últimas 24h. None quando não há câmera ativa.
            Não existe tabela de detecções positivas — o denominador real é aproximado
            por horas-câmera monitoradas (fórmula exposta em tooltip na UI).
          - compliance_by_class: mesmo cálculo por classe de violação.
        """
        now = datetime.now(tz=UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)
        hour_ago = now - timedelta(hours=1)
        two_hours_ago = now - timedelta(hours=2)
        day_ago = now - timedelta(hours=24)

        camera_repo = _get_camera_repo()
        alert_repo = _get_alert_repo()
        training_repo = _get_training_repo()

        def _safe(fn, *args, default=0):  # type: ignore[no-untyped-def]
            try:
                return fn(*args)
            except Exception as exc:
                logger.warning("stats_count_safe: fn=%s err=%s", fn.__name__, exc)
                return default

        stats = {
            "cameras_active": _safe(camera_repo.count_by_status, tenant_id, module_code, "active"),
            "cameras_total": _safe(camera_repo.count_by_module, tenant_id, module_code),
            "alerts_today": _safe(alert_repo.count_since, tenant_id, module_code, today_start),
            "alerts_week": _safe(alert_repo.count_since, tenant_id, module_code, week_start),
            "alerts_last_hour": _safe(
                alert_repo.count_in_window, tenant_id, hour_ago, now, module_code
            ),
            "alerts_prev_hour": _safe(
                alert_repo.count_in_window, tenant_id, two_hours_ago, hour_ago, module_code
            ),
        }

        model = _safe(training_repo.get_active_for_tenant, tenant_id, default=None)
        stats["active_model_name"] = model.get("name") if model else None
        stats["active_model_map50"] = model.get("map50") if model else None

        cameras_active = stats["cameras_active"] or 0
        if cameras_active > 0:
            total_camera_hours = cameras_active * 24
            violation_hours = _safe(
                alert_repo.camera_hours_with_violation, tenant_id, module_code, day_ago
            ) or 0
            rate = 100.0 * (1 - min(violation_hours, total_camera_hours) / total_camera_hours)
            stats["compliance_rate"] = round(rate, 1)

            by_class_rows = _safe(
                alert_repo.violation_hours_by_class, tenant_id, module_code, day_ago,
                default=[],
            ) or []
            compliance_by_class: dict[str, float] = {}
            for row in by_class_rows:
                cls = row.get("class")
                hours = row.get("hours") or 0
                if not cls:
                    continue
                pct = 100.0 * (1 - min(hours, total_camera_hours) / total_camera_hours)
                compliance_by_class[cls] = round(pct, 1)
            stats["compliance_by_class"] = compliance_by_class
        else:
            stats["compliance_rate"] = None
            stats["compliance_by_class"] = {}

        return stats

    def toggle_class(self, class_id: str, is_active: bool) -> dict:
        """Ativa ou desativa uma classe do módulo."""
        from app.core.exceptions import NotFoundError  # noqa: PLC0415
        result = _get_module_repo().toggle_class_active(class_id, is_active)
        if not result:
            raise NotFoundError("Classe", class_id)
        return result


module_service = ModuleService()
