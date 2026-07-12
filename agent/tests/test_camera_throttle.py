"""Tests — throttle de FPS por câmera no CameraStream (WS10).

O capture loop lê todo frame do RTSP (esvaziar buffer), mas só emite on_frame
no rate alvo. Simulamos 30 frames/s com relógio fake (monkeypatch em
time.monotonic) — sem cv2, sem rede.
"""
from unittest.mock import MagicMock

import src.camera_manager as camera_manager
from src.camera_manager import CameraManager, CameraStream
from src.config import CameraConfig


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _stream_with_clock(monkeypatch, fps: int):
    clock = FakeClock()
    monkeypatch.setattr(camera_manager.time, "monotonic", clock.monotonic)
    on_frame = MagicMock()
    stream = CameraStream("cam-1", "rtsp://x", on_frame, fps=fps)
    return stream, on_frame, clock


def test_fps_1_emits_about_once_per_second(monkeypatch):
    """30 frames/s simulados com fps=1 → ~1 emissão por segundo."""
    stream, on_frame, clock = _stream_with_clock(monkeypatch, fps=1)

    for _ in range(90):  # 3 segundos a 30 fps
        stream._maybe_emit("frame")
        clock.advance(1 / 30)

    assert 3 <= on_frame.call_count <= 4


def test_fps_5_emits_about_five_per_second(monkeypatch):
    stream, on_frame, clock = _stream_with_clock(monkeypatch, fps=5)

    for _ in range(30):  # 1 segundo a 30 fps
        stream._maybe_emit("frame")
        clock.advance(1 / 30)

    assert 5 <= on_frame.call_count <= 6


def test_fps_30_emits_every_frame(monkeypatch):
    stream, on_frame, clock = _stream_with_clock(monkeypatch, fps=30)

    for _ in range(30):
        stream._maybe_emit("frame")
        clock.advance(1 / 30)

    assert on_frame.call_count == 30


def test_set_fps_applies_at_runtime(monkeypatch):
    """set_fps muda o throttle sem recriar o stream (comando da cloud)."""
    stream, on_frame, clock = _stream_with_clock(monkeypatch, fps=1)

    for _ in range(30):
        stream._maybe_emit("frame")
        clock.advance(1 / 30)
    count_at_1fps = on_frame.call_count
    assert count_at_1fps <= 2

    stream.set_fps(30)
    on_frame.reset_mock()
    for _ in range(30):
        stream._maybe_emit("frame")
        clock.advance(1 / 30)
    assert on_frame.call_count >= 29


def test_set_fps_clamps_to_minimum_1():
    stream = CameraStream("cam-1", "rtsp://x", MagicMock(), fps=5)
    stream.set_fps(0)
    assert stream.fps == 1
    stream.set_fps(-10)
    assert stream.fps == 1


def test_on_frame_receives_camera_id_and_frame(monkeypatch):
    stream, on_frame, _clock = _stream_with_clock(monkeypatch, fps=30)
    stream._maybe_emit("frame-xyz")
    on_frame.assert_called_once_with("cam-1", "frame-xyz")


def test_manager_update_camera_fps(monkeypatch):
    """CameraManager propaga fps e atualiza stream em runtime."""
    # start() vira no-op para não abrir thread/cv2
    monkeypatch.setattr(CameraStream, "start", lambda self: None)
    mgr = CameraManager()
    mgr.add_camera("cam-1", "rtsp://x", MagicMock(), fps=10)

    assert mgr._streams["cam-1"].fps == 10
    assert mgr.update_camera_fps("cam-1", 15) is True
    assert mgr._streams["cam-1"].fps == 15
    assert mgr.update_camera_fps("ghost", 15) is False


def test_camera_config_has_fps_default_5():
    cfg = CameraConfig(id="c1", name="Cam")
    assert cfg.fps == 5


def test_camera_config_accepts_fps_from_dict():
    """from_env_and_yaml filtra por __dataclass_fields__ — fps é aceito."""
    cfg = CameraConfig(**{"id": "c1", "name": "Cam", "fps": 15})
    assert cfg.fps == 15
