"""Tests: Constants and Enums — ensures all values importable and correct."""


class TestVideoStatus:
    def test_values(self) -> None:
        from app.constants import VideoStatus
        assert VideoStatus.PENDING == "pending"
        assert VideoStatus.UPLOADING == "uploading"
        assert VideoStatus.PROCESSING == "processing"
        assert VideoStatus.COMPLETED == "completed"
        assert VideoStatus.FAILED == "failed"

    def test_is_string_enum(self) -> None:
        from app.constants import VideoStatus
        assert isinstance(VideoStatus.PENDING, str)


class TestFrameStatus:
    def test_values(self) -> None:
        from app.constants import FrameStatus
        assert FrameStatus.RAW == "raw"
        assert FrameStatus.QUEUED == "queued"
        assert FrameStatus.ANNOTATED == "annotated"
        assert FrameStatus.REJECTED == "rejected"


class TestTrainingStatus:
    def test_values(self) -> None:
        from app.constants import TrainingStatus
        assert TrainingStatus.QUEUED == "queued"
        assert TrainingStatus.RUNNING == "running"
        assert TrainingStatus.COMPLETED == "completed"
        assert TrainingStatus.FAILED == "failed"
        assert TrainingStatus.STOPPED == "stopped"


class TestCameraStatus:
    def test_values(self) -> None:
        from app.constants import CameraStatus
        assert CameraStatus.INACTIVE == "inactive"
        assert CameraStatus.STARTING == "starting"
        assert CameraStatus.ACTIVE == "active"
        assert CameraStatus.ERROR == "error"


class TestUserRole:
    def test_values(self) -> None:
        from app.constants import UserRole
        assert UserRole.ADMIN == "admin"
        assert UserRole.OPERATOR == "operator"


class TestEpiClass:
    def test_values(self) -> None:
        from app.constants import EpiClass
        assert EpiClass.HELMET == "helmet"
        assert EpiClass.NO_HELMET == "no_helmet"
        assert EpiClass.VEST == "vest"
        assert EpiClass.NO_VEST == "no_vest"
        assert EpiClass.GLOVES == "gloves"
        assert EpiClass.NO_GLOVES == "no_gloves"
        assert EpiClass.SAFETY_GLASSES == "safety_glasses"
        assert EpiClass.NO_SAFETY_GLASSES == "no_safety_glasses"

    def test_is_string_enum(self) -> None:
        from app.constants import EpiClass
        assert isinstance(EpiClass.HELMET, str)


class TestTrainingPreset:
    def test_values(self) -> None:
        from app.constants import TrainingPreset
        assert TrainingPreset.FAST == "fast"
        assert TrainingPreset.BALANCED == "balanced"
        assert TrainingPreset.QUALITY == "quality"


class TestR2Prefix:
    def test_prefixes(self) -> None:
        from app.constants import R2Prefix
        assert R2Prefix.RAW_VIDEOS == "raw-videos"
        assert R2Prefix.FRAMES == "frames"
        assert R2Prefix.LABELS == "labels"
        assert R2Prefix.DATASETS == "datasets"
        assert R2Prefix.MODELS == "models"
        assert R2Prefix.EVIDENCE == "evidence"


class TestRedisChannel:
    def test_channels(self) -> None:
        from app.constants import RedisChannel
        assert "camera_id" in RedisChannel.DETECTION
        assert "job_id" in RedisChannel.TRAINING_PROGRESS
        assert "worker_id" in RedisChannel.WORKER_HEALTH
        assert RedisChannel.DETECTIONS == "epi:detections"
        assert RedisChannel.WORKERS_SET == "epi:workers"

    def test_format_detection_channel(self) -> None:
        from app.constants import RedisChannel
        channel = RedisChannel.DETECTION.format(camera_id="cam-123")
        assert channel == "det:cam-123"

    def test_format_training_channel(self) -> None:
        from app.constants import RedisChannel
        channel = RedisChannel.TRAINING_PROGRESS.format(job_id="job-456")
        assert channel == "training:job-456"
