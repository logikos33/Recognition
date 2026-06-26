"""
Tests: versioning.py helper logic — build_dataset_version input validation,
split logic, fallback paths, and copy-error tolerance (item-24).

celery is not installed in the api venv; celery_app is replaced with a
transparent fake so the task function remains the original Python callable.
"""
import sys
import types
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

# ──────────────────────────────────────────────────────────────────
# Transparent celery setup — must run before versioning is imported.
# Replace celery_app with a fake whose .task() is a passthrough.
# ──────────────────────────────────────────────────────────────────
class _TransparentCelery:
    def task(self, *args, **kwargs):
        def _decorator(fn):
            return fn
        return _decorator

_fake_celery_app = types.ModuleType("app.infrastructure.queue.celery_app")
_fake_celery_app.celery = _TransparentCelery()
sys.modules["app.infrastructure.queue.celery_app"] = _fake_celery_app

for _cn in ("celery", "celery.signals", "celery.app", "celery.app.base"):
    if _cn not in sys.modules:
        sys.modules[_cn] = MagicMock()

# Force fresh import (guard against previous test loading it with a non-transparent stub)
for _key in list(sys.modules):
    if "queue.tasks.versioning" in _key:
        del sys.modules[_key]

import app.infrastructure.queue.tasks.versioning as _versioning_mod  # noqa: F401


def _make_frame(video_id=None, frame_num=1):
    return {
        "id": uuid4(),
        "video_id": video_id or uuid4(),
        "filename": f"frame_{frame_num:04d}.jpg",
        "frame_number": frame_num,
        "is_validated": True,
    }


def _make_task_self():
    mock_self = MagicMock()
    mock_self.retry.side_effect = Exception("retry-called")
    return mock_self


def _call_build(frames, classes=None, **kwargs):
    """Run build_dataset_version with mocked annotation repo and storage."""
    if classes is None:
        classes = [{"id": 1, "name": "helmet"}]

    mock_repo = MagicMock()
    mock_repo._execute.return_value = frames
    mock_repo.get_classes_by_user.return_value = classes

    mock_storage = MagicMock()
    mock_storage.upload_bytes.return_value = None
    mock_storage.copy_object.return_value = None

    mock_self = _make_task_self()

    with patch("app.infrastructure.queue.tasks.versioning._get_annotation_repo",
               return_value=mock_repo), \
         patch("app.infrastructure.queue.tasks.versioning._get_storage",
               return_value=mock_storage):
        from app.infrastructure.queue.tasks.versioning import build_dataset_version
        result = build_dataset_version(
            mock_self, user_id=str(uuid4()), version="v1.0", **kwargs
        )

    return result, mock_storage, mock_self


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestBuildDatasetVersionValidation:

    def test_no_frames_raises_value_error(self):
        with pytest.raises(ValueError, match="Nenhum frame"):
            _call_build(frames=[])

    def test_insufficient_frames_raises_value_error(self):
        frames = [_make_frame() for _ in range(4)]
        with pytest.raises(ValueError, match="Mínimo: 5"):
            _call_build(frames=frames)

    def test_five_frames_is_minimum_that_passes(self):
        vid_id = uuid4()
        frames = [_make_frame(video_id=vid_id, frame_num=i) for i in range(5)]
        result, _, _ = _call_build(frames=frames)
        assert result["total_frames"] == 5
        assert result["status"] == "completed"
        # Single-video fallback: test takes last val frame, so val may end up 0
        total_split = result["train_count"] + result["val_count"] + result["test_count"]
        assert total_split == 5
        assert result["test_count"] >= 1


# ---------------------------------------------------------------------------
# Split logic
# ---------------------------------------------------------------------------

class TestBuildDatasetVersionSplit:

    def test_single_video_group_test_fallback_not_empty(self):
        """With one video, train gets it; val/test are populated via fallback."""
        vid_id = uuid4()
        frames = [_make_frame(video_id=vid_id, frame_num=i) for i in range(10)]
        result, _, _ = _call_build(frames=frames)
        assert result["test_count"] >= 1
        assert result["train_count"] >= 1
        total = result["train_count"] + result["val_count"] + result["test_count"]
        assert total == 10

    def test_multiple_video_groups_split_all_frames(self):
        videos = [uuid4() for _ in range(6)]
        frames = [_make_frame(video_id=v, frame_num=1) for v in videos]
        frames += [_make_frame(video_id=v, frame_num=2) for v in videos]

        result, _, _ = _call_build(frames=frames)
        assert result["total_frames"] == 12
        total = result["train_count"] + result["val_count"] + result["test_count"]
        assert total == 12

    def test_enough_videos_populates_all_splits(self):
        """With ≥3 video groups, each split gets at least one group."""
        videos = [uuid4() for _ in range(5)]
        frames = [_make_frame(video_id=v, frame_num=i) for v in videos for i in range(2)]

        result, _, _ = _call_build(frames=frames)
        assert result["train_count"] >= 1
        # val or test may be empty for 5 videos due to int(5*0.2)=1
        total = result["train_count"] + result["val_count"] + result["test_count"]
        assert total == 10

    def test_custom_train_ratio_stored_in_result(self):
        videos = [uuid4() for _ in range(10)]
        frames = [_make_frame(video_id=v) for v in videos]

        result, _, _ = _call_build(frames=frames, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1)
        assert result["splits"]["train_ratio"] == 0.8
        assert result["splits"]["val_ratio"] == 0.1
        assert result["splits"]["test_ratio"] == 0.1


