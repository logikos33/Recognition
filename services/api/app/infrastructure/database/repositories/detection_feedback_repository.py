"""Repository: DetectionFeedback — flywheel de feedback do operador (migration 059)."""
from typing import Any

from app.infrastructure.database.repositories.base import BaseRepository


class DetectionFeedbackRepository(BaseRepository):
    """SQL para public.detection_feedback."""

    def create(
        self,
        tenant_id: str,
        module: str | None,
        camera_id: str | None,
        detection_ref: str | None,
        frame_r2_key: str | None,
        verdict: str,
        corrected_class: str | None,
        created_by: str,
    ) -> dict[str, Any] | None:
        return self._execute_mutation(
            """
            INSERT INTO public.detection_feedback (
                tenant_id, module, camera_id, detection_ref,
                frame_r2_key, verdict, corrected_class, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, verdict, created_at
            """,
            (
                tenant_id, module, camera_id, detection_ref,
                frame_r2_key, verdict, corrected_class, created_by,
            ),
        )

    def list_by_module(
        self,
        tenant_id: str,
        module: str | None = None,
        limit: int = 100,
        verdict: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lista feedback para revisão ou exportação para pipeline de treino."""
        limit = min(max(limit, 1), 500)
        conditions = ["tenant_id = %s"]
        params: list = [tenant_id]
        if module:
            conditions.append("module = %s")
            params.append(module)
        if verdict:
            conditions.append("verdict = %s")
            params.append(verdict)
        where = " AND ".join(conditions)
        params.append(limit)
        return self._execute(
            f"SELECT id, module, camera_id, detection_ref, frame_r2_key, "  # noqa: S608
            f"verdict, corrected_class, created_by, created_at "
            f"FROM public.detection_feedback WHERE {where} "
            f"ORDER BY created_at DESC LIMIT %s",
            tuple(params),
        )

    def summary_by_module(self, tenant_id: str) -> list[dict[str, Any]]:
        """Contagem de feedback por módulo e verdict (para dashboard de qualidade)."""
        return self._execute(
            """
            SELECT module, verdict, COUNT(*) AS count
            FROM public.detection_feedback
            WHERE tenant_id = %s
            GROUP BY module, verdict
            ORDER BY module, verdict
            """,
            (tenant_id,),
        )
