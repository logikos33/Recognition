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
        return self._annotation_repo.get_classes_by_user(user_id)

    def create_class(
        self, user_id: UUID, name: str, color: str = "#3b82f6"
    ) -> dict:
        """Cria classe YOLO."""
        if not name or not name.strip():
            raise ValidationError("Nome da classe é obrigatório")
        return self._annotation_repo.create_class(user_id, name.strip(), color)

    def get_frame_annotations(self, frame_id: UUID, user_id: UUID | None = None) -> list[dict]:
        """Lista anotações de um frame (com nome/cor da classe).

        Se o frame não tem anotações humanas mas tem pre_annotations (DINO/SAM),
        retorna as pré-anotações convertidas para o formato AnnotationInterface.

        AI_NOTE: US-021 — fallback para pré-anotações JSONB quando não há anotações humanas.
        """
        # AI_NOTE: US-035 — ownership check prevents IDOR cross-tenant frame access
        if user_id is not None and not self._frame_repo.get_by_id_and_user(frame_id, user_id):
            raise NotFoundError("Frame", str(frame_id))

        annotations = self._annotation_repo.get_by_frame(frame_id)
        if annotations:
            # Humano já anotou — não misturar com IA
            for a in annotations:
                a["id"] = str(a["id"])
            return annotations

        # Sem anotações humanas — tentar pré-anotações da IA
        pre = self._frame_repo.get_pre_annotations(frame_id)
        if not pre:
            return []

        # Buscar classes do usuário para mapear label → class_id
        classes: list[dict] = []
        if user_id is not None:
            classes = self._annotation_repo.get_classes_by_user(user_id)
        class_map = {c["name"].lower(): c["id"] for c in classes}

        result = []
        for i, p in enumerate(pre):
            bbox = p.get("bbox", [0.5, 0.5, 0.1, 0.1])
            label = (p.get("label") or "").lower().strip()
            class_name = p.get("label") or "Desconhecido"

            # Mapear label → class_id; fallback para primeiro class ou 1
            class_id = class_map.get(label)
            if class_id is None and classes:
                class_id = classes[0]["id"]
            if class_id is None:
                class_id = 1

            # Garantir coordenadas válidas [0,1]
            try:
                cx, cy, w, h = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                cx = max(0.0, min(1.0, cx))
                cy = max(0.0, min(1.0, cy))
                w = max(0.01, min(1.0, w))
                h = max(0.01, min(1.0, h))
            except (IndexError, ValueError, TypeError):
                logger.warning(
                    "pre_annotation_invalid_bbox: frame=%s, i=%d, bbox=%s", frame_id, i, bbox
                )
                continue

            result.append({
                "id": f"pre-{i}",
                "class_id": class_id,
                "class_name": class_name,
                "x_center": cx,
                "y_center": cy,
                "width": w,
                "height": h,
                "source": "ai",
                "confidence": p.get("confidence"),
            })

        logger.debug("pre_annotations_loaded: frame=%s, count=%d", frame_id, len(result))
        return result

    def save_annotations(
        self,
        frame_id: UUID,
        annotations: list[dict],
        user_id: UUID | None = None,
    ) -> int:
        """Salva anotações de um frame (replace all).

        Valida formato YOLO: cx, cy, w, h entre 0 e 1.
        Marca frame como anotado.
        Exporta labels em formato YOLO .txt para R2/storage.

        AI_NOTE: user_id opcional para verificação de posse (anti-IDOR).
        Se fornecido, usa get_by_id_and_user para garantir que o frame
        pertence ao usuário. Fallback para get_by_id se user_id ausente.
        """
        frame = (
            self._frame_repo.get_by_id_and_user(frame_id, user_id)
            if user_id is not None
            else self._frame_repo.get_by_id(frame_id)
        )
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
