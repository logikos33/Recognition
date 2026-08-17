"""Tests for LiveViewLoop: supervisão do transcode + push dos segmentos."""

import os
import threading
import time
from concurrent.futures import Future
from pathlib import Path

import pytest

from app.live_view.live_view_loop import (
    LiveViewLoop,
    _proportional_max_pushes,
    _resolve_camera_urls,
    build_live_view_loop_from_env,
)
from app.live_view.segment_pusher import SegmentPushError
from app.recorder_client import RecorderError


def _settled(path, data=b"data"):
    """Segmento só sobe depois de assentar — envelhece o mtime no teste."""
    path.write_bytes(data)
    st = path.stat()
    os.utime(path, (st.st_atime, st.st_mtime - 5))
    return path


def _hot(path, data=b"hot"):
    """Segmento permanece "quente" (is_settling=True) de forma determinística
    — mtime no FUTURO em vez de confiar em nenhum tick real acontecer dentro
    de _SETTLE_SECONDS. Nunca assenta sozinho; o teste que precisa dele
    assentando chama `_settled`/`_age_to_settled` explicitamente."""
    path.write_bytes(data)
    st = path.stat()
    os.utime(path, (st.st_atime, st.st_mtime + 100))
    return path


def _age_to_settled(path):
    """Reenvelhece um arquivo (tipicamente criado com `_hot`) pra além de
    _SETTLE_SECONDS, sem tocar o conteúdo — simula o ffmpeg fechando o
    segmento entre um tick e o outro."""
    now = time.time()
    os.utime(path, (now, now - 5))
    return path


def _playlist_text(*names: str, media_sequence: int = 0) -> str:
    """Playlist no formato real do ffmpeg deste repo (`hls_flags
    delete_segments+omit_endlist` — sem PROGRAM-DATE-TIME, sem ENDLIST): um
    par `#EXTINF`+URI por segmento."""
    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        "#EXT-X-TARGETDURATION:2",
        f"#EXT-X-MEDIA-SEQUENCE:{media_sequence}",
    ]
    for name in names:
        lines.append("#EXTINF:2.000000,")
        lines.append(name)
    return "\n".join(lines) + "\n"


def _wait_until(predicate, timeout=5.0, interval=0.01, poll=None):
    """Poll determinístico (sem sleep fixo) até `predicate()` virar True ou
    estourar o timeout — usado pelos testes de concorrência real (D-74),
    onde o resultado do worker thread não chega no mesmo tick que o
    submeteu."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if poll is not None:
            poll()
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError("timed out waiting for condition")


class _InlineExecutor:
    """Executor de teste (D-74): `submit` roda a função NA HORA, na mesma
    thread do chamador, e devolve um `Future` já resolvido. Preserva a
    semântica síncrona que os testes pré-existentes esperam de um único
    `tick()` mesmo com o push agora saindo por um `_executor.submit(...)` —
    sem isso, tick() dispararia trabalho de verdade em background e as
    asserções logo em seguida virariam uma corrida (flaky)."""

    def submit(self, fn, *args, **kwargs):
        future: Future = Future()
        try:
            result = fn(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 - repassa qualquer falha do job
            future.set_exception(exc)
        else:
            future.set_result(result)
        return future

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        pass


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
        executor=_InlineExecutor(),
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
    sinalizou a saída. Usa um segmento (não a playlist) pra sinalizar — a
    detecção de `viewer_left` é a mesma nos dois casos, e um segmento não
    depende do gate de prefixo da playlist.
    """
    seg = _settled(tmp_path / "segment1.ts")
    pushes = []
    viewer_gone = {"yes": False}

    def _push(http, base, bearer, camera_id, filename, data):
        pushes.append(filename)
        viewer_gone["yes"] = True
        return False  # espectador saiu

    def _fetch_wanted(http, base, bearer):
        return [] if viewer_gone["yes"] else [_CAMERA]

    t = _FakeTranscoder(files=[seg], running=True)
    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_push,
        fetch_wanted_fn=_fetch_wanted,
        executor=_InlineExecutor(),
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
        executor=_InlineExecutor(),
    )
    loop._transcoders[_CAMERA] = _FakeTranscoder(files=[playlist], running=True)

    loop.tick()  # 1º tick: _wanted vazio -> precisa aprender
    loop.tick()
    loop.tick()

    # Só o tick inicial consulta; depois a resposta do push basta.
    assert len(polls) == 1


