"""Tests for collector_state (D-86): contador de cota persistido entre
restarts + interruptor-mestre COLLECTOR_ENABLED.

Reusa os fakes de test_collector_loop (recorder/upload/clock) para provar o
comportamento fim-a-fim: coleta -> grava estado -> "restart" (novo
CollectorLoop no mesmo state file) -> cota NÃO re-arma.
"""

import json
import threading

from app.collector.collector_loop import CollectorLoop
from app.collector.collector_state import (
    collection_enabled,
    load_counts,
    save_counts,
)
from tests.test_collector_loop import (
    _BLACK,
    _CAMERA,
    _GRAY,
    _RECORDER_ID,
    _WHITE,
    _fake_upload_fn,
    _FakeClock,
    _FakeRecorder,
    _FakeTokenSource,
)


def _make_loop_with_state(recorder, upload_calls, state_path, **overrides):
    defaults = dict(
        recorder=recorder,
        camera_ids=[_CAMERA],
        api_base_url="https://api.example",
        recorder_id=_RECORDER_ID,
        token_source=_FakeTokenSource(),
        http_client=object(),
        upload_fn=_fake_upload_fn(upload_calls),
        clock=_FakeClock(),
        poll_interval_s=0.0,
        burst_count=3,
        burst_interval_s=0.0,
        cooldown_s=30.0,
        target_frames_per_camera=1000,
        state_path=str(state_path) if state_path is not None else None,
    )
    defaults.update(overrides)
    return CollectorLoop(**defaults)


# ── load/save ────────────────────────────────────────────────────────────────


def test_load_counts_missing_file_returns_empty(tmp_path):
    assert load_counts(str(tmp_path / "nao-existe.json")) == {}


def test_load_counts_corrupt_json_returns_empty(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{nem json")
    assert load_counts(str(path)) == {}


def test_load_counts_wrong_shape_returns_empty(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"frames_uploaded": [1, 2, 3]}))
    assert load_counts(str(path)) == {}


def test_load_counts_ignores_invalid_values_keeps_valid(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps({"frames_uploaded": {"cam-a": 17, "cam-b": "muitos", "cam-c": -3}})
    )
    # inválido é ignorado; negativo vira 0 (contagem nunca é negativa)
    assert load_counts(str(path)) == {"cam-a": 17, "cam-c": 0}


def test_save_then_load_roundtrip(tmp_path):
    path = str(tmp_path / "state.json")
    save_counts(path, {"cam-a": 42, "cam-b": 0})
    assert load_counts(path) == {"cam-a": 42, "cam-b": 0}


def test_save_counts_never_raises_on_bad_path():
    # diretório impossível (arquivo no meio do caminho) — best-effort, sem exceção
    save_counts("/dev/null/impossivel/state.json", {"cam-a": 1})


# ── integração com o CollectorLoop ───────────────────────────────────────────


def test_burst_persists_counts_to_state_file(tmp_path):
    state_path = tmp_path / "state.json"
    recorder = _FakeRecorder({_CAMERA: [_BLACK, _WHITE, _GRAY, _BLACK]})
    uploads = []
    loop = _make_loop_with_state(recorder, uploads, state_path)

    loop.tick(threading.Event())  # seed
    loop.tick(threading.Event())  # motion -> burst (3 uploads)

    assert len(uploads) == 3
    assert load_counts(str(state_path)) == {_CAMERA: 3}


def test_restart_does_not_rearm_quota(tmp_path):
    """O cenário exato do D-86: restart no meio da campanha NÃO dobra a coleta."""
    state_path = tmp_path / "state.json"
    save_counts(str(state_path), {_CAMERA: 1000})  # cota já batida

    recorder = _FakeRecorder({_CAMERA: [_BLACK, _WHITE, _GRAY]})
    uploads = []
    # "restart": processo novo, mesmo state file, alvo 1000
    loop = _make_loop_with_state(recorder, uploads, state_path)

    loop.tick(threading.Event())
    loop.tick(threading.Event())

    # cota persistida ≥ alvo -> câmera nem é capturada (zero chamadas RTSP)
    assert uploads == []
    assert recorder.calls == []


def test_restart_resumes_from_persisted_count(tmp_path):
    state_path = tmp_path / "state.json"
    save_counts(str(state_path), {_CAMERA: 998})  # faltam 2 pro alvo

    recorder = _FakeRecorder({_CAMERA: [_BLACK, _WHITE, _GRAY, _BLACK]})
    uploads = []
    loop = _make_loop_with_state(recorder, uploads, state_path, target_frames_per_camera=1000)

    loop.tick(threading.Event())  # seed
    loop.tick(threading.Event())  # burst — para no alvo, não em burst_count

    assert len(uploads) == 2  # 998 + 2 = 1000, nem um frame a mais
    assert load_counts(str(state_path)) == {_CAMERA: 1000}


def test_state_file_preserves_cameras_not_in_current_map(tmp_path):
    """Câmera desativada na triagem sai do channel_map, mas a contagem dela
    NÃO pode evaporar do state file — religada depois, continua de onde parou."""
    state_path = tmp_path / "state.json"
    save_counts(str(state_path), {"cam-arquivada": 500, _CAMERA: 0})

    recorder = _FakeRecorder({_CAMERA: [_BLACK, _WHITE, _GRAY, _BLACK]})
    uploads = []
    loop = _make_loop_with_state(recorder, uploads, state_path)

    loop.tick(threading.Event())
    loop.tick(threading.Event())

    persisted = load_counts(str(state_path))
    assert persisted["cam-arquivada"] == 500
    assert persisted[_CAMERA] == 3


def test_no_state_path_means_no_persistence(tmp_path):
    recorder = _FakeRecorder({_CAMERA: [_BLACK, _WHITE, _GRAY, _BLACK]})
    uploads = []
    loop = _make_loop_with_state(recorder, uploads, None)

    loop.tick(threading.Event())
    loop.tick(threading.Event())

    assert len(uploads) == 3
    assert not (tmp_path / "x.json").exists()


# ── interruptor-mestre ───────────────────────────────────────────────────────


def test_collection_enabled_default_on():
    assert collection_enabled({}) is True


def test_collection_enabled_off_values():
    for value in ("0", "false", "no", " FALSE ", "No"):
        assert collection_enabled({"COLLECTOR_ENABLED": value}) is False


def test_collection_enabled_on_values():
    for value in ("1", "true", "yes", "qualquer-coisa"):
        assert collection_enabled({"COLLECTOR_ENABLED": value}) is True
