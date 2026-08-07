"""Tests: AnnotationService."""
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.services.annotation_service import AnnotationService
from app.domain.services.class_namespace import namespace_tenant_class_id


class TestAnnotationService:
    """Testes para AnnotationService."""

    def setup_method(self) -> None:
        self.annotation_repo = MagicMock()
        self.frame_repo = MagicMock()
        self.module_repo = MagicMock()
        self.module_repo.get_classes.return_value = [
            {"module_code": "epi", "class_id": 0, "class_name": "helmet"},
            {"module_code": "epi", "class_id": 1, "class_name": "no_helmet"},
            {"module_code": "epi", "class_id": 2, "class_name": "vest"},
        ]
        self.service = AnnotationService(self.annotation_repo, self.frame_repo, self.module_repo)

    def test_get_classes(self) -> None:
        uid = uuid4()
        self.annotation_repo.get_classes_by_user.return_value = [
            {"id": 1, "name": "Capacete", "color": "#22c55e"},
            {"id": 2, "name": "Colete", "color": "#f59e0b"},
        ]
        result = self.service.get_classes(uid)
        assert len(result) == 2

    def test_create_class(self) -> None:
        uid = uuid4()
        self.annotation_repo.create_class.return_value = {
            "id": 1, "name": "Capacete", "color": "#22c55e",
        }
        result = self.service.create_class(uid, "Capacete", "#22c55e")
        assert result["name"] == "Capacete"

    def test_create_class_empty_name(self) -> None:
        with pytest.raises(ValidationError, match="obrigatório"):
            self.service.create_class(uuid4(), "", "#fff")

    def test_save_annotations_success(self) -> None:
        fid = uuid4()
        self.frame_repo.get_by_id.return_value = {"id": fid}
        self.annotation_repo.save_batch.return_value = 2
        annotations = [
            {"class_id": 1, "class_name": "no_helmet", "module_code": "epi",
             "x_center": 0.5, "y_center": 0.5, "width": 0.3, "height": 0.4},
            {"class_id": 2, "class_name": "vest", "module_code": "epi",
             "x_center": 0.2, "y_center": 0.8, "width": 0.1, "height": 0.2},
        ]
        result = self.service.save_annotations(fid, annotations)
        assert result == 2
        self.frame_repo.mark_annotated.assert_called_once_with(fid)

    def test_save_annotations_frame_not_found(self) -> None:
        self.frame_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            self.service.save_annotations(uuid4(), [])

    def test_save_annotations_invalid_coords(self) -> None:
        fid = uuid4()
        self.frame_repo.get_by_id.return_value = {"id": fid}
        annotations = [
            {"class_id": 1, "class_name": "no_helmet", "module_code": "epi",
             "x_center": 1.5, "y_center": 0.5, "width": 0.3, "height": 0.4},
        ]
        with pytest.raises(ValidationError, match="entre 0 e 1"):
            self.service.save_annotations(fid, annotations)

    def test_save_annotations_missing_field(self) -> None:
        fid = uuid4()
        self.frame_repo.get_by_id.return_value = {"id": fid}
        annotations = [{"class_id": 1, "x_center": 0.5}]
        with pytest.raises(ValidationError, match="obrigatório"):
            self.service.save_annotations(fid, annotations)

    def test_save_annotations_empty_class_name_raises(self) -> None:
        fid = uuid4()
        self.frame_repo.get_by_id.return_value = {"id": fid}
        annotations = [
            {"class_id": 1, "class_name": "  ", "module_code": "epi",
             "x_center": 0.5, "y_center": 0.5, "width": 0.3, "height": 0.4},
        ]
        with pytest.raises(ValidationError, match="class_name"):
            self.service.save_annotations(fid, annotations)

    def test_save_annotations_unknown_class_id_raises_422(self) -> None:
        fid = uuid4()
        self.frame_repo.get_by_id.return_value = {"id": fid}
        annotations = [
            {"class_id": 99, "class_name": "forklift", "module_code": "epi",
             "x_center": 0.5, "y_center": 0.5, "width": 0.3, "height": 0.4},
        ]
        with pytest.raises(ValidationError, match="não existe no módulo"):
            self.service.save_annotations(fid, annotations)

    def test_save_annotations_unknown_module_raises(self) -> None:
        fid = uuid4()
        self.frame_repo.get_by_id.return_value = {"id": fid}
        self.module_repo.get_classes.return_value = []
        annotations = [
            {"class_id": 0, "class_name": "truck", "module_code": "fueling",
             "x_center": 0.5, "y_center": 0.5, "width": 0.3, "height": 0.4},
        ]
        with pytest.raises(ValidationError, match="Módulo desconhecido"):
            self.service.save_annotations(fid, annotations)

    def test_get_frame_annotations(self) -> None:
        fid = uuid4()
        self.annotation_repo.get_by_frame.return_value = [
            {"id": uuid4(), "class_id": 1, "x_center": 0.5,
             "y_center": 0.5, "width": 0.3, "height": 0.4},
        ]
        result = self.service.get_frame_annotations(fid)
        assert len(result) == 1

    def test_save_annotations_exports_yolo_labels(self) -> None:
        """YOLO .txt is uploaded to storage after saving annotations."""
        fid = uuid4()
        frame = {
            "id": str(fid),
            "filename": "frames/user1/vid1/frame_0001.jpg",
        }
        self.frame_repo.get_by_id.return_value = frame
        self.annotation_repo.save_batch.return_value = 1

        annotations = [
            {"class_id": 0, "class_name": "helmet", "module_code": "epi",
             "x_center": 0.5, "y_center": 0.5, "width": 0.3, "height": 0.4},
        ]

        from unittest.mock import patch
        mock_storage = MagicMock()
        with patch("app.infrastructure.storage.local_storage.get_storage",
                   return_value=mock_storage):
            result = self.service.save_annotations(fid, annotations)

        assert result == 1
        mock_storage.upload_bytes.assert_called_once()
        call_args = mock_storage.upload_bytes.call_args
        label_key = call_args[0][0]
        label_content = call_args[0][1].decode("utf-8")

        assert label_key == "labels/user1/vid1/frame_0001.txt"
        assert label_content == "0 0.500000 0.500000 0.300000 0.400000"

    def test_save_annotations_yolo_key_derivation_no_ext(self) -> None:
        """Label key derivation works when frame has no extension."""
        fid = uuid4()
        frame = {"id": str(fid), "filename": "frames/u/v/frame_no_ext"}
        self.frame_repo.get_by_id.return_value = frame
        self.annotation_repo.save_batch.return_value = 1

        from unittest.mock import patch
        mock_storage = MagicMock()
        with patch("app.infrastructure.storage.local_storage.get_storage",
                   return_value=mock_storage):
            self.service.save_annotations(fid, [
                {"class_id": 1, "class_name": "no_helmet", "module_code": "epi",
                 "x_center": 0.1, "y_center": 0.2, "width": 0.3, "height": 0.4},
            ])

        call_args = mock_storage.upload_bytes.call_args
        label_key = call_args[0][0]
        assert "labels/" in label_key

    def test_save_annotations_accepts_tenant_custom_class(self) -> None:
        """Bug corrigido: classe custom criada pelo tenant (yolo_classes) é
        aceita no save, união catálogo∪tenant (class_namespace)."""
        fid = uuid4()
        tenant_id = str(uuid4())
        self.frame_repo.get_by_id_and_user.return_value = {"id": fid}
        self.annotation_repo.get_classes_for_tenant.return_value = [
            {"id": 10, "name": "Protetor Auricular", "color": "#f59e0b"},
        ]
        self.annotation_repo.save_batch.return_value = 1
        class_id = namespace_tenant_class_id(10)
        annotations = [
            {"class_id": class_id, "class_name": "Protetor Auricular", "module_code": "epi",
             "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2},
        ]
        result = self.service.save_annotations(fid, annotations, uuid4(), tenant_id)
        assert result == 1
        self.annotation_repo.get_classes_for_tenant.assert_called_once_with(
            tenant_id, module_code="epi"
        )

    def test_save_annotations_rejects_class_from_other_tenant(self) -> None:
        """Uma classe custom que pertence a OUTRO tenant nunca entra no set
        válido (query já escopada por tenant_id do contexto) — cross-tenant
        continua rejeitado (C-01), mesmo com o id namespaced correto."""
        fid = uuid4()
        tenant_id = str(uuid4())
        self.frame_repo.get_by_id_and_user.return_value = {"id": fid}
        # Simula o request escopado pro tenant atual: a classe de outro
        # tenant nunca aparece nesta consulta.
        self.annotation_repo.get_classes_for_tenant.return_value = []
        class_id = namespace_tenant_class_id(999)  # id de classe de outro tenant
        annotations = [
            {"class_id": class_id, "class_name": "Classe de Outro Tenant", "module_code": "epi",
             "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2},
        ]
        with pytest.raises(ValidationError, match="não existe no módulo"):
            self.service.save_annotations(fid, annotations, uuid4(), tenant_id)

    def test_save_annotations_without_tenant_id_never_queries_tenant_classes(self) -> None:
        """tenant_id ausente (uso interno/Celery) → só o catálogo global é
        considerado, sem query extra em yolo_classes."""
        fid = uuid4()
        self.frame_repo.get_by_id.return_value = {"id": fid}
        annotations = [
            {"class_id": 0, "class_name": "helmet", "module_code": "epi",
             "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2},
        ]
        self.annotation_repo.save_batch.return_value = 1
        result = self.service.save_annotations(fid, annotations)
        assert result == 1
        self.annotation_repo.get_classes_for_tenant.assert_not_called()

    def test_export_yolo_labels_storage_error_is_swallowed(self) -> None:
        """Storage failures in export don't propagate."""
        fid = uuid4()
        frame = {"id": str(fid), "filename": "frames/u/v/frame.jpg"}
        self.frame_repo.get_by_id.return_value = frame
        self.annotation_repo.save_batch.return_value = 1

        from unittest.mock import patch
        mock_storage = MagicMock()
        mock_storage.upload_bytes.side_effect = RuntimeError("S3 error")
        with patch("app.infrastructure.storage.local_storage.get_storage",
                   return_value=mock_storage):
            result = self.service.save_annotations(fid, [
                {"class_id": 0, "class_name": "helmet", "module_code": "epi",
                 "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.3},
            ])
        assert result == 1