_CAMERA_2 = "cam-2"
_RTSP_2 = "rtsp://admin:pw@10.0.0.9:554/cam/realmonitor?channel=2&subtype=1"


def test_new_viewer_on_idle_camera_starts_it_while_other_streams(tmp_path):
    """D-36: cam-1 já transmite (com espectador) e cam-2 está ociosa. Um
    espectador novo aparece em cam-2 — a supressão antiga (`_streaming` =
    any() das câmeras) travava o poll pra sempre assim que UMA câmera
    qualquer estivesse no ar, então cam-2 nunca seria descoberta até cam-1
    perder o espectador. Com o fix, sobra candidata ociosa -> poll continua
    rodando e descobre o espectador novo."""
    polls = []
    wanted_response = [_CAMERA]

    def _push(http, base, bearer, camera_id, filename, data):
        return True

    def _fetch_wanted(http, base, bearer):
        polls.append(1)
        return list(wanted_response)

    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP, _CAMERA_2: _RTSP_2},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_push,
        fetch_wanted_fn=_fetch_wanted,
        executor=_InlineExecutor(),
    )
    transcoder_1 = _FakeTranscoder(files=[], running=True)
    transcoder_2 = _FakeTranscoder(files=[], running=False)
    loop._transcoders[_CAMERA] = transcoder_1
    loop._transcoders[_CAMERA_2] = transcoder_2

    loop.tick()  # 1º tick: _wanted vazio -> aprende {_CAMERA}; cam-2 ociosa
    assert loop._wanted == {_CAMERA}
    assert transcoder_2.start_calls == 0
    assert len(polls) == 1  # cam-2 ociosa -> não suprime, mas só 1 poll até aqui

    wanted_response[:] = [_CAMERA, _CAMERA_2]  # espectador novo em cam-2

    loop.tick()

    assert transcoder_2.start_calls == 1  # descoberto sem esperar cam-1 esvaziar
    assert transcoder_1.start_calls == 0  # cam-1 não foi reiniciada
    assert transcoder_1.stop_calls == 0
    assert len(polls) == 2  # cam-2 ociosa manteve o poll ativo no 2º tick também


def test_wanted_poll_suppressed_when_all_known_cameras_streaming(tmp_path):
    """Mesma otimização de `test_wanted_poll_suppressed_while_streaming`, mas
    com N>1 câmeras: só suprime quando NENHUMA candidata ociosa resta."""
    polls = []

    def _push(http, base, bearer, camera_id, filename, data):
        return True

    def _fetch_wanted(http, base, bearer):
        polls.append(1)
        return [_CAMERA, _CAMERA_2]

    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP, _CAMERA_2: _RTSP_2},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_push,
        fetch_wanted_fn=_fetch_wanted,
        executor=_InlineExecutor(),
    )
    loop._transcoders[_CAMERA] = _FakeTranscoder(files=[], running=True)
    loop._transcoders[_CAMERA_2] = _FakeTranscoder(files=[], running=True)

    loop.tick()  # 1º tick: _wanted vazio -> aprende as duas, ambas já rodando
    loop.tick()
    loop.tick()

    # Todas as câmeras conhecidas transmitindo -> zero poll extra.
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
        executor=_InlineExecutor(),
    )
    loop._transcoders[_CAMERA] = t
    loop._wanted = {_CAMERA}

    loop.tick()  # não deve levantar

    assert t.start_calls == 1  # manteve o estado anterior


