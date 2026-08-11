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

    def test_training_pipeline_prefixes(self) -> None:
        from app.constants import R2Prefix
        assert R2Prefix.TRAINING_IMAGES == "training-images"
        assert R2Prefix.DATASET_EXPORTS == "dataset-exports"


class TestFrameSource:
    def test_values_match_check_094(self) -> None:
        from app.constants import FrameSource
        assert FrameSource.VIDEO == "video"
        assert FrameSource.UPLOAD == "upload"
        assert FrameSource.AUTO == "auto"
        assert FrameSource.NVR == "nvr"
        # CHECK chk_training_frames_source: ('auto', 'nvr', 'upload', 'video')
        assert {s.value for s in FrameSource} == {"auto", "nvr", "upload", "video"}

    def test_is_string_enum(self) -> None:
        from app.constants import FrameSource
        assert isinstance(FrameSource.VIDEO, str)


class TestDatasetVersionStatus:
    def test_values(self) -> None:
        from app.constants import DatasetVersionStatus
        assert DatasetVersionStatus.BUILDING == "building"
        assert DatasetVersionStatus.READY == "ready"
        assert DatasetVersionStatus.ERROR == "error"


class TestExportFormat:
    def test_values(self) -> None:
        from app.constants import ExportFormat
        assert ExportFormat.COCO == "coco"
        assert ExportFormat.YOLO == "yolo"


class TestFramework:
    def test_values(self) -> None:
        from app.constants import Framework
        assert Framework.RFDETR == "rfdetr"
        assert Framework.YOLOX == "yolox"
        assert Framework.ULTRALYTICS == "ultralytics"


class TestGpuProvider:
    def test_values(self) -> None:
        from app.constants import GpuProvider
        assert GpuProvider.RUNPOD == "runpod"
        assert GpuProvider.VAST_AI == "vast_ai"
        assert GpuProvider.COLAB == "colab"
        assert GpuProvider.LOCAL == "local"
        assert GpuProvider.EDGE == "edge"


class TestEvalVerdict:
    def test_values_match_check_101(self) -> None:
        from app.constants import EvalVerdict
        # CHECK chk_model_evaluations_verdict: ('pending', 'promote', 'reject')
        assert {v.value for v in EvalVerdict} == {"pending", "promote", "reject"}


class TestRecorderProtocol:
    def test_values_match_check_099(self) -> None:
        from app.constants import RecorderProtocol
        # CHECK chk_recorders_protocol
        assert {p.value for p in RecorderProtocol} == {
            "onvif", "hikvision", "dahua", "intelbras", "rtsp",
        }


class TestRecorderStatus:
    def test_values_match_check_099(self) -> None:
        from app.constants import RecorderStatus
        # CHECK chk_recorders_status
        assert {s.value for s in RecorderStatus} == {
            "unknown", "online", "offline", "error",
        }


class TestDeploymentStatus:
    def test_values_match_check_100(self) -> None:
        from app.constants import DeploymentStatus
        assert DeploymentStatus.ACTIVE == "active"
        assert DeploymentStatus.INACTIVE == "inactive"
        # CHECK chk_model_deployments_status inclui 'rolled_back'
        assert DeploymentStatus.ROLLED_BACK == "rolled_back"


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
