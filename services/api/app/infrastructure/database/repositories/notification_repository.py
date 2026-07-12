"""Repository: Notification — canais e log de entregas (migration 058)."""
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository


class NotificationRepository(BaseRepository):
    """SQL para public.notification_channels e public.notification_log."""

    # ── Channels ──────────────────────────────────────────────────────────────

    def list_channels(self, tenant_id: str) -> list[dict[str, Any]]:
        return self._execute(
            """
            SELECT id, type, recipients, enabled, created_at, updated_at
            FROM public.notification_channels
            WHERE tenant_id = %s
            ORDER BY created_at
            """,
            (tenant_id,),
        )

    def get_channel(self, tenant_id: str, channel_id: str) -> dict[str, Any] | None:
        return self._execute_one(
            "SELECT id, type, config, recipients, enabled, created_at, updated_at "
            "FROM public.notification_channels WHERE tenant_id = %s AND id = %s",
            (tenant_id, channel_id),
        )

    def create_channel(
        self,
        tenant_id: str,
        channel_type: str,
        config: dict,
        recipients: list,
    ) -> dict[str, Any] | None:
        import json
        return self._execute_mutation(
            """
            INSERT INTO public.notification_channels (tenant_id, type, config, recipients)
            VALUES (%s, %s, %s::jsonb, %s::jsonb)
            RETURNING id, type, recipients, enabled, created_at
            """,
            (tenant_id, channel_type, json.dumps(config), json.dumps(recipients)),
        )

    def update_channel(
        self,
        tenant_id: str,
        channel_id: str,
        enabled: bool | None,
        recipients: list | None,
        config: dict | None,
    ) -> dict[str, Any] | None:
        import json
        sets = ["updated_at = NOW()"]
        params: list = []
        if enabled is not None:
            sets.append("enabled = %s")
            params.append(enabled)
        if recipients is not None:
            sets.append("recipients = %s::jsonb")
            params.append(json.dumps(recipients))
        if config is not None:
            sets.append("config = %s::jsonb")
            params.append(json.dumps(config))
        params += [tenant_id, channel_id]
        return self._execute_mutation(
            f"UPDATE public.notification_channels SET {', '.join(sets)} "  # noqa: S608
            f"WHERE tenant_id = %s AND id = %s "
            f"RETURNING id, type, recipients, enabled, updated_at",
            tuple(params),
        )

    def delete_channel(self, tenant_id: str, channel_id: str) -> int:
        return self._execute_mutation_no_return(
            "DELETE FROM public.notification_channels WHERE tenant_id = %s AND id = %s",
            (tenant_id, channel_id),
        )

    # ── Log ───────────────────────────────────────────────────────────────────

    def log_delivery(
        self,
        tenant_id: str,
        channel_id: str | None,
        alert_ref: str | None,
        status: str,
        dedup_key: str | None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        return self._execute_mutation(
            """
            INSERT INTO public.notification_log
                (tenant_id, channel_id, alert_ref, status, dedup_key, error)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id, status, sent_at
            """,
            (tenant_id, channel_id, alert_ref, status, dedup_key, error),
        )
