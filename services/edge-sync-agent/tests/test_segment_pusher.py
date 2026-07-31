"""Tests for segment_pusher: contrato multipart do push + cache de reenvio."""

import pytest

from app.live_view.segment_pusher import (
    PushedFileCache,
    SegmentPushError,
    push_segment,
)

_CAMERA = "44444444-4444-4444-4444-444444444444"


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


class _FakeHttpClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls: list[dict] = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self._response


class _RaisingHttpClient:
    def post(self, *args, **kwargs):
        raise ConnectionError("connection refused")


def test_successful_push_targets_live_view_endpoint():
    client = _FakeHttpClient(_FakeResponse(201))

    push_segment(client, "https://api.example/", "tok", _CAMERA, "segment3.ts", b"\x47ts")

    call = client.calls[0]
    assert call["url"] == f"https://api.example/api/v1/edge/live-view/{_CAMERA}/segment"
    assert call["headers"]["Authorization"] == "Bearer tok"
    assert call["data"]["filename"] == "segment3.ts"
    assert call["files"]["file"] == ("segment3.ts", b"\x47ts", "video/mp2t")


def test_playlist_push_uses_m3u8_content_type():
    client = _FakeHttpClient(_FakeResponse(201))
    push_segment(client, "https://api.example", "tok", _CAMERA, "stream.m3u8", b"#EXTM3U")
    assert client.calls[0]["files"]["file"][2] == "application/vnd.apple.mpegurl"


def test_non_201_raises_push_error():
    client = _FakeHttpClient(_FakeResponse(422, text="filename inválido"))
    with pytest.raises(SegmentPushError, match="422"):
        push_segment(client, "https://api.example", "tok", _CAMERA, "bad", b"x")


def test_network_error_raises_push_error():
    with pytest.raises(SegmentPushError):
        push_segment(_RaisingHttpClient(), "https://api.example", "tok", _CAMERA, "s.ts", b"x")


# ── PushedFileCache ─────────────────────────────────────────────────────────


def test_unchanged_playlist_is_not_repushed(tmp_path):
    """Custo por request: a API roda com 1 worker + --max-requests, então
    tráfego contínuo recicla o worker. A playlist muda a cada ~2s e o TTL na
    nuvem é 20s — reenviar só na mudança tem margem de sobra."""
    cache = PushedFileCache()
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text("#EXTM3U\nsegment1.ts\n")

    assert cache.should_push(playlist) is True
    cache.mark_pushed(playlist)
    assert cache.should_push(playlist) is False


def test_changed_playlist_is_repushed(tmp_path):
    """Segmento novo entrou na playlist -> precisa subir, senão o player não
    enxerga o segmento seguinte."""
    cache = PushedFileCache()
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text("#EXTM3U\nsegment1.ts\n")
    cache.mark_pushed(playlist)

    playlist.write_text("#EXTM3U\nsegment1.ts\nsegment2.ts\n")

    assert cache.should_push(playlist) is True


def test_unchanged_segment_is_not_repushed(tmp_path):
    cache = PushedFileCache()
    seg = tmp_path / "segment1.ts"
    seg.write_bytes(b"data")

    assert cache.should_push(seg) is True
    cache.mark_pushed(seg)
    assert cache.should_push(seg) is False


def test_changed_segment_is_repushed(tmp_path):
    """FFmpeg pode reciclar o nome com conteúdo novo — tamanho diferente
    precisa subir de novo."""
    cache = PushedFileCache()
    seg = tmp_path / "segment1.ts"
    seg.write_bytes(b"data")
    cache.mark_pushed(seg)

    seg.write_bytes(b"completely different content")

    assert cache.should_push(seg) is True


def test_missing_file_is_not_pushed(tmp_path):
    cache = PushedFileCache()
    assert cache.should_push(tmp_path / "gone.ts") is False


def test_forget_all_clears_cache(tmp_path):
    cache = PushedFileCache()
    seg = tmp_path / "segment1.ts"
    seg.write_bytes(b"data")
    cache.mark_pushed(seg)
    assert cache.should_push(seg) is False

    cache.forget_all()

    assert cache.should_push(seg) is True


def test_cache_is_capped(tmp_path):
    cache = PushedFileCache(max_entries=4)
    for i in range(20):
        seg = tmp_path / f"segment{i}.ts"
        seg.write_bytes(b"x")
        cache.mark_pushed(seg)
    assert len(cache._seen) <= 4