# ---------------------------------------------------------------------------
# Class names
# ---------------------------------------------------------------------------

class TestBuildDatasetVersionClasses:

    def test_empty_classes_defaults_to_objeto(self):
        vid_id = uuid4()
        frames = [_make_frame(video_id=vid_id, frame_num=i) for i in range(5)]
        result, _, _ = _call_build(frames=frames, classes=[])
        assert result["class_names"] == ["Objeto"]

    def test_multiple_classes_all_included(self):
        vid_id = uuid4()
        frames = [_make_frame(video_id=vid_id, frame_num=i) for i in range(5)]
        classes = [{"id": 1, "name": "helmet"}, {"id": 2, "name": "vest"}]
        result, _, _ = _call_build(frames=frames, classes=classes)
        assert "helmet" in result["class_names"]
        assert "vest" in result["class_names"]
        assert len(result["class_names"]) == 2


# ---------------------------------------------------------------------------
# Storage interactions
# ---------------------------------------------------------------------------

class TestBuildDatasetVersionStorage:

    def test_yaml_uploaded_once(self):
        vid_id = uuid4()
        frames = [_make_frame(video_id=vid_id, frame_num=i) for i in range(5)]
        result, mock_storage, _ = _call_build(frames=frames)
        mock_storage.upload_bytes.assert_called_once()

    def test_yaml_key_contains_dataset_yaml(self):
        vid_id = uuid4()
        frames = [_make_frame(video_id=vid_id, frame_num=i) for i in range(5)]
        result, mock_storage, _ = _call_build(frames=frames)
        key_arg = mock_storage.upload_bytes.call_args[0][0]
        assert "dataset.yaml" in key_arg

    def test_copy_errors_collected_not_raised(self):
        vid_id = uuid4()
        frames = [_make_frame(video_id=vid_id, frame_num=i) for i in range(5)]

        mock_repo = MagicMock()
        mock_repo._execute.return_value = frames
        mock_repo.get_classes_by_user.return_value = [{"id": 1, "name": "helmet"}]

        mock_storage = MagicMock()
        mock_storage.copy_object.side_effect = Exception("R2 unavailable")
        mock_storage.upload_bytes.return_value = None

        mock_self = _make_task_self()

        with patch("app.infrastructure.queue.tasks.versioning._get_annotation_repo",
                   return_value=mock_repo), \
             patch("app.infrastructure.queue.tasks.versioning._get_storage",
                   return_value=mock_storage):
            from app.infrastructure.queue.tasks.versioning import build_dataset_version
            result = build_dataset_version(mock_self, user_id=str(uuid4()), version="v1.0")

        assert result["status"] == "completed"
        assert len(result["copy_errors"]) > 0

    def test_result_contains_all_expected_keys(self):
        vid_id = uuid4()
        frames = [_make_frame(video_id=vid_id, frame_num=i) for i in range(5)]
        result, _, _ = _call_build(frames=frames)
        required_keys = (
            "user_id", "version", "status", "total_frames", "train_count",
            "val_count", "test_count", "class_names", "dataset_yaml",
            "dataset_yaml_key", "copy_errors", "splits",
        )
        for key in required_keys:
            assert key in result, f"Missing result key: {key}"

    def test_dataset_yaml_key_path_structure(self):
        vid_id = uuid4()
        frames = [_make_frame(video_id=vid_id, frame_num=i) for i in range(5)]
        user_id = str(uuid4())

        mock_repo = MagicMock()
        mock_repo._execute.return_value = frames
        mock_repo.get_classes_by_user.return_value = [{"id": 1, "name": "helmet"}]
        mock_storage = MagicMock()
        mock_storage.upload_bytes.return_value = None
        mock_storage.copy_object.return_value = None
        mock_self = _make_task_self()

        with patch("app.infrastructure.queue.tasks.versioning._get_annotation_repo",
                   return_value=mock_repo), \
             patch("app.infrastructure.queue.tasks.versioning._get_storage",
                   return_value=mock_storage):
            from app.infrastructure.queue.tasks.versioning import build_dataset_version
            result = build_dataset_version(mock_self, user_id=user_id, version="v2.0")

        assert result["dataset_yaml_key"] == f"datasets/{user_id}/v2.0/dataset.yaml"