def test_tick_pushes_segments_before_playlist(tmp_path):
    """Correção estrutural dos 425 (#308): a nuvem só pode anunciar (.m3u8)
    segmento que JÁ está no Redis — o .ts sobe ANTES da playlist que o
    lista. Antes a ordem era [playlist, segmento] e cada segmento novo abria
    1–3s de janela de 425 no player."""
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text(_playlist_text("segment1.ts"))
    seg = _settled(tmp_path / "segment1.ts", b"\x47ts-bytes")

    pushes = []
    loop = _make_loop(_FakeTranscoder(files=[playlist, seg]), pushes, tmp_path)
    loop.tick()

    assert [p["filename"] for p in pushes] == ["segment1.ts", "stream.m3u8"]
    assert pushes[0]["data"] == b"\x47ts-bytes"
    assert all(p["camera_id"] == _CAMERA for p in pushes)


# ── playlist consistente por construção: snapshot + truncamento do rabo ────
#
# Substitui o antigo `hold_playlist` por settling (que segurava a playlist
# INTEIRA e represava o avanço por um tick inteiro): a playlist agora avança
# a cada tick, truncada ao maior prefixo de segmentos que a nuvem já tem.


def test_playlist_truncated_while_newest_segment_settles(tmp_path):
    """(a) O segmento mais novo listado ainda está quente (ffmpeg pode
    anexar os últimos bytes) -> a playlist sobe TRUNCADA sem ele, NO MESMO
    tick — nem o URI, nem o `#EXTINF` dele; `#EXT-X-MEDIA-SEQUENCE` intacto
    (conta a partir da 1ª entrada, cortar só o rabo não o afeta).

    (b) No tick seguinte, o segmento assenta e sobe -> a playlist sobe
    COMPLETA; o conteúdo mudou (digest diferente), então não é dedupada
    contra o push truncado do tick anterior.
    """
    seg1 = _settled(tmp_path / "segment1.ts", b"seg1-bytes")
    seg2 = _hot(tmp_path / "segment2.ts", b"seg2-bytes")
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text(_playlist_text("segment1.ts", "segment2.ts", media_sequence=5))

    pushes = []
    transcoder = _FakeTranscoder(files=[playlist, seg1, seg2])
    loop = _make_loop(transcoder, pushes, tmp_path)
    loop.tick()

    # (a) segment2 ainda quente -> nem tentado; playlist sobe truncada.
    assert [p["filename"] for p in pushes] == ["segment1.ts", "stream.m3u8"]
    truncated = pushes[-1]["data"].decode()
    assert "segment1.ts" in truncated
    assert "segment2.ts" not in truncated  # nem o URI...
    assert truncated.count("#EXTINF") == 1  # ...nem o EXTINF dele
    assert "#EXT-X-MEDIA-SEQUENCE:5" in truncated  # intacto

    # (b) segment2 assenta -> sobe no próximo tick, playlist completa junto.
    _age_to_settled(seg2)
    loop.tick()

    new_pushes = pushes[2:]
    assert [p["filename"] for p in new_pushes] == ["segment2.ts", "stream.m3u8"]
    full = new_pushes[-1]["data"].decode()
    assert "segment1.ts" in full and "segment2.ts" in full
    assert full.count("#EXTINF") == 2
    assert full != truncated  # digest diferente -> não foi dedupada


def test_playlist_not_pushed_when_stale_segment_push_fails_mid_prefix(tmp_path):
    """(c) Buraco no meio: o push do segmento mais ANTIGO (`segment1`) falha
    seletivamente, mas o mais NOVO (`segment2`) sobe — um nome não-enviado
    com um enviado depois dele. Não dá pra truncar o meio (só o rabo), então
    a playlist inteira fica de fora deste tick (fallback conservador, mesmo
    comportamento do antigo hold pra falha real)."""
    seg1 = _settled(tmp_path / "segment1.ts", b"seg1")
    seg2 = _settled(tmp_path / "segment2.ts", b"seg2")
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text(_playlist_text("segment1.ts", "segment2.ts"))

    pushed = []

    def _push(http, base, bearer, camera_id, filename, data):
        if filename == "segment1.ts":
            raise SegmentPushError("cloud down")
        pushed.append(filename)
        return True

    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_push,
        fetch_wanted_fn=lambda *a: [_CAMERA],
        executor=_InlineExecutor(),
    )
    loop._transcoders[_CAMERA] = _FakeTranscoder(files=[playlist, seg1, seg2])

    loop.tick()

    assert pushed == ["segment2.ts"]  # segment1 falhou, segment2 subiu
    assert "stream.m3u8" not in pushed  # buraco -> playlist não sobe


