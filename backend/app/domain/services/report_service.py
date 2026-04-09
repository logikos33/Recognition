"""
EPI Monitor V2 — Report Service.

Reports globais para a home page do app.
"""
import logging
from datetime import datetime, timedelta, timezone

from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.alert_repository import AlertRepository
from app.infrastructure.database.repositories.camera_repository import CameraRepository

logger = logging.getLogger(__name__)


def _get_alert_repo() -> AlertRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return AlertRepository(pool)


def _get_camera_repo() -> CameraRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return CameraRepository(pool)


class ReportService:
    """Gera reports agregados para a home page."""

    def get_home_reports(self, tenant_id: str) -> dict:
        """Reports globais para home page (todos os módulos)."""
        now = datetime.now(tz=timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        alert_repo = _get_alert_repo()
        camera_repo = _get_camera_repo()

        alerts_today = alert_repo.count_all_since(tenant_id, today_start)
        alerts_week = alert_repo.count_all_since(tenant_id, week_start)
        cameras_active = camera_repo.count_active_all(tenant_id)
        cameras_total = camera_repo.count_all(tenant_id)

        # Estimativa: câmeras ativas * 8h * 3600 frames/h processados
        hours_active = 8
        processings_today = cameras_active * 3600 * hours_active
        objects_identified = processings_today * 3  # média 3 objetos/frame

        # Gráfico: alertas por hora nas últimas 24h
        alerts_by_hour_raw = alert_repo.count_by_hour(
            tenant_id,
            now - timedelta(hours=24),
            now,
        )
        alerts_by_hour = [
            {"hour": str(row["hour"]), "count": row["count"]}
            for row in alerts_by_hour_raw
        ]

        return {
            "cards": {
                "alerts_today": alerts_today,
                "alerts_week": alerts_week,
                "cameras_active": cameras_active,
                "cameras_total": cameras_total,
                "processings_today": processings_today,
                "objects_identified": objects_identified,
            },
            "chart": {
                "alerts_by_hour": alerts_by_hour,
            },
        }


report_service = ReportService()
