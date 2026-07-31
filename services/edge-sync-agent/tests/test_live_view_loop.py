"""Tests for LiveViewLoop: supervisão do transcode + push dos segmentos."""

import threading

import pytest

from app.live_view.live_view_loop import (
    LiveViewLoop,
    _resolve_camera_urls,
    build_live_view_loop_from_env,
)
from app.live_view.segment_pusher import SegmentPushError
from app.recorder_client import RecorderError

_CAMERA = "cam-1"
_RTSP = "rtsp://admin:pw@10.0.0.9:554/cam/realmonitor?channel=1&subtype=1"


class _FakeTokenSource:
    def get_bearer(self, ttl_s: int = 300) -> str:
        return "fake-bearer"


class _FakeTranscoder:
    def __init__(self, files=None, running=True, stderr=""):
        self._files = files or []
        self._running = running
        self._stderr = stderr
        self.start_calls = 0
        self.stop_calls = 0

    def is_running(self):
        return self._running

    def start(self):
        self.start_calls += 1
        self._running = True

    def stop(self):
        self.stop_calls += 1

    def stderr_tail(self):
        return self._stderr

    def list_ready_files(self):
        return self._files


def _make_loop(transcoder, pushes, tmp_path, wanted=None, still_wanted=True):
    """wanted=None -> câmera COM espectador (caso comum dos testes de push).
    Passe wanted=[] para simular ninguém assistindo."""
    def _push(http, base, bearer, camera_id, filename, data):
        pushes.append({"camera_id": camera_id, "filename": filename, "data": data})
        return still_wanted

    def _fetch_wanted(http, base, bearer):
        return [_CAMERA] if wanted is None else list(wanted)

    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_push,
        fetch_wanted_fn=_fetch_wanted,
    )
    loop._transcoders[_CAMERA] = transcoder
    return loop


def test_tick_starts_transcoder_when_wanted(tmp_path):
    t = _FakeTranscoder(running=False)
    loop = _make_loop(t, [], tmp_path)
    loop.tick()
    assert t.start_calls == 1


# ── LV-3: sob demanda ───────────────────────────────────────────────────────


def test_no_viewer_never_starts_transcoder(tmp_path):
    """Ninguém assistindo -> nenhum FFmpeg sobe, nenhum segmento é empurrado.
    É o ponto do LV-3: sem espectador, custo zero."""
    t = _FakeTranscoder(running=False)
    pushes = []
    loop = _make_loop(t, pushes, tmp_path, wanted=[])

    loop.tick()
    loop.tick()

    assert t.start_calls == 0
    assert pushes == []


def test_viewer_leaving_stops_transcoder(tmp_path):
    t = _FakeTranscoder(files=[], running=True)
    loop = _make_loop(t, [], tmp_path, wanted=[])

    loop.tick()

    assert t.stop_calls == 1


def test_push_response_still_wanted_false_drops_camera(tmp_path):
    """Espectador saiu no meio da transmissão — descoberto pela resposta do
    push, sem gastar request só pra perguntar.

    A nuvem responde a mesma verdade nos dois canais (ambos leem
    `epi:stream:{id}:active`), então o fake devolve [] depois que o push já
    sinalizou a saída.
    """
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text("#EXTM3U\nsegment1.ts\n")
    pushes = []
    viewer_gone = {"yes": False}

    def _push(http, base, bearer, camera_id, filename, data):
        pushes.append(filename)
        viewer_gone["yes"] = True
        return False  # espectador saiu

    def _fetch_wanted(http, base, bearer):
        return [] if viewer_gone["yes"] else [_CAMERA]

    t = _FakeTranscoder(files=[playlist], running=True)
    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_push,
        fetch_wanted_fn=_fetch_wanted,
    )
    loop._transcoders[_CAMERA] = t

    loop.tick()
    assert len(pushes) == 1
    assert _CAMERA not in loop._wanted  # saiu da lista pela resposta do push

    loop.tick()  # próximo tick derruba o transcode
    assert t.stop_calls == 1


