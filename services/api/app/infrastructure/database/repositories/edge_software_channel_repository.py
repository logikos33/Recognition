"""Repository: public.edge_software_channels — bare-metal OTA target_ref per
channel (migration 106, ADR-0057 item 10, no Docker — see
docs/edge/REGRAS_PLATAFORMA_JETSON.md §3.4). Platform-level, not tenant data:
no tenant_id column, same as public.feature-flag-style config.
"""
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository


class EdgeSoftwareChannelRepository(BaseRepository):
    def get_target_ref(self, channel: str) -> str | None:
        row = self._execute_one(
            "SELECT target_ref FROM public.edge_software_channels WHERE channel = %s",
            (channel,),
        )
        return row["target_ref"] if row else None

    def list_channels(self) -> list[dict[str, Any]]:
        return self._execute(
            "SELECT channel, target_ref, updated_at, updated_by "
            "FROM public.edge_software_channels "
            "ORDER BY channel"
        )

    def set_target_ref(
        self, channel: str, target_ref: str, updated_by: str | None
    ) -> dict[str, Any]:
        """Upsert — publishing a channel's target_ref is idempotent by design
        (an admin re-pinning the same ref, or fixing a typo, is the normal
        case, not an error)."""
        row = self._execute_mutation(
            """
            INSERT INTO public.edge_software_channels (channel, target_ref, updated_by, updated_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (channel) DO UPDATE
                SET target_ref = EXCLUDED.target_ref,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = now()
            RETURNING channel, target_ref, updated_at, updated_by
            """,
            (channel, target_ref, updated_by),
        )
        return row