def test_playlist_not_pushed_when_truncation_would_leave_no_segments(tmp_path):
    """(d) Único segmento listado, ainda quente -> o prefixo fica vazio.
    Empurrar um manifesto sem nenhum segmento é pior do que não empurrar (o
    player leria um stream sem mídia) -> a playlist não sobe."""
    seg = _hot(tmp_path / "segment1.ts")
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text(_playlist_text("segment1.ts"))

    pushes = []
    loop = _make_loop(_FakeTranscoder(files=[playlist, seg]), pushes, tmp_path)
    loop.tick()

    assert pushes == []


def test_truncated_playlist_content_is_deduped_across_ticks(tmp_path):
    """(e) O mesmo conteúdo truncado duas vezes seguidas (segment2 nunca
    assenta neste teste) gera um push só — dedupe por digest do CONTEÚDO
    efetivamente empurrado, não do arquivo em disco (que nem muda)."""
    seg1 = _settled(tmp_path / "segment1.ts", b"seg1")
    seg2 = _hot(tmp_path / "segment2.ts", b"seg2")  # nunca assenta
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text(_playlist_text("segment1.ts", "segment2.ts"))

    pushes = []
    loop = _make_loop(_FakeTranscoder(files=[playlist, seg1, seg2]), pushes, tmp_path)
    loop.tick()
    loop.tick()

    filenames = [p["filename"] for p in pushes]
    assert filenames.count("stream.m3u8") == 1  # conteúdo truncado igual -> 1 push
    assert filenames.count("segment1.ts") == 1  # inalterado -> não reenviado


def test_playlist_push_uses_snapshot_not_reread_content(tmp_path):
    """(f) A corrida original medida no soak: o gate decidia sobre
    `list_ready_files()` do INÍCIO do job, mas `read_bytes()` da playlist
    rodava no FIM — no intervalo (com POSTs de segmento no meio), o ffmpeg
    podia reescrever o `.m3u8` com um segmento recém-fechado, e o conteúdo
    NOVO subia sob a decisão VELHA (o navegador sabia do segmento ~1,7s
    antes dele existir no Redis).

    Aqui `push_fn` simula o ffmpeg: ao empurrar `segment1`, reescreve
    `stream.m3u8` em disco como se um `segment2` tivesse acabado de fechar.
    O conteúdo de playlist empurrado tem que ser o SNAPSHOT capturado antes
    disso — nunca uma releitura do arquivo."""
    seg1 = _settled(tmp_path / "segment1.ts", b"seg1")
    playlist = tmp_path / "stream.m3u8"
    original_content = _playlist_text("segment1.ts")
    playlist.write_text(original_content)

    pushes = []

    def _push(http, base, bearer, camera_id, filename, data):
        pushes.append({"filename": filename, "data": data})
        if filename == "segment1.ts":
            # ffmpeg "fecha" segment2 e reescreve a playlist ENQUANTO o
            # push de segment1 estava em voo.
            playlist.write_text(_playlist_text("segment1.ts", "segment2.ts"))
        return True

    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_push,
        fetch_wanted_fn=lambda *a: [_CAMERA],
        executor=_InlineExecutor(),
    )
    loop._transcoders[_CAMERA] = _FakeTranscoder(files=[playlist, seg1])

    loop.tick()

    playlist_pushes = [p for p in pushes if p["filename"] == "stream.m3u8"]
    assert len(playlist_pushes) == 1
    assert playlist_pushes[0]["data"].decode() == original_content  # snapshot
    assert b"segment2.ts" not in playlist_pushes[0]["data"]  # nunca a releitura


def test_playlist_snapshot_discarded_when_file_changes_mid_read(tmp_path, monkeypatch):
    """stat1 -> read_bytes -> stat2: se o arquivo mudou DURANTE a própria
    leitura do snapshot, o conteúdo é descartado neste tick (sobe íntegro no
    próximo) — nunca um Frankenstein de metade-antigo/metade-novo. Segmentos
    não são afetados por essa regra."""
    seg = _settled(tmp_path / "segment1.ts", b"seg1")
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text(_playlist_text("segment1.ts"))

    original_read_bytes = Path.read_bytes
    future = time.time() + 100

    def _read_then_mutate(self, *args, **kwargs):
        data = original_read_bytes(self, *args, **kwargs)
        if self == playlist:
            os.utime(self, (future, future))  # "ffmpeg" reescreveu no meio
        return data

    monkeypatch.setattr(Path, "read_bytes", _read_then_mutate)

    pushes = []
    loop = _make_loop(_FakeTranscoder(files=[playlist, seg]), pushes, tmp_path)
    loop.tick()

    filenames = [p["filename"] for p in pushes]
    assert "stream.m3u8" not in filenames  # snapshot descartado
    assert "segment1.ts" in filenames  # segmento não afetado


def test_playlist_not_pushed_when_segment_push_fails(tmp_path):
    """Falha real de push (não é gate por settling): o único segmento
    listado falha -> nunca entra no prefixo -> playlist não sobe. No tick
    seguinte a falha some -> segmento sobe, prefixo completo, playlist
    sobe."""
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text(_playlist_text("segment1.ts"))
    seg = _settled(tmp_path / "segment1.ts", b"data")

    pushes = []
    fail_ts = {"active": True}

    def _selective_push(http, base, bearer, camera_id, filename, data):
        if fail_ts["active"] and filename.endswith(".ts"):
            raise SegmentPushError("cloud down")
        pushes.append({"camera_id": camera_id, "filename": filename, "data": data})
        return True

    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_selective_push,
        fetch_wanted_fn=lambda *a: [_CAMERA],
        executor=_InlineExecutor(),
    )
    loop._transcoders[_CAMERA] = _FakeTranscoder(files=[playlist, seg])

    loop.tick()
    assert pushes == []  # segmento falhou -> nunca entra no prefixo

    fail_ts["active"] = False
    loop.tick()
    assert [p["filename"] for p in pushes] == ["segment1.ts", "stream.m3u8"]


def test_nothing_is_repushed_while_unchanged(tmp_path):
    """Tick sem mudança nenhuma não gera request — o custo por request é real
    do lado da nuvem (1 worker gunicorn + --max-requests)."""
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text(_playlist_text("segment1.ts"))
    seg = _settled(tmp_path / "segment1.ts", b"data")

    pushes = []
    loop = _make_loop(_FakeTranscoder(files=[playlist, seg]), pushes, tmp_path)
    loop.tick()
    assert len(pushes) == 2  # 1º tick sobe os dois

    loop.tick()
    assert len(pushes) == 2  # 2º tick, nada mudou -> zero request


def test_playlist_repushed_when_new_segment_enters(tmp_path):
    playlist = tmp_path / "stream.m3u8"
    playlist.write_text(_playlist_text("segment1.ts"))
    seg = _settled(tmp_path / "segment1.ts", b"data")

    pushes = []
    transcoder = _FakeTranscoder(files=[playlist, seg])
    loop = _make_loop(transcoder, pushes, tmp_path)
    loop.tick()

    seg2 = _settled(tmp_path / "segment2.ts", b"data2")
    playlist.write_text(_playlist_text("segment1.ts", "segment2.ts"))
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
    seg = _settled(tmp_path / "segment1.ts", b"data")

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
        executor=_InlineExecutor(),
    )
    loop._transcoders[_CAMERA] = _FakeTranscoder(files=[seg])

    loop.tick()
    loop.tick()

    assert len(attempts) == 2  # retentou, não marcou como enviado