def test_wanted_poll_suppressed_while_streaming(tmp_path):
    """Transmitindo, o poll é suprimido — a resposta do push já responde.
    Sem isso seria 1 request extra por tick durante toda a transmissão."""
    polls = []
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text("#EXTM3U\n")

    def _push(http, base, bearer, camera_id, filename, data):
        return True

    def _fetch_wanted(http, base, bearer):
        polls.append(1)
        return [_CAMERA]

    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_push,
        fetch_wanted_fn=_fetch_wanted,
    )
    loop._transcoders[_CAMERA] = _FakeTranscoder(files=[playlist], running=True)

    loop.tick()  # 1º tick: _wanted vazio -> precisa aprender
    loop.tick()
    loop.tick()

    # Só o tick inicial consulta; depois a resposta do push basta.
    assert len(polls) == 1


def test_wanted_poll_failure_keeps_previous_state(tmp_path):
    """Nuvem inacessível não deve derrubar um stream que está no ar."""
    def _failing_fetch(http, base, bearer):
        raise SegmentPushError("nuvem fora")

    t = _FakeTranscoder(files=[], running=False)
    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=lambda *a: True,
        fetch_wanted_fn=_failing_fetch,
    )
    loop._transcoders[_CAMERA] = t
    loop._wanted = {_CAMERA}

    loop.tick()  # não deve levantar

    assert t.start_calls == 1  # manteve o estado anterior


def test_tick_pushes_playlist_and_segments(tmp_path):
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text("#EXTM3U\nsegment1.ts\n")
    seg = tmp_path / "segment1.ts"
    seg.write_bytes(b"\x47ts-bytes")

    pushes = []
    loop = _make_loop(_FakeTranscoder(files=[playlist, seg]), pushes, tmp_path)
    loop.tick()

    assert [p["filename"] for p in pushes] == ["stream.m3u8", "segment1.ts"]
    assert pushes[1]["data"] == b"\x47ts-bytes"
    assert all(p["camera_id"] == _CAMERA for p in pushes)


def test_nothing_is_repushed_while_unchanged(tmp_path):
    """Tick sem mudança nenhuma não gera request — o custo por request é real
    do lado da nuvem (1 worker gunicorn + --max-requests)."""
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text("#EXTM3U\nsegment1.ts\n")
    seg = tmp_path / "segment1.ts"
    seg.write_bytes(b"data")

    pushes = []
    loop = _make_loop(_FakeTranscoder(files=[playlist, seg]), pushes, tmp_path)
    loop.tick()
    assert len(pushes) == 2  # 1º tick sobe os dois

    loop.tick()
    assert len(pushes) == 2  # 2º tick, nada mudou -> zero request


def test_playlist_repushed_when_new_segment_enters(tmp_path):
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text("#EXTM3U\nsegment1.ts\n")
    seg = tmp_path / "segment1.ts"
    seg.write_bytes(b"data")

    pushes = []
    transcoder = _FakeTranscoder(files=[playlist, seg])
    loop = _make_loop(transcoder, pushes, tmp_path)
    loop.tick()

    seg2 = tmp_path / "segment2.ts"
    seg2.write_bytes(b"data2")
    playlist.write_text("#EXTM3U\nsegment1.ts\nsegment2.ts\n")
    transcoder._files = [playlist, seg, seg2]
    loop.tick()

    filenames = [p["filename"] for p in pushes]
    assert filenames.count("stream.m3u8") == 2  # mudou -> reenviada
    assert filenames.count("segment1.ts") == 1  # inalterado -> não reenviado
    assert filenames.count("segment2.ts") == 1  # novo -> enviado


def test_empty_file_is_skipped(tmp_path):
    empty = tmp_path / "segment1.ts"
    empty.write_bytes(b"")
    pushes = []
    loop = _make_loop(_FakeTranscoder(files=[empty]), pushes, tmp_path)
    loop.tick()
    assert pushes == []


def test_vanished_file_is_skipped_without_raising(tmp_path):
    """delete_segments pode apagar o arquivo entre listar e ler."""
    gone = tmp_path / "segment-gone.ts"
    pushes = []
    loop = _make_loop(_FakeTranscoder(files=[gone]), pushes, tmp_path)
    loop.tick()  # não deve levantar
    assert pushes == []


