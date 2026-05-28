"""Tests: AnnotationService."""
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.services.annotation_service import AnnotationService


class TestAnnotationService:
    """Testes para AnnotationService."""

    def setup_method(self) -> None:
        self.annotation_repo = MagicMock()
        self.frame_repo = MagicMock()
        self.service = AnnotationService(self.annotation_repo, self.frame_repo)

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
            {"class_id": 1, "x_center": 0.5, "y_center": 0.5,
             "width": 0.3, "height": 0.4},
            {"class_id": 2, "x_center": 0.2, "y_center": 0.8,
             "width": 0.1, "height": 0.2},
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
            {"class_id": 1, "x_center": 1.5, "y_center": 0.5,
             "width": 0.3, "height": 0.4},
        ]
        with pytest.raises(ValidationError, match="entre 0 e 1"):
            self.service.save_annotations(fid, annotations)

    def test_save_annotations_missing_field(self) -> None:
        fid = uuid4()
        self.frame_repo.get_by_id.return_value = {"id": fid}
        annotations = [{"class_id": 1, "x_center": 0.5}]
        with pytest.raises(ValidationError, match="obrigatório"):
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
            {"class_id": 0, "x_center": 0.5, "y_center": 0.5,
             "width": 0.3, "height": 0.4},
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
                {"class_id": 1, "x_center": 0.1, "y_center": 0.2,
                 "width": 0.3, "height": 0.4},
            ])

        call_args = mock_storage.upload_bytes.call_args
        label_key = call_args[0][0]
        assert "labels/" in label_key

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
                {"class_id": 0, "x_center": 0.5, "y_center": 0.5,
                 "width": 0.2, "height": 0.3},
            ])
        assert result == 1
