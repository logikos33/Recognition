"""Helper compartilhado: derivação de status offline para sites edge.

Fonte única de verdade usada por task-005 (GET /sites/health) e
task-016 (GET /overview). SQL e Python usam EXATAMENTE o mesmo limiar.
Regra do PR #25: sites em status 'provisioning' NÃO entram no contador offline.
"""
import os
from datetime import datetime, timezone

OFFLINE_THRESHOLD_SECONDS: int = int(
    os.environ.get("EDGE_OFFLINE_THRESHOLD_SECONDS", "120")
)


def derive_site_health_status(
    last_heartbeat_at: datetime | None,
    heartbeat_status: str | None,
    threshold_seconds: int = OFFLINE_THRESHOLD_SECONDS,
) -> str:
    """Deriva status do site a partir do último heartbeat.

    - Sem heartbeat → 'offline'
    - Heartbeat mais antigo que threshold_seconds → 'offline'
    - Caso contrário → status do heartbeat (healthy/degraded/critical)
    """
    if last_heartbeat_at is None:
        return "offline"
    if last_heartbeat_at.tzinfo is None:
        last_heartbeat_at = last_heartbeat_at.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - last_heartbeat_at).total_seconds()
    if elapsed > threshold_seconds:
        return "offline"
    return heartbeat_status or "offline"


def is_site_offline(
    last_heartbeat_at: datetime | None,
    heartbeat_status: str | None,
    site_status: str,
    threshold_seconds: int = OFFLINE_THRESHOLD_SECONDS,
) -> bool:
    """Retorna True se o site deve ser contado como offline no overview.

    Sites em 'provisioning' nunca são offline (são setup, não falha).
    """
    if site_status == "provisioning":
        return False
    return derive_site_health_status(last_heartbeat_at, heartbeat_status, threshold_seconds) == "offline"
