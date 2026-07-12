"""Repository: Training Frames."""
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from app.constants import FrameSource
from app.infrastructure.database.repositories.base import BaseRepository

_INSERT_COLUMNS = (
    "video_id, frame_number, filename, timestamp_seconds, source, r2_key, "
    "camera_id, recorder_id, width, height, model_confidence, captured_at, "
    "tenant_id, module_code"
)

# tenant_id NUNCA pode nascer NULL silenciosamente: as queries de auto-training
# e active-learning filtram WHERE tenant_id = %s e linhas órfãs ficam
# invisíveis. Fallback: explícito → tenant do user → tenant do dono do vídeo.
_TENANT_COALESCE = (
    "COALESCE(%(tenant_id)s::uuid, "
    "(SELECT tenant_id FROM users WHERE id = %(user_id)s::uuid), "
    "(SELECT u.tenant_id FROM training_videos v "
    "JOIN users u ON u.id = v.user_id WHERE v.id = %(video_id)s::uuid))"
)


class FrameRepository(BaseRepository):
    """Queries SQL para tabela training_frames."""

    def create(
        self,
        video_id: UUID | None,
        frame_number: int,
        filename: str,
        timestamp_seconds: float | None = None,
        *,
        source: str = FrameSource.VIDEO,
        r2_key: str | None = None,
        camera_id: UUID | None = None,
        recorder_id: UUID | None = None,
        width: int | None = None,
        height: int | None = None,
        model_confidence: float | None = None,
        captured_at: datetime | None = None,
        tenant_id: UUID | str | None = None,
        module_code: str | None = None,
        user_id: UUID | str | None = None,
    ) -> dict[str, Any]:
        """Cria registro de frame (multi-fonte desde migration 094).

        video_id é opcional (frames de upload/auto-captura/NVR não têm vídeo pai).
        Defaults retrocompatíveis: callers legados (video_id, frame_number,
        filename, timestamp_seconds) continuam funcionando — source='video',
        r2_key=filename (chave R2 legada), module_code='epi' (default do schema).
        tenant_id cai para o tenant do user_id ou do dono do vídeo quando não
        informado (linha com tenant NULL é invisível às queries tenant-scoped).
        """
        return self._execute_mutation(
            f"INSERT INTO training_frames ({_INSERT_COLUMNS}) "
            "VALUES (%(video_id)s, %(frame_number)s, %(filename)s, "
            "%(timestamp_seconds)s, %(source)s, %(r2_key)s, %(camera_id)s, "
            f"%(recorder_id)s, %(width)s, %(height)s, %(model_confidence)s, "
            f"%(captured_at)s, {_TENANT_COALESCE}, "
            "COALESCE(%(module_code)s, 'epi')) RETURNING *",
            {
                "video_id": str(video_id) if video_id else None,
                "frame_number": frame_number,
                "filename": filename,
                "timestamp_seconds": timestamp_seconds,
                "source": str(source),
                "r2_key": r2_key or filename,
                "camera_id": str(camera_id) if camera_id else None,
                "recorder_id": str(recorder_id) if recorder_id else None,
                "width": width,
                "height": height,
                "model_confidence": model_confidence,
                "captured_at": captured_at,
                "tenant_id": str(tenant_id) if tenant_id else None,
                "user_id": str(user_id) if user_id else None,
                "module_code": module_code,
            },
        )  # type: ignore[return-value]

    def create_bulk(self, frames: list[dict[str, Any]]) -> int:
        """Insere múltiplos frames. Retorna count.

        Cada dict precisa de frame_number e filename; demais chaves são
        opcionais com os mesmos defaults de create(). executemany com
        placeholders nomeados exige lista de DICTS (não tuplas) — bug
        latente corrigido (antes: [(f,) for f in frames]).
        """
        rows = [self._with_bulk_defaults(f) for f in frames]
        return self._execute_many(
            f"INSERT INTO training_frames ({_INSERT_COLUMNS}) "
            "VALUES (%(video_id)s, %(frame_number)s, %(filename)s, "
            "%(timestamp_seconds)s, %(source)s, %(r2_key)s, %(camera_id)s, "
            "%(recorder_id)s, %(width)s, %(height)s, %(model_confidence)s, "
            f"%(captured_at)s, {_TENANT_COALESCE}, "
            "COALESCE(%(module_code)s, 'epi'))",
            rows,  # type: ignore[arg-type]
        )

    @staticmethod
    def _with_bulk_defaults(frame: dict[str, Any]) -> dict[str, Any]:
        """Normaliza um dict de frame para o INSERT bulk (defaults retrocompat)."""
        def _opt_str(value: Any) -> str | None:
            return str(value) if value else None

        return {
            "video_id": _opt_str(frame.get("video_id")),
            "frame_number": frame["frame_number"],
            "filename": frame["filename"],
            "timestamp_seconds": frame.get("timestamp_seconds"),
            "source": str(frame.get("source") or FrameSource.VIDEO),
            "r2_key": frame.get("r2_key") or frame["filename"],
            "camera_id": _opt_str(frame.get("camera_id")),
            "recorder_id": _opt_str(frame.get("recorder_id")),
            "width": frame.get("width"),
            "height": frame.get("height"),
            "model_confidence": frame.get("model_confidence"),
            "captured_at": frame.get("captured_at"),
            "tenant_id": _opt_str(frame.get("tenant_id")),
            "user_id": _opt_str(frame.get("user_id")),
            "module_code": frame.get("module_code"),
        }

    def get_by_id(self, frame_id: UUID) -> dict[str, Any] | None:
        """Busca frame por ID sem verificação de posse.

        INTERNAL USE ONLY — use get_by_id_and_user() in API handlers.
        Safe for Celery tasks where user context is not available.
        """
        return self._execute_one(
            "SELECT * FROM training_frames WHERE id = %s",
            (str(frame_id),),
        )

    def get_by_video(self, video_id: UUID) -> list[dict[str, Any]]:
        """Lista frames de um vídeo."""
        return self._execute(
            "SELECT * FROM training_frames WHERE video_id = %s "
            "ORDER BY frame_number ASC",
            (str(video_id),),
        )

    def get_next_unannotated(self, video_id: UUID) -> dict[str, Any] | None:
        """Busca próximo frame não anotado (FIFO)."""
        return self._execute_one(
            "SELECT * FROM training_frames "
            "WHERE video_id = %s AND is_annotated = FALSE "
            "ORDER BY frame_number ASC LIMIT 1",
            (str(video_id),),
        )

    def mark_annotated(self, frame_id: UUID) -> dict[str, Any] | None:
        """Marca frame como anotado."""
        return self._execute_mutation(
            "UPDATE training_frames SET is_annotated = TRUE "
            "WHERE id = %s RETURNING *",
            (str(frame_id),),
        )

    def update_quality_status(
        self,
        frame_id: UUID,
        status: str,
        scores: dict | None = None,
    ) -> "dict[str, Any] | None":
        """Atualiza quality_status e quality_scores do frame."""
        return self._execute_mutation(
            "UPDATE training_frames SET quality_status = %s, quality_scores = %s "
            "WHERE id = %s RETURNING *",
            (status, json.dumps(scores or {}), str(frame_id)),
        )

    def get_approved_by_video(self, video_id: UUID) -> "list[dict[str, Any]]":
        """Lista frames aprovados no filtro de qualidade."""
        return self._execute(
            "SELECT * FROM training_frames "
            "WHERE video_id = %s AND quality_status != 'rejected' "
            "ORDER BY frame_number ASC",
            (str(video_id),),
        )

    def count_by_status(self, video_id: UUID) -> dict[str, int]:
        """Conta frames por status de anotação."""
        rows = self._execute(
            "SELECT is_annotated, COUNT(*) as count "
            "FROM training_frames WHERE video_id = %s "
            "GROUP BY is_annotated",
            (str(video_id),),
        )
        result = {"annotated": 0, "pending": 0, "total": 0}
        for row in rows:
            if row["is_annotated"]:
                result["annotated"] = row["count"]
            else:
                result["pending"] = row["count"]
        result["total"] = result["annotated"] + result["pending"]
        return result

    # AI_NOTE: US-021 — Surface pre-annotations from JSONB for AnnotationInterface
    def get_pre_annotations(self, frame_id: UUID) -> "list[dict] | None":
        """Retorna pré-anotações DINO/SAM do frame (JSONB), ou None se não houver."""
        row = self._execute_one(
            "SELECT pre_annotations FROM training_frames WHERE id = %s",
            (str(frame_id),),
        )
        if not row:
            return None
        return row.get("pre_annotations")  # list[dict] ou None

    def get_annotated_by_video(self, video_id: UUID, user_id: UUID) -> "list[dict]":
        """Lista frames anotados de um vídeo verificando posse via user_id.

        JOIN em training_videos garante que apenas o dono do vídeo obtém resultados
        (mesmo padrão de count_validated/get_by_id_and_user). Fix P0-01.
        """
        return self._execute(
            "SELECT tf.*, "
            "  COUNT(fa.id) AS annotation_count, "
            "  tf.validated_at IS NOT NULL AS is_validated "
            "FROM training_frames tf "
            "JOIN training_videos tv ON tv.id = tf.video_id "
            "LEFT JOIN frame_annotations fa ON fa.frame_id = tf.id "
            "WHERE tf.video_id = %s AND tv.user_id = %s AND tf.is_annotated = TRUE "
            "GROUP BY tf.id "
            "ORDER BY tf.frame_number ASC",
            (str(video_id), str(user_id)),
        )

    def get_by_id_and_user(self, frame_id: UUID, user_id: UUID) -> "dict | None":
        """Busca frame por ID validando posse.

        AI_NOTE: US-022 security fix — evita IDOR ao validar/anotar frame.

        Achado (validação E2E Fase A): o JOIN original era INNER contra
        training_videos — frames sem vídeo pai (video_id NULL, fontes
        upload/auto/nvr desde a migration 094) NUNCA batiam, então
        save_annotations/validate_frame quebravam 100% das vezes pra
        qualquer imagem enviada via upload (WS-A2). training_frames não
        tem coluna user_id própria (só tenant_id) — pra frame sem vídeo, a
        posse correta é por tenant (mesmo modelo usado em todo o resto do
        WS-A2, ex. list_images_filtered). Frame com vídeo mantém a regra
        original (dono do vídeo) — comportamento existente preservado.
        """
        return self._execute_one(
            "SELECT tf.* FROM training_frames tf "
            "LEFT JOIN training_videos tv ON tv.id = tf.video_id "
            "WHERE tf.id = %s AND ("
            "  tv.user_id = %s "
            "  OR (tf.video_id IS NULL "
            "      AND tf.tenant_id = (SELECT tenant_id FROM users WHERE id = %s))"
            ")",
            (str(frame_id), str(user_id), str(user_id)),
        )

    def mark_validated(self, frame_id: UUID, user_id: UUID) -> "dict | None":
        """Marca frame como validado por humano (apenas frames do próprio usuário).

        AI_NOTE: filtra por posse pra prevenir IDOR. Mesmo achado do fix em
        get_by_id_and_user: o JOIN original (`FROM training_videos tv WHERE
        tf.video_id = tv.id`) é efetivamente um INNER JOIN — frame sem
        vídeo pai (upload/auto/nvr, video_id NULL) nunca batia, então
        nenhuma imagem enviada via upload podia ser marcada como revisada.
        Frame com vídeo mantém a regra original (dono do vídeo); frame sem
        vídeo usa posse por tenant (única disponível — a tabela não tem
        coluna user_id própria).
        """
        return self._execute_mutation(
            "UPDATE training_frames tf "
            "SET validated_by = %s, validated_at = NOW() "
            "WHERE tf.id = %s AND ("
            "  EXISTS (SELECT 1 FROM training_videos tv "
            "          WHERE tv.id = tf.video_id AND tv.user_id = %s) "
            "  OR (tf.video_id IS NULL "
            "      AND tf.tenant_id = (SELECT tenant_id FROM users WHERE id = %s))"
            ") "
            "RETURNING tf.*",
            (str(user_id), str(frame_id), str(user_id), str(user_id)),
        )

    def get_by_user_paginated(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 24,
        is_annotated: "bool | None" = None,
        order: str = "desc",
    ) -> "dict[str, Any]":
        """Lista frames do usuário com paginação e filtros.

        Usado pela galeria de imagens de treino (Tab 1).
        Filtra por user_id via JOIN em training_videos.
        """
        offset = (page - 1) * page_size

        conditions = ["tv.user_id = %s"]
        params: list[Any] = [str(user_id)]

        if is_annotated is not None:
            conditions.append("tf.is_annotated = %s")
            params.append(is_annotated)

        where = " AND ".join(conditions)
        order_dir = "DESC" if order == "desc" else "ASC"

        count_row = self._execute_one(
            "SELECT COUNT(*) AS total FROM training_frames tf "
            f"JOIN training_videos tv ON tv.id = tf.video_id WHERE {where}",
            tuple(params),
        )
        total = int(count_row["total"]) if count_row else 0

        frames = self._execute(
            "SELECT tf.id, tf.video_id, tf.frame_number, tf.filename, "
            "tf.is_annotated, tf.created_at, "
            "tv.original_filename AS video_name "
            "FROM training_frames tf "
            f"JOIN training_videos tv ON tv.id = tf.video_id WHERE {where} "
            f"ORDER BY tf.created_at {order_dir} LIMIT %s OFFSET %s",
            tuple(params + [page_size, offset]),
        )

        return {
            "frames": list(frames),
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    def count_validated(self, video_id: UUID, user_id: UUID) -> dict:
        """Conta frames validados e anotados de um vídeo (verificando posse).

        AI_NOTE: JOIN em training_videos garante que user_id é dono do vídeo.
        """
        row = self._execute_one(
            "SELECT "
            "  COUNT(*) FILTER (WHERE tf.is_annotated = TRUE) AS annotated, "
            "  COUNT(*) FILTER (WHERE tf.validated_at IS NOT NULL) AS validated, "
            "  COUNT(*) AS total "
            "FROM training_frames tf "
            "JOIN training_videos tv ON tv.id = tf.video_id "
            "WHERE tf.video_id = %s AND tv.user_id = %s",
            (str(video_id), str(user_id)),
        )
        return (
            {
                "annotated": int(row["annotated"] or 0),
                "validated": int(row["validated"] or 0),
                "total": int(row["total"] or 0),
            }
            if row
            else {"annotated": 0, "validated": 0, "total": 0}
        )

    # ------------------------------------------------------------------
    # WS-A2 — galeria multi-fonte (método APPEND-ONLY; não alterar acima)
    # ------------------------------------------------------------------

    _STATUS_CONDITIONS: "dict[str, str]" = {
        # Plano linhas 83-85 — status é COMPUTADO, sem coluna nova.
        "unlabeled": "tf.is_annotated = FALSE",
        "labeled": "(tf.is_annotated = TRUE AND tf.validated_at IS NULL)",
        "reviewed": "tf.validated_at IS NOT NULL",
    }

    def list_images_filtered(
        self,
        tenant_id: "UUID | str",
        page: int = 1,
        page_size: int = 24,
        source: "str | None" = None,
        status: "str | None" = None,
        is_annotated: "bool | None" = None,
        order: str = "desc",
    ) -> "dict[str, Any]":
        """Lista imagens de treino do tenant com filtros ?source= e ?status=.

        Diferenças de get_by_user_paginated (mantido intacto p/ compat):
          - escopo por tenant_id (frames de upload/auto/nvr não têm vídeo
            pai, logo não têm user_id derivável — C-01 multi-tenant);
          - LEFT JOIN em training_videos (video_id pode ser NULL desde 094);
          - status computado no SELECT:
              unlabeled = NOT is_annotated
              labeled   = is_annotated AND validated_at IS NULL
              reviewed  = validated_at IS NOT NULL

        Retorno com o MESMO shape de get_by_user_paginated; cada frame ganha
        campos extras (source, r2_key, width, height, status). WHERE é montado
        só com fragmentos estáticos whitelisted — input do usuário vai
        exclusivamente em params (%s).
        """
        offset = (max(1, page) - 1) * page_size

        conditions = ["tf.tenant_id = %s"]
        params: "list[Any]" = [str(tenant_id)]

        if source is not None:
            conditions.append("tf.source = %s")
            params.append(str(source))

        if status is not None:
            status_condition = self._STATUS_CONDITIONS.get(status)
            if status_condition is None:
                raise ValueError(
                    f"status inválido: {status!r} "
                    f"(esperado: {sorted(self._STATUS_CONDITIONS)})"
                )
            conditions.append(status_condition)

        if is_annotated is not None:
            conditions.append("tf.is_annotated = %s")
            params.append(is_annotated)

        where = " AND ".join(conditions)
        order_dir = "DESC" if order == "desc" else "ASC"

        count_row = self._execute_one(
            f"SELECT COUNT(*) AS total FROM training_frames tf WHERE {where}",
            tuple(params),
        )
        total = int(count_row["total"]) if count_row else 0

        frames = self._execute(
            "SELECT tf.id, tf.video_id, tf.frame_number, tf.filename, "
            "tf.r2_key, tf.source, tf.width, tf.height, "
            "tf.is_annotated, tf.created_at, "
            "CASE WHEN tf.validated_at IS NOT NULL THEN 'reviewed' "
            "     WHEN tf.is_annotated THEN 'labeled' "
            "     ELSE 'unlabeled' END AS status, "
            "tv.original_filename AS video_name "
            "FROM training_frames tf "
            "LEFT JOIN training_videos tv ON tv.id = tf.video_id "
            f"WHERE {where} "
            f"ORDER BY tf.created_at {order_dir} LIMIT %s OFFSET %s",
            tuple(params + [page_size, offset]),
        )

        return {
            "frames": list(frames),
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }
