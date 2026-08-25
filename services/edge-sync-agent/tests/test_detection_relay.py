"""DetectionRelay: Redis det:* (pipeline local, ADR-0002) → SQLiteBuffer.

É o PRODUTOR do caminho detecções→cloud: antes dele nada no agente chamava
SQLiteBuffer.enqueue fora dos testes — o Uploader drenava um buffer que
ninguém enchia.
"""

import json
import threading
from unittest.mock import MagicMock

import pytest

from app.detection_relay import (
    DetectionRelay,
    build_detection_relay_from_env,
)
from app.sqlite_buffer import SQLiteBuffer


class _FakePubSub:
    """pubsub mínimo (psubscribe/get_message/close) alimentado por uma lista."""

    def __init__(self, messages):
        self._messages = list(messages)
        self.patterns: list[str] = []
        self.closed = False

    def psubscribe(self, *patterns):
        self.patterns.extend(patterns)

    def get_message(self, ignore_subscribe_messages=False, timeout=0.0):
        if self._messages:
            return self._messages.pop(0)
        return None

    def close(self):
        self.closed = True


def _pmessage(channel: str, payload, pattern: str = "det:*"):
    data = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
    return {"type": "pmessage", "pattern": pattern, "channel": channel, "data": data}


@pytest.fixture()
def buf(tmp_path):
    b = SQLiteBuffer(str(tmp_path / "relay.db"))
    yield b
    b.close()


# ── handle(): uma mensagem → (ou não) uma linha no buffer ───────────────────

def test_violation_frame_becomes_detection_event(buf):
    relay = DetectionRelay(buf, lambda: _FakePubSub([]))
    payload = {
        "camera_id": "cam-uuid-1",
        "timestamp": "2026-08-23T12:00:00Z",
        "detections": [{"class": "no_helmet", "confidence": 0.91, "bbox": [1, 2, 3, 4]}],
        "has_violation": True,
    }

    row_id = relay.handle("det:cam-uuid-1", json.dumps(payload))

    assert row_id is not None
    [item] = buf.dequeue_batch()
    assert item["event_type"] == "detection"
    assert item["camera_id"] == "cam-uuid-1"
    assert item["payload"] == payload


def test_frame_without_violation_is_dropped(buf):
    """det:* é tráfego de overlay ao vivo (5 FPS × N câmeras, efêmero por
    ADR-0002). Só violação vira EVENTO — relayar todo frame encheria um
    buffer que nunca descarta (disco cheio = intertravamento do Orin)."""
    relay = DetectionRelay(buf, lambda: _FakePubSub([]))

    assert relay.handle("det:c1", json.dumps({"camera_id": "c1", "detections": [],
                                               "has_violation": False})) is None
    assert relay.handle("det:c1", json.dumps({"camera_id": "c1", "detections": []})) is None
    assert buf.count_unsent() == 0


def test_camera_id_falls_back_to_channel_suffix(buf):
    relay = DetectionRelay(buf, lambda: _FakePubSub([]))

    relay.handle("det:cam-from-channel", json.dumps({"has_violation": True}))
    relay.handle("detections:tenant-x:cam-deep", json.dumps({"has_violation": True}))

    cams = [e["camera_id"] for e in buf.dequeue_batch()]
    assert cams == ["cam-from-channel", "cam-deep"]


def test_bytes_channel_and_data_are_decoded(buf):
    relay = DetectionRelay(buf, lambda: _FakePubSub([]))

    relay.handle(b"det:cam-b", json.dumps({"has_violation": True}).encode())

    [item] = buf.dequeue_batch()
    assert item["camera_id"] == "cam-b"


def test_malformed_message_is_dropped_not_raised(buf):
    relay = DetectionRelay(buf, lambda: _FakePubSub([]))

    assert relay.handle("det:c1", b"\xff\xfenot json") is None
    assert relay.handle("det:c1", "[1, 2, 3]") is None  # JSON, mas não objeto
    assert buf.count_unsent() == 0


# ── run(): assina, drena mensagens, para no stop_event, fecha o pubsub ───────

def test_run_subscribes_both_channel_names_and_drains(buf):
    """Assina det:* (nome usado por services/inference e pelo worker Celery —
    o que o socket_bridge da API consome) E detections:* (nome do ADR-0002 /
    edge.env.example) — os dois nomes coexistem na documentação."""
    ps = _FakePubSub([
        _pmessage("det:c1", {"camera_id": "c1", "has_violation": True}),
        {"type": "psubscribe", "pattern": "det:*", "channel": "det:*", "data": 1},
        _pmessage("det:c2", {"camera_id": "c2", "has_violation": False}),
        _pmessage("detections:c3", {"camera_id": "c3", "has_violation": True},
                  pattern="detections:*"),
    ])
    relay = DetectionRelay(buf, lambda: ps, poll_s=0.0)
    stop = threading.Event()

    def _stop_when_drained():
        while ps._messages:
            pass
        stop.set()

    t = threading.Thread(target=_stop_when_drained, daemon=True)
    t.start()
    relay.run(stop)
    t.join(timeout=2.0)

    assert set(ps.patterns) == {"det:*", "detections:*"}
    assert [e["camera_id"] for e in buf.dequeue_batch()] == ["c1", "c3"]
    assert ps.closed is True


def test_run_exits_immediately_when_stop_already_set(buf):
    ps = _FakePubSub([_pmessage("det:c1", {"has_violation": True})])
    relay = DetectionRelay(buf, lambda: ps, poll_s=0.0)
    stop = threading.Event()
    stop.set()

    relay.run(stop)

    assert buf.count_unsent() == 0
    assert ps.closed is True


def test_run_propagates_transport_error_for_supervisor_restart(buf):
    """Queda do Redis → exceção sobe; main._supervise reinicia com backoff e
    o pubsub é refeito do zero (nada de reconexão caseira aqui)."""
    ps = _FakePubSub([])
    ps.get_message = MagicMock(side_effect=ConnectionError("redis down"))
    relay = DetectionRelay(buf, lambda: ps, poll_s=0.0)

    with pytest.raises(ConnectionError):
        relay.run(threading.Event())
    assert ps.closed is True


# ── build_detection_relay_from_env ───────────────────────────────────────────

def test_disabled_without_edge_redis_url(buf):
    assert build_detection_relay_from_env(buf, env={}) is None
    assert build_detection_relay_from_env(buf, env={"EDGE_REDIS_URL": ""}) is None


def test_enabled_with_edge_redis_url_uses_redis_pubsub(buf, monkeypatch):
    fake_redis_mod = MagicMock()
    client = MagicMock()
    fake_redis_mod.Redis.from_url.return_value = client
    monkeypatch.setitem(__import__("sys").modules, "redis", fake_redis_mod)

    relay = build_detection_relay_from_env(
        buf, env={"EDGE_REDIS_URL": "redis://127.0.0.1:6379/0"}
    )

    assert isinstance(relay, DetectionRelay)
    relay._pubsub_factory()
    fake_redis_mod.Redis.from_url.assert_called_once_with("redis://127.0.0.1:6379/0")
    client.pubsub.assert_called_once_with()
