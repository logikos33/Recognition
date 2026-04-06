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
        """
        frame = self._frame_repo.get_by_id(frame_id)
        if not frame:
            raise NotFoundError("Frame", str(frame_id))

        for ann in annotations:
            self._validate_annotation(ann)

        count = self._annotation_repo.save_batch(frame_id, annotations)

        if count > 0:
            self._frame_repo.mark_annotated(frame_id)

        return count

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