def test_push_failure_does_not_mark_as_pushed(tmp_path):
    seg = tmp_path / "segment1.ts"
    seg.write_bytes(b"data")

    attempts = []

    def _failing_push(http, base, bearer, camera_id, filename, data):
        attempts.append(filename)
        raise SegmentPushError("cloud down")

    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_failing_push,
        fetch_wanted_fn=lambda *a: [_CAMERA],
    )
    loop._transcoders[_CAMERA] = _FakeTranscoder(files=[seg])

    loop.tick()
    loop.tick()

    assert len(attempts) == 2  # retentou, não marcou como enviado


def test_dead_transcoder_forgets_cache_before_restart(tmp_path):
    """Numeração de segmento reinicia com o FFmpeg — um nome reusado precisa
    subir de novo."""
    seg = tmp_path / "segment1.ts"
    seg.write_bytes(b"data")
    pushes = []

    alive = _FakeTranscoder(files=[seg], running=True)
    loop = _make_loop(alive, pushes, tmp_path)
    loop.tick()
    assert len(pushes) == 1

    alive._running = False
    loop.tick()  # detecta morte, esquece cache, reinicia
    alive._running = True
    loop.tick()

    assert len(pushes) == 2


def test_start_failure_is_logged_not_fatal(tmp_path):
    class _FailingTranscoder(_FakeTranscoder):
        def start(self):
            raise RecorderError("ffmpeg indisponível")

    loop = _make_loop(_FailingTranscoder(running=False), [], tmp_path)
    loop.tick()  # não deve levantar


def test_run_stops_and_cleans_up_on_stop_event(tmp_path):
    t = _FakeTranscoder(files=[])
    loop = _make_loop(t, [], tmp_path)
    loop._poll_interval_s = 0.0

    stop_event = threading.Event()
    stop_event.set()
    loop.run(stop_event)

    assert t.stop_calls == 1  # stop_all no finally


def test_camera_ids_property(tmp_path):
    loop = _make_loop(_FakeTranscoder(), [], tmp_path)
    assert loop.camera_ids == [_CAMERA]


# ── _resolve_camera_urls / build_from_env ───────────────────────────────────


class _FakeRecorder:
    def __init__(self, channel_map):
        self._channel_map = channel_map

    def _build_live_url(self, channel):
        return f"rtsp://admin:pw@10.0.0.9:554/cam/realmonitor?channel={channel}&subtype=1"


def test_resolve_camera_urls_uses_recorder_live_url():
    urls = _resolve_camera_urls(_FakeRecorder({"cam-a": 1, "cam-b": 2}))
    assert set(urls) == {"cam-a", "cam-b"}
    assert "channel=1" in urls["cam-a"]
    assert "channel=2" in urls["cam-b"]


def test_resolve_camera_urls_empty_when_no_channel_map():
    assert _resolve_camera_urls(_FakeRecorder({})) == {}


def test_resolve_camera_urls_skips_camera_whose_url_fails():
    class _PartiallyFailing(_FakeRecorder):
        def _build_live_url(self, channel):
            if channel == 2:
                raise RecorderError("sem canal mapeado")
            return f"rtsp://10.0.0.9:554/cam/realmonitor?channel={channel}&subtype=1"

    urls = _resolve_camera_urls(_PartiallyFailing({"cam-a": 1, "cam-b": 2}))
    assert set(urls) == {"cam-a"}


def test_build_from_env_happy_path(tmp_path):
    loop = build_live_view_loop_from_env(
        _FakeRecorder({"cam-a": 1}),
        _FakeTokenSource(),
        env={"EDGE_API_URL": "https://api.example", "LIVE_VIEW_WORK_DIR": str(tmp_path)},
    )
    assert loop.camera_ids == ["cam-a"]


def test_build_from_env_no_cameras_raises(tmp_path):
    with pytest.raises(ValueError, match="Nenhuma câmera"):
        build_live_view_loop_from_env(
            _FakeRecorder({}),
            _FakeTokenSource(),
            env={"LIVE_VIEW_WORK_DIR": str(tmp_path)},
        )


def test_build_from_env_applies_overrides(tmp_path):
    loop = build_live_view_loop_from_env(
        _FakeRecorder({"cam-a": 1}),
        _FakeTokenSource(),
        env={
            "LIVE_VIEW_WORK_DIR": str(tmp_path),
            "LIVE_VIEW_POLL_INTERVAL_S": "2.5",
            "LIVE_VIEW_SEGMENT_SECONDS": "4",
        },
    )
    assert loop._poll_interval_s == 2.5
