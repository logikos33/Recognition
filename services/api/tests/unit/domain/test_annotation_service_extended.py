"""
Tests: AnnotationService — get_frame_annotations (pre-annotation fallback),
save_annotations paths e _validate_annotation (item-24).

Complementa test_annotation_service.py com os caminhos não cobertos.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.domain.services.annotation_service import AnnotationService


class TestAnnotationServiceExtended:

    def setup_method(self):
        self.annotation_repo = MagicMock()
        self.frame_repo = MagicMock()
        self.service = AnnotationService(self.annotation_repo, self.frame_repo)

    def _frame(self, frame_id=None, filename="frames/u/v/frame_0001.jpg"):
        return {"id": frame_id or uuid4(), "filename": filename, "is_annotated": False}

    # ------------------------------------------------------------------
    # get_frame_annotations — with user_id IDOR check
    # ------------------------------------------------------------------

    def test_get_frame_annotations_user_owns_frame(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = [
            {"id": uuid4(), "class_id": 1, "x_center": 0.5, "y_center": 0.5}
        ]

        result = self.service.get_frame_annotations(frame_id, user_id)
        assert len(result) == 1
        assert isinstance(result[0]["id"], str)

    def test_get_frame_annotations_user_not_owner_raises(self):
        self.frame_repo.get_by_id_and_user.return_value = None
        with pytest.raises(NotFoundError):
            self.service.get_frame_annotations(uuid4(), uuid4())

    def test_get_frame_annotations_no_user_skips_idor_check(self):
        frame_id = uuid4()
        self.annotation_repo.get_by_frame.return_value = [{"id": uuid4(), "class_id": 1}]
        result = self.service.get_frame_annotations(frame_id, user_id=None)
        self.frame_repo.get_by_id_and_user.assert_not_called()
        assert len(result) == 1

    # ------------------------------------------------------------------
    # get_frame_annotations — pre-annotation fallback (AI)
    # ------------------------------------------------------------------

    def test_get_frame_annotations_returns_pre_annotations_when_no_human(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = []  # no human annotations
        self.annotation_repo.get_classes_by_user.return_value = [
            {"id": 1, "name": "helmet", "color": "#0f0"}
        ]
        self.frame_repo.get_pre_annotations.return_value = [
            {"class": "helmet", "bbox": [0.5, 0.5, 0.2, 0.2], "confidence": 0.9}
        ]

        result = self.service.get_frame_annotations(frame_id, user_id)
        assert len(result) == 1
        assert result[0]["source"] == "ai"
        assert result[0]["class_name"] == "helmet"
        assert result[0]["class_id"] == 1

    def test_get_frame_annotations_pre_annotation_dict_bbox(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = []
        self.annotation_repo.get_classes_by_user.return_value = []
        self.frame_repo.get_pre_annotations.return_value = [
            {"class": "vest", "bbox": {"cx": 0.5, "cy": 0.5, "w": 0.1, "h": 0.1}, "confidence": 0.8}
        ]

        result = self.service.get_frame_annotations(frame_id, user_id)
        assert len(result) == 1
        assert result[0]["x_center"] == 0.5
        assert result[0]["class_id"] == 1  # fallback to 1 when no classes

    def test_get_frame_annotations_invalid_bbox_is_skipped(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = []
        self.annotation_repo.get_classes_by_user.return_value = []
        self.frame_repo.get_pre_annotations.return_value = [
            {"class": "helmet", "bbox": "not-a-bbox", "confidence": 0.9}
        ]

        result = self.service.get_frame_annotations(frame_id, user_id)
        assert result == []

    def test_get_frame_annotations_no_pre_annotations_returns_empty(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = []
        self.frame_repo.get_pre_annotations.return_value = []

        result = self.service.get_frame_annotations(frame_id, user_id)
        assert result == []

    def test_get_frame_annotations_class_not_in_map_uses_fallback(self):
        frame_id = uuid4()
        user_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.get_by_frame.return_value = []
        self.annotation_repo.get_classes_by_user.return_value = [
            {"id": 99, "name": "known_class", "color": "#fff"}
        ]
        self.frame_repo.get_pre_annotations.return_value = [
            {"class": "unknown_label", "bbox": [0.5, 0.5, 0.1, 0.1], "confidence": 0.7}
        ]

        result = self.service.get_frame_annotations(frame_id, user_id)
        assert len(result) == 1
        assert result[0]["class_id"] == 99  # first available class

    # ------------------------------------------------------------------
    # save_annotations
    # ------------------------------------------------------------------

    # _export_yolo_labels does `from app.infrastructure.storage.local_storage import get_storage`
    # inside the function body. Patch at source module to intercept it.
    _STORAGE_PATH = "app.infrastructure.storage.local_storage.get_storage"

    def test_save_annotations_with_user_id(self):
        frame_id = uuid4()
        user_id = uuid4()
        frame = self._frame(frame_id)
        self.frame_repo.get_by_id_and_user.return_value = frame
        self.annotation_repo.save_batch.return_value = 2

        ann = [
            {"class_id": 1, "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2},
            {"class_id": 2, "x_center": 0.3, "y_center": 0.3, "width": 0.1, "height": 0.1},
        ]
        with patch(self._STORAGE_PATH):
            count = self.service.save_annotations(frame_id, ann, user_id)

        assert count == 2
        self.frame_repo.mark_annotated.assert_called_once_with(frame_id)

    def test_save_annotations_without_user_id_uses_get_by_id(self):
        frame_id = uuid4()
        frame = self._frame(frame_id)
        self.frame_repo.get_by_id.return_value = frame
        self.annotation_repo.save_batch.return_value = 1

        ann = [{"class_id": 1, "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2}]
        with patch(self._STORAGE_PATH):
            self.service.save_annotations(frame_id, ann, user_id=None)

        self.frame_repo.get_by_id.assert_called_once_with(frame_id)

    def test_save_annotations_frame_not_found_raises(self):
        self.frame_repo.get_by_id_and_user.return_value = None
        with pytest.raises(NotFoundError):
            self.service.save_annotations(uuid4(), [], uuid4())

    def test_save_annotations_zero_count_does_not_mark_annotated(self):
        frame_id = uuid4()
        self.frame_repo.get_by_id_and_user.return_value = self._frame(frame_id)
        self.annotation_repo.save_batch.return_value = 0

        self.service.save_annotations(frame_id, [], uuid4())
        self.frame_repo.mark_annotated.assert_not_called()

    # ------------------------------------------------------------------
    # _validate_annotation
    # ------------------------------------------------------------------

    def test_validate_annotation_missing_class_id_raises(self):
        with pytest.raises(ValidationError, match="class_id"):
            self.service._validate_annotation(
                {"x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2}
            )

    def test_validate_annotation_coord_out_of_range_raises(self):
        with pytest.raises(ValidationError, match="entre 0 e 1"):
            self.service._validate_annotation(
                {"class_id": 1, "x_center": 1.5, "y_center": 0.5, "width": 0.2, "height": 0.2}
            )

    def test_validate_annotation_valid_passes(self):
        self.service._validate_annotation(
            {"class_id": 1, "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2}
        )  # no exception

    # ------------------------------------------------------------------
    # _export_yolo_labels — best-effort, storage error silenced
    # ------------------------------------------------------------------

    def test_export_yolo_labels_storage_error_is_silenced(self):
        frame = self._frame(filename="frames/u/v/frame_001.jpg")
        ann = [{"class_id": 1, "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.2}]

        with patch(self._STORAGE_PATH) as mock_gs:
            mock_gs.return_value.upload_bytes.side_effect = Exception("R2 error")
            # Should not raise — _export_yolo_labels is best-effort
            self.service._export_yolo_labels(frame, ann)