def test_dead_transcoder_forgets_cache_before_restart(tmp_path):
    """Numeração de segmento reinicia com o FFmpeg — um nome reusado precisa
    subir de novo."""
    seg = _settled(tmp_path / "segment1.ts", b"data")
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


# ── D-74: push paralelo por câmera ──────────────────────────────────────────
#
# Estes testes usam um `ThreadPoolExecutor` REAL (não o `_InlineExecutor`) —
# é a concorrência em si que está sob teste. Determinísticos via
# `threading.Event` (segura um push) + `_wait_until` (poll com timeout, sem
# `sleep` fixo) em vez de qualquer corrida de tempo.


def test_slow_camera_push_does_not_block_others(tmp_path):
    """Câmera lenta não trava as demais: o bug original (D-74) era 1 thread
    pra todas as câmeras, então uma câmera lenta atrasava o ciclo inteiro
    (~19s medidos por câmera). Com um worker thread por câmera, a câmera B
    (push instantâneo) termina mesmo com a câmera A ainda presa."""
    block_a = threading.Event()
    pushes = []
    lock = threading.Lock()

    def _push(http, base, bearer, camera_id, filename, data):
        if camera_id == _CAMERA:
            block_a.wait(timeout=5)
        with lock:
            pushes.append(camera_id)
        return True

    dir_a, dir_b = tmp_path / "a", tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    seg_a = _settled(dir_a / "segment1.ts")
    seg_b = _settled(dir_b / "segment1.ts")

    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP, _CAMERA_2: _RTSP_2},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_push,
        fetch_wanted_fn=lambda *a: [_CAMERA, _CAMERA_2],
        max_parallel_pushes=4,
    )
    loop._transcoders[_CAMERA] = _FakeTranscoder(files=[seg_a], running=True)
    loop._transcoders[_CAMERA_2] = _FakeTranscoder(files=[seg_b], running=True)

    try:
        loop.tick()

        _wait_until(lambda: _CAMERA_2 in pushes)  # B empurrou sem esperar A
        assert _CAMERA not in pushes  # A ainda preso no Event
        assert _CAMERA in loop._push_futures  # job de A ainda em voo

        block_a.set()
        _wait_until(
            lambda: _CAMERA not in loop._push_futures,
            poll=loop._collect_finished_pushes,
        )
        assert _CAMERA in pushes  # próxima coleta recolhe o job de A
    finally:
        block_a.set()
        loop.stop_all()


def test_at_most_one_job_in_flight_per_camera(tmp_path):
    """Com um job de uma câmera ainda em voo, um novo tick NÃO submete um
    segundo job pra mesma câmera — só um worker por câmera de cada vez."""
    block = threading.Event()
    submissions = []

    def _push(http, base, bearer, camera_id, filename, data):
        submissions.append(camera_id)
        block.wait(timeout=5)
        return True

    seg = _settled(tmp_path / "segment1.ts")
    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_push,
        fetch_wanted_fn=lambda *a: [_CAMERA],
        max_parallel_pushes=4,
    )
    loop._transcoders[_CAMERA] = _FakeTranscoder(files=[seg], running=True)

    try:
        loop.tick()  # submete o único job permitido pra _CAMERA
        assert _CAMERA in loop._push_futures

        loop.tick()  # job ainda em voo -> câmera inteira pulada
        loop.tick()

        block.set()
        _wait_until(
            lambda: _CAMERA not in loop._push_futures,
            poll=loop._collect_finished_pushes,
        )
        assert submissions == [_CAMERA]  # só a 1ª submissão aconteceu
    finally:
        block.set()
        loop.stop_all()


