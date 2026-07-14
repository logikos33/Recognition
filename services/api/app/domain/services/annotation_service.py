"""
Recognition — Annotation Service.

Lógica de anotação de frames. Adapta-se ao contrato do AnnotationInterface.jsx.
"""
import logging
from uuid import UUID

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
)
from app.infrastructure.database.repositories.frame_repository import FrameRepository
from app.infrastructure.database.repositories.module_repository import ModuleRepository

logger = logging.getLogger(__name__)


class AnnotationService:
    """Use cases de anotação de frames."""

    def __init__(
        self,
        annotation_repo: AnnotationRepository,
        frame_repo: FrameRepository,
        module_repo: ModuleRepository,
    ) -> None:
        self._annotation_repo = annotation_repo
        self._frame_repo = frame_repo
        self._module_repo = module_repo

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
            # AI_NOTE: DINO salva "class", legado usa "label"
            label = (p.get("class") or p.get("label") or "").lower().strip()
            class_name = p.get("class") or p.get("label") or "Desconhecido"

            # Mapear label → class_id — SEM fallback silencioso (ADR-0017,
            # task-077). Label que não mapeia pra nenhuma classe conhecida do
            # usuário é um erro de dados/integração, não "assume a primeira
            # classe" ou "assume id=1" — isso é exatamente a classe de bug
            # que esta task corrige (rótulo errado sem erro visível).
            class_id = class_map.get(label)
            if class_id is None:
                logger.warning(
                    "pre_annotation_unmapped_label: frame=%s, i=%d, label=%r",
                    frame_id, i, label,
                )
                raise ValidationError(
                    f"Pré-anotação com label desconhecido: '{label}' "
                    "não corresponde a nenhuma classe do usuário"
                )

            # Garantir coordenadas válidas [0,1]
            # AI_NOTE: DINO salva bbox como dict {cx,cy,w,h}, legado como array [cx,cy,w,h]
            try:
                if isinstance(bbox, dict):
                    cx = float(bbox.get("cx", 0.5))
                    cy = float(bbox.get("cy", 0.5))
                    w = float(bbox.get("w", 0.1))
                    h = float(bbox.get("h", 0.1))
                else:
                    cx, cy, w, h = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                cx = max(0.0, min(1.0, cx))
                cy = max(0.0, min(1.0, cy))
                w = max(0.01, min(1.0, w))
                h = max(0.01, min(1.0, h))
            except (IndexError, ValueError, TypeError, KeyError):
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

        module_classes_cache: dict[str, set[int]] = {}
        for ann in annotations:
            self._validate_annotation(ann)
            self._validate_class(ann, module_classes_cache)

        count = self._annotation_repo.save_batch(frame_id, annotations)

        if count > 0:
            self._frame_repo.mark_annotated(frame_id)
            self._export_yolo_labels(frame, annotations)

        return count

    def pre_annotate_frame(
        self, frame_id: UUID, tenant_id: str, user_id: UUID, module_code: str
    ) -> int:
        """Dispara pré-anotação (WS-B4, backend plugável — OFF por padrão).

        403 se o tenant não tiver a flag `pre_annotation_enabled` ligada
        (ver ADR-0031, adendo — nasce desligada por causa do histórico de
        custo×qualidade do DINO+SAM). Ownership check via get_by_id_and_user
        (mesmo padrão anti-IDOR de save_annotations/get_frame_annotations).
        """
        if not self._frame_repo.get_by_id_and_user(frame_id, user_id):
            raise NotFoundError("Frame", str(frame_id))

        from app.domain.services.pre_annotation.factory import (  # noqa: PLC0415
            get_pre_annotation_backend,
        )
        backend = get_pre_annotation_backend(str(tenant_id))
        if backend is None:
            raise AuthorizationError(
                "Pré-anotação desabilitada para este tenant "
                "(feature flag pre_annotation_enabled)"
            )
        return backend.predict_and_store(str(frame_id), module_code)

    def accept_suggestions(
        self, frame_id: UUID, user_id: UUID, indices: list[int] | None = None
    ) -> int:
        """Aceita pré-anotações como anotações reais (WS-B4).

        indices=None aceita todas as sugestões pendentes; senão, só os
        índices dados (0-based, mesma ordem de pre_annotations/get_frame_
        annotations). Reusa get_frame_annotations (já faz ownership check
        + conversão bbox/class_id) — se o frame já tem anotação humana,
        não há sugestão "ai" pendente pra aceitar (mesma regra de "não
        misturar humano com IA" de get_frame_annotations).
        """
        suggestions = self.get_frame_annotations(frame_id, user_id)
        ai_suggestions = [s for s in suggestions if s.get("source") == "ai"]
        if indices is not None:
            wanted = set(indices)
            ai_suggestions = [s for i, s in enumerate(ai_suggestions) if i in wanted]
        if not ai_suggestions:
            return 0

        count = self._annotation_repo.accept_pre_annotations(
            frame_id, ai_suggestions, user_id
        )
        if count > 0:
            self._frame_repo.mark_annotated(frame_id)
        return count

    def _export_yolo_labels(self, frame: dict, annotations: list[dict]) -> None:
        """Serializa anotações em formato YOLO e faz upload para storage.

        Formato YOLO: uma linha por box — <class_id> <cx> <cy> <w> <h>
        Valores normalizados [0,1]. Chave R2: labels/{frame_key_sem_ext}.txt

        class_id aqui é o índice 0-based do MÓDULO (module_classes.class_id),
        já validado em _validate_class antes do save (task-077) — é o mesmo
        índice usado para treinar o modelo, não precisa de tradução.
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
        required = ["class_id", "class_name", "module_code", "x_center", "y_center", "width", "height"]
        for field in required:
            if field not in ann:
                raise ValidationError(f"Campo obrigatório: {field}")

        for coord in ["x_center", "y_center", "width", "height"]:
            val = float(ann[coord])
            if not (0.0 <= val <= 1.0):
                raise ValidationError(
                    f"{coord} deve estar entre 0 e 1 (recebido: {val})"
                )

    def _validate_class(self, ann: dict, cache: dict[str, set[int]]) -> None:
        """Valida class_name/module_code (task-077 — sem fallback, ADR-0017).

        class_name não pode ser vazio; (module_code, class_id) precisa
        corresponder a uma classe real de module_classes — a única fonte de
        verdade para o espaço de numeração usado pelo frontend. cache evita
        N queries repetidas por module_code dentro do mesmo batch.
        """
        class_name = str(ann.get("class_name") or "").strip()
        if not class_name:
            raise ValidationError("class_name é obrigatório e não pode ser vazio")

        module_code = str(ann.get("module_code") or "").strip()
        if not module_code:
            raise ValidationError("module_code é obrigatório e não pode ser vazio")

        if module_code not in cache:
            classes = self._module_repo.get_classes(module_code)
            cache[module_code] = {c["class_id"] for c in classes}
            if not cache[module_code]:
                logger.warning("annotation_unknown_module: module_code=%s", module_code)
                raise ValidationError(f"Módulo desconhecido: '{module_code}'")

        class_id = ann.get("class_id")
        if class_id not in cache[module_code]:
            logger.warning(
                "annotation_unknown_class: module_code=%s class_id=%s",
                module_code, class_id,
            )
            raise ValidationError(
                f"class_id {class_id} não existe no módulo '{module_code}'"
            )
