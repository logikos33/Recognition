"""
EPI Monitor V2 — Annotation Service.

Lógica de anotação de frames. Adapta-se ao contrato do AnnotationInterface.jsx.
"""
import logging
from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
)
from app.infrastructure.database.repositories.frame_repository import FrameRepository

logger = logging.getLogger(__name__)


class AnnotationService:
    """Use cases de anotação de frames."""

    def __init__(
        self,
        annotation_repo: AnnotationRepository,
        frame_repo: FrameRepository,
    ) -> None:
        self._annotation_repo = annotation_repo
        self._frame_repo = frame_repo

    def get_classes(self, user_id: UUID) -> list[dict]:
        """Lista classes YOLO do usuário."""
        classes = self._annotation_repo.get_classes_by_user(user_id)
        return classes

    def create_class(
        self, user_id: UUID, name: str, color: str = "#3b82f6"
    ) -> dict:
        """Cria classe YOLO."""
        if not name or not name.strip():
            raise ValidationError("Nome da classe é obrigatório")
        return self._annotation_repo.create_class(user_id, name.strip(), color)

    def get_frame_annotations(self, frame_id: UUID) -> list[dict]:
        """Lista anotações de um frame (com nome/cor da classe)."""
        annotations = self._annotation_repo.get_by_frame(frame_id)
        for a in annotations:
            a["id"] = str(a["id"])
        return annotations

    def save_annotations(
        self,
        frame_id: UUID,
        annotations: list[dict],
    ) -> int:
        """Salva anotações de um frame (replace all).

        Valida formato YOLO: cx, cy, w, h entre 0 e 1.
        Marca frame como anotado.
        Exporta labels em formato YOLO .txt para R2/storage.
        """
        frame = self._frame_repo.get_by_id(frame_id)
        if not frame:
            raise NotFoundError("Frame", str(frame_id))

        for ann in annotations:
            self._validate_annotation(ann)

        count = self._annotation_repo.save_batch(frame_id, annotations)

        if count > 0:
            self._frame_repo.mark_annotated(frame_id)
            self._export_yolo_labels(frame, annotations)

        return count

    def _export_yolo_labels(self, frame: dict, annotations: list[dict]) -> None:
        """Serializa anotações em formato YOLO e faz upload para storage.

        Formato YOLO: uma linha por box — <class_id> <cx> <cy> <w> <h>
        Valores normalizados [0,1]. Chave R2: labels/{frame_key_sem_ext}.txt
        """
        try:
            lines = []
            for ann in annotations:
                lines.append(
                    f"{int(ann['class_id'])} "
                    f"{float(ann['x_center']):.6f} "
                    f"{float(ann['y_center']):.6f} "
                    f"{float(ann['width']):.6f} "
                    f"{float(ann['height']):.6f}"
                )

            label_content = "\n".join(lines).encode("utf-8")

            # Derivar chave do label a partir do filename do frame
            # frame_key: frames/{user_id}/{video_id}/frame_NNNN.jpg
            # label_key: labels/{user_id}/{video_id}/frame_NNNN.txt
            frame_key: str = frame.get("filename", "")
            if frame_key:
                base, _ = frame_key.rsplit(".", 1) if "." in frame_key else (frame_key, "")
                label_key = base.replace("frames/", "labels/", 1) + ".txt"
            else:
                label_key = f"labels/unknown/{frame['id']}.txt"

            from app.infrastructure.storage.local_storage import get_storage
            storage = get_storage()
            storage.upload_bytes(label_key, label_content, "text/plain")

            logger.debug("yolo_labels_exported: frame_id=%s, key=%s, boxes=%d",
                         frame.get("id"), label_key, len(annotations))

        except Exception as exc:
            # Exportação de labels é best-effort — não falha o save
            logger.error("yolo_export_failed: frame_id=%s, error=%s", frame.get("id"), exc)

    @staticmethod
    def _validate_annotation(ann: dict) -> None:
        """Valida uma anotação individual."""
        required = ["class_id", "x_center", "y_center", "width", "height"]
        for field in required:
            if field not in ann:
                raise ValidationError(f"Campo obrigatório: {field}")

        for coord in ["x_center", "y_center", "width", "height"]:
            val = float(ann[coord])
            if not (0.0 <= val <= 1.0):
                raise ValidationError(
                    f"{coord} deve estar entre 0 e 1 (recebido: {val})"
                )