def test_viewer_left_from_job_result_applies_on_collect(tmp_path):
    """`viewer_left` descoberto DENTRO do worker thread só deve mutar
    `self._wanted` quando `_collect_finished_pushes` roda no thread
    principal (nunca dentro do job em si — thread-safety de `_wanted`)."""
    seg = _settled(tmp_path / "segment1.ts")

    def _push(http, base, bearer, camera_id, filename, data):
        return False  # espectador saiu

    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_push,
        fetch_wanted_fn=lambda *a: [_CAMERA],
        max_parallel_pushes=4,
    )
    loop._transcoders[_CAMERA] = _FakeTranscoder(files=[seg], running=True)

    try:
        loop.tick()
        _wait_until(
            lambda: _CAMERA not in loop._push_futures,
            poll=loop._collect_finished_pushes,
        )
        assert _CAMERA not in loop._wanted
    finally:
        loop.stop_all()


def test_camera_with_job_in_flight_defers_lifecycle(tmp_path):
    """Câmera com job de push em voo não sofre stop/restart de transcoder no
    mesmo tick, mesmo que o poll de `wanted` diga que ela não é mais
    desejada — o lifecycle espera o job em voo terminar."""
    block = threading.Event()
    wanted_response = [_CAMERA]

    def _push(http, base, bearer, camera_id, filename, data):
        block.wait(timeout=5)
        return True

    def _fetch_wanted(http, base, bearer):
        return list(wanted_response)

    seg = _settled(tmp_path / "segment1.ts")
    loop = LiveViewLoop(
        camera_urls={_CAMERA: _RTSP},
        api_base_url="https://api.example",
        token_source=_FakeTokenSource(),
        work_dir=str(tmp_path),
        http_client=object(),
        push_fn=_push,
        fetch_wanted_fn=_fetch_wanted,
        max_parallel_pushes=4,
    )
    t = _FakeTranscoder(files=[seg], running=True)
    loop._transcoders[_CAMERA] = t

    try:
        loop.tick()  # submete job, fica preso no Event
        assert _CAMERA in loop._push_futures

        wanted_response[:] = []  # espectador "some" do lado do poll
        loop._wanted = set()  # força repoll no próximo tick (sem supressão)
        loop.tick()  # job ainda em voo -> lifecycle (stop) adiado

        assert t.stop_calls == 0

        block.set()
        _wait_until(
            lambda: _CAMERA not in loop._push_futures,
            poll=loop._collect_finished_pushes,
        )
    finally:
        block.set()
        loop.stop_all()


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


# ── teto de pushes proporcional ao site (rodada 11/08, D-85) ────────────────


def test_proportional_max_pushes_has_floor_and_grows_with_site():
    # Site pequeno fica no piso histórico (D-74) — nunca abaixo de 8.
    assert _proportional_max_pushes(1) == 8
    assert _proportional_max_pushes(6) == 8
    # A partir daí cresce com o site: câmeras + folga de 2 slots.
    assert _proportional_max_pushes(8) == 10
    assert _proportional_max_pushes(29) == 31


def test_build_from_env_max_pushes_proportional_to_cameras(tmp_path):
    """Com o iNVD cheio (29 câmeras) e SEM env explícito, o teto acompanha o
    site — um default fixo de 8 traria o rodízio (#325–#331) de volta."""
    channel_map = {f"cam-{n}": n for n in range(1, 30)}  # 29 câmeras
    loop = build_live_view_loop_from_env(
        _FakeRecorder(channel_map),
        _FakeTokenSource(),
        env={"LIVE_VIEW_WORK_DIR": str(tmp_path)},
    )
    try:
        assert loop._executor._max_workers == 31  # 29 + folga de 2
    finally:
        loop._executor.shutdown(wait=False)


def test_build_from_env_max_pushes_env_override_wins(tmp_path):
    """LIVE_VIEW_MAX_PARALLEL_PUSHES explícito continua mandando — é o botão
    de emergência pra estrangular upload sem redeploy."""
    channel_map = {f"cam-{n}": n for n in range(1, 30)}
    loop = build_live_view_loop_from_env(
        _FakeRecorder(channel_map),
        _FakeTokenSource(),
        env={
            "LIVE_VIEW_WORK_DIR": str(tmp_path),
            "LIVE_VIEW_MAX_PARALLEL_PUSHES": "4",
        },
    )
    try:
        assert loop._executor._max_workers == 4
    finally:
        loop._executor.shutdown(wait=False)
