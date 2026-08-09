"""Tests for segment_pusher: contrato multipart do push + cache de reenvio."""

import os

import pytest

from app.live_view.segment_pusher import (
    PushedFileCache,
    SegmentPushError,
    push_segment,
)


def _settled(path, data=b"data"):
    """Escreve e envelhece o mtime: segmento só sobe depois de assentar
    (_SETTLE_SECONDS), pra não subir .ts que o ffmpeg ainda está fechando."""
    path.write_bytes(data)
    st = path.stat()
    os.utime(path, (st.st_atime, st.st_mtime - 5))
    return path


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
    seg = _settled(tmp_path / "segment1.ts")

    assert cache.should_push(seg) is True
    cache.mark_pushed(seg)
    assert cache.should_push(seg) is False


def test_changed_segment_is_repushed(tmp_path):
    """FFmpeg pode reciclar o nome com conteúdo novo — tamanho diferente
    precisa subir de novo."""
    cache = PushedFileCache()
    seg = _settled(tmp_path / "segment1.ts")
    cache.mark_pushed(seg)

    _settled(seg, b"completely different content")

    assert cache.should_push(seg) is True


def test_missing_file_is_not_pushed(tmp_path):
    cache = PushedFileCache()
    assert cache.should_push(tmp_path / "gone.ts") is False


def test_forget_all_clears_cache(tmp_path):
    cache = PushedFileCache()
    seg = _settled(tmp_path / "segment1.ts")
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


def test_hot_segment_is_not_pushed_yet(tmp_path):
    """Duplicação medida em campo: o ffmpeg registra o .ts na playlist e AINDA
    anexa os últimos bytes. stream77.ts subiu com 276729 e depois 276760 (31
    bytes a mais) — mesmo segmento, dois pushes."""
    cache = PushedFileCache()
    seg = tmp_path / "segment1.ts"
    seg.write_bytes(b"ainda escrevendo")

    # recém-escrito -> ainda não subiu
    assert cache.should_push(seg) is False


def test_settled_segment_is_pushed(tmp_path):
    cache = PushedFileCache()
    seg = tmp_path / "segment1.ts"
    seg.write_bytes(b"fechado")
    import os as _os
    stat = seg.stat()
    _os.utime(seg, (stat.st_atime, stat.st_mtime - 5))  # envelhece 5s

    assert cache.should_push(seg) is True


def test_playlist_is_not_subject_to_settle_delay(tmp_path):
    """A playlist é pequena/atômica e precisa subir assim que muda, senão o
    player não enxerga o segmento novo."""
    cache = PushedFileCache()
    pl = tmp_path / "stream.m3u8"
    pl.write_text("#EXTM3U\nsegment1.ts\n")

    assert cache.should_push(pl) is True


# ── has_pushed / should_push_content / mark_pushed_content ─────────────────
#
# Playlist consistente por construção: o que sobe pode ser um TRUNCAMENTO do
# arquivo em disco, então a dedupe da playlist não pode usar (mtime, size)
# do arquivo — usa um digest do CONTEÚDO efetivamente empurrado.


def test_has_pushed_false_for_unknown_name():
    cache = PushedFileCache()
    assert cache.has_pushed("segment1.ts") is False


def test_has_pushed_true_after_mark_pushed(tmp_path):
    """`.ts` marcado via `mark_pushed` (assinatura mtime/size) também conta
    pra `has_pushed` — é o sinal que o caller usa pra montar o prefixo da
    playlist truncada."""
    cache = PushedFileCache()
    seg = _settled(tmp_path / "segment1.ts")
    cache.mark_pushed(seg)
    assert cache.has_pushed("segment1.ts") is True


def test_has_pushed_true_after_mark_pushed_content():
    cache = PushedFileCache()
    cache.mark_pushed_content("stream.m3u8", "deadbeef")
    assert cache.has_pushed("stream.m3u8") is True


def test_should_push_content_true_for_new_digest():
    cache = PushedFileCache()
    assert cache.should_push_content("stream.m3u8", "abc123") is True


def test_should_push_content_false_for_same_digest():
    cache = PushedFileCache()
    cache.mark_pushed_content("stream.m3u8", "abc123")
    assert cache.should_push_content("stream.m3u8", "abc123") is False


def test_should_push_content_true_when_digest_changes():
    cache = PushedFileCache()
    cache.mark_pushed_content("stream.m3u8", "abc123")
    assert cache.should_push_content("stream.m3u8", "def456") is True


def test_content_signature_never_collides_with_mtime_size_signature(tmp_path):
    """(mtime, size) do `.ts` e ("sha256", digest) da playlist convivem no
    mesmo dict `_seen` sem colidir — mesmo em cenários adversariais (mtime
    pequeno, size pequeno) o formato distinto ("sha256", ...) não pode ser
    confundido com uma tupla (float, int)."""
    cache = PushedFileCache()
    seg = tmp_path / "segment1.ts"
    seg.write_bytes(b"x")
    st = seg.stat()
    os.utime(seg, (st.st_atime, st.st_mtime - 5))
    cache.mark_pushed(seg)

    # Mesmo nome nunca acontece na prática (um é .ts, outro .m3u8), mas o
    # ponto é a FORMA da assinatura, não o nome — usa o nome do segmento só
    # pra provar que não colide por acidente de tupla.
    assert cache.should_push_content("segment1.ts", "abc123") is True


def test_forget_all_clears_content_signatures_too():
    cache = PushedFileCache()
    cache.mark_pushed_content("stream.m3u8", "abc123")
    cache.forget_all()
    assert cache.has_pushed("stream.m3u8") is False
    assert cache.should_push_content("stream.m3u8", "abc123") is True


def test_content_cache_is_capped():
    cache = PushedFileCache(max_entries=4)
    for i in range(20):
        cache.mark_pushed_content(f"stream{i}.m3u8", f"digest{i}")
    assert len(cache._seen) <= 4
