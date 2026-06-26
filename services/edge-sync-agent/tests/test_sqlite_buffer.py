"""Tests for SQLiteBuffer: persistence, ordering, idempotency, drain."""

import time

import pytest

from app.sqlite_buffer import SQLiteBuffer


@pytest.fixture()
def buf(tmp_path):
    b = SQLiteBuffer(str(tmp_path / "test.db"))
    yield b
    b.close()


# ── enqueue / dequeue ────────────────────────────────────────────────────────

def test_enqueue_returns_incrementing_ids(buf):
    id1 = buf.enqueue("detection", "cam1", {"x": 1})
    id2 = buf.enqueue("detection", "cam1", {"x": 2})
    assert id2 > id1


def test_dequeue_preserves_insertion_order(buf):
    for i in range(5):
        buf.enqueue("detection", "cam1", {"seq": i})
    batch = buf.dequeue_batch()
    seqs = [e["payload"]["seq"] for e in batch]
    assert seqs == list(range(5))


def test_dequeue_respects_limit(buf):
    for _ in range(10):
        buf.enqueue("detection", "cam1", {})
    batch = buf.dequeue_batch(limit=3)
    assert len(batch) == 3


def test_dequeue_empty_buffer_returns_empty_list(buf):
    assert buf.dequeue_batch() == []


def test_payload_roundtrip(buf):
    payload = {"class": "helmet", "confidence": 0.97, "bbox": [10, 20, 30, 40]}
    buf.enqueue("detection", "cam7", payload)
    event = buf.dequeue_batch()[0]
    assert event["payload"] == payload
    assert event["event_type"] == "detection"
    assert event["camera_id"] == "cam7"


# ── mark_sent ────────────────────────────────────────────────────────────────

def test_mark_sent_removes_from_dequeue(buf):
    id1 = buf.enqueue("detection", "cam1", {})
    buf.enqueue("detection", "cam1", {})
    buf.mark_sent([id1])
    batch = buf.dequeue_batch()
    assert len(batch) == 1
    assert batch[0]["id"] != id1


def test_mark_sent_empty_list_is_noop(buf):
    buf.enqueue("detection", "cam1", {})
    buf.mark_sent([])  # must not raise
    assert buf.count_unsent() == 1


# ── mark_failed ──────────────────────────────────────────────────────────────

def test_mark_failed_keeps_event_in_queue(buf):
    eid = buf.enqueue("detection", "cam1", {})
    buf.mark_failed([eid])
    batch = buf.dequeue_batch()
    assert len(batch) == 1
    assert batch[0]["attempts"] == 1


def test_mark_failed_increments_attempts_on_each_call(buf):
    eid = buf.enqueue("detection", "cam1", {})
    buf.mark_failed([eid])
    buf.mark_failed([eid])
    buf.mark_failed([eid])
    batch = buf.dequeue_batch()
    assert batch[0]["attempts"] == 3


def test_mark_failed_empty_list_is_noop(buf):
    buf.enqueue("detection", "cam1", {})
    buf.mark_failed([])  # must not raise
    assert buf.count_unsent() == 1


# ── count_unsent ─────────────────────────────────────────────────────────────

def test_count_unsent_reflects_state(buf):
    assert buf.count_unsent() == 0
    buf.enqueue("detection", "cam1", {})
    buf.enqueue("detection", "cam1", {})
    assert buf.count_unsent() == 2
    ids = [e["id"] for e in buf.dequeue_batch()]
    buf.mark_sent(ids)
    assert buf.count_unsent() == 0


# ── persistence across restart ───────────────────────────────────────────────

def test_events_survive_close_and_reopen(tmp_path):
    db_path = str(tmp_path / "persist.db")
    b1 = SQLiteBuffer(db_path)
    b1.enqueue("detection", "cam1", {"data": "keep_me"})
    b1.close()

    b2 = SQLiteBuffer(db_path)
    batch = b2.dequeue_batch()
    b2.close()

    assert len(batch) == 1
    assert batch[0]["payload"]["data"] == "keep_me"


def test_partially_sent_batch_survives_restart(tmp_path):
    db_path = str(tmp_path / "partial.db")
    b1 = SQLiteBuffer(db_path)
    id1 = b1.enqueue("detection", "cam1", {"n": 1})
    b1.enqueue("detection", "cam1", {"n": 2})
    b1.mark_sent([id1])
    b1.close()

    b2 = SQLiteBuffer(db_path)
    batch = b2.dequeue_batch()
    b2.close()

    # Only the unsent event should be returned
    assert len(batch) == 1
    assert batch[0]["payload"]["n"] == 2


# ── purge_old ────────────────────────────────────────────────────────────────

def test_purge_old_removes_sent_events_past_cutoff(tmp_path):
    db_path = str(tmp_path / "purge.db")
    buf = SQLiteBuffer(db_path)
    eid = buf.enqueue("detection", "cam1", {})

    # Manually backdate sent_at to simulate old event
    buf._conn.execute(
        "UPDATE event_buffer SET sent_at = ? WHERE id = ?",
        (time.time() - 10 * 86_400, eid),
    )
    buf._conn.commit()

    deleted = buf.purge_old(days=7)
    buf.close()
    assert deleted == 1


def test_purge_old_keeps_unsent_events(buf):
    buf.enqueue("detection", "cam1", {})
    deleted = buf.purge_old(days=0)  # even with days=0, unsent are safe
    assert deleted == 0
    assert buf.count_unsent() == 1


def test_purge_old_keeps_recently_sent_events(buf):
    eid = buf.enqueue("detection", "cam1", {})
    buf.mark_sent([eid])
    deleted = buf.purge_old(days=7)  # just sent — not old enough
    assert deleted == 0
