"""Tests for stream_rtsp_clip: subprocess wiring, chunking, and error paths.

Uses a fake Popen (no real ffmpeg invoked) — proves the plumbing, not
ffmpeg's actual behavior against a real RTSP source (no hardware available,
documented in the module docstring).
"""

import io

import pytest

from app.recorder_client import RecorderError
from app.rtsp_clip_stream import stream_rtsp_clip

_VALID_URL = "rtsp://10.0.0.5:554/cam/playback?channel=1&starttime=x&endtime=y"


class _FakeStdout:
    def __init__(self, chunks: list[bytes]) -> None:
        self._buffer = io.BytesIO(b"".join(chunks))

    def read(self, size: int) -> bytes:
        return self._buffer.read(size)


class _FakeProc:
    def __init__(self, chunks: list[bytes], stderr: bytes = b"") -> None:
        self.stdout = _FakeStdout(chunks)
        self.stderr = io.BytesIO(stderr)
        self._terminated = False
        self._poll_result = None

    def poll(self):
        return self._poll_result

    def terminate(self):
        self._terminated = True
        self._poll_result = 0

    def wait(self, timeout=None):
        return 0


def _fake_popen_factory(chunks: list[bytes], stderr: bytes = b""):
    def _popen(cmd, **kwargs):
        return _FakeProc(chunks, stderr=stderr)

    return _popen


def test_streams_chunks_from_ffmpeg_stdout():
    popen = _fake_popen_factory([b"mp4-bytes-1", b"mp4-bytes-2"])
    chunks = list(stream_rtsp_clip(_VALID_URL, duration_seconds=5.0, popen=popen))
    assert b"".join(chunks) == b"mp4-bytes-1mp4-bytes-2"


def test_invalid_url_raises_before_spawning_process():
    calls = []

    def _popen(cmd, **kwargs):
        calls.append(cmd)
        return _FakeProc([b"x"])

    with pytest.raises(RecorderError):
        list(stream_rtsp_clip("ftp://bad-scheme/cam", duration_seconds=5.0, popen=_popen))
    assert calls == []


def test_non_positive_duration_rejected():
    def _popen(cmd, **kwargs):
        raise AssertionError("ffmpeg should never be spawned for a bad duration")

    with pytest.raises(RecorderError):
        list(stream_rtsp_clip(_VALID_URL, duration_seconds=0, popen=_popen))


def test_ffmpeg_missing_binary_raises_recorder_error():
    def _popen(cmd, **kwargs):
        raise OSError("No such file or directory: 'ffmpeg'")

    with pytest.raises(RecorderError):
        list(stream_rtsp_clip(_VALID_URL, duration_seconds=5.0, popen=_popen))


def test_empty_output_raises_recorder_error_with_stderr_tail():
    popen = _fake_popen_factory([], stderr=b"Connection refused")
    with pytest.raises(RecorderError, match="Connection refused"):
        list(stream_rtsp_clip(_VALID_URL, duration_seconds=5.0, popen=popen))


def test_credentials_never_appear_in_raised_error_message():
    url = "rtsp://admin:s3cr3t@10.0.0.5:554/cam/playback"

    def _popen(cmd, **kwargs):
        raise OSError("boom")

    with pytest.raises(RecorderError) as exc_info:
        list(stream_rtsp_clip(url, duration_seconds=5.0, popen=_popen))
    assert "s3cr3t" not in str(exc_info.value)
