"""Durable SQLite WAL buffer for edge events — survives restarts, never discards."""

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS event_buffer (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT    NOT NULL,
    camera_id   TEXT    NOT NULL,
    payload     TEXT    NOT NULL,
    created_at  REAL    NOT NULL,
    sent_at     REAL,
    attempts    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_unsent
    ON event_buffer(created_at, id)
    WHERE sent_at IS NULL;
"""


class SQLiteBuffer:
    """Thread-safe persistent event queue backed by SQLite WAL."""

    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._lock = threading.Lock()
        self._conn = self._open()

    def _open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(_DDL)
        conn.commit()
        return conn

    # ── writes ───────────────────────────────────────────────────────────────

    def enqueue(self, event_type: str, camera_id: str, payload: dict) -> int:
        """Insert one event; returns its row id."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO event_buffer (event_type, camera_id, payload, created_at)"
                " VALUES (?, ?, ?, ?)",
                (event_type, camera_id, json.dumps(payload), time.time()),
            )
            self._conn.commit()
            return cur.lastrowid  # type: ignore[return-value]

    def mark_sent(self, ids: list[int]) -> None:
        """Mark events as successfully uploaded (removes them from future batches)."""
        if not ids:
            return
        ph = ",".join("?" * len(ids))
        with self._lock:
            self._conn.execute(
                f"UPDATE event_buffer SET sent_at = ? WHERE id IN ({ph})",
                [time.time(), *ids],
            )
            self._conn.commit()

    def mark_failed(self, ids: list[int]) -> None:
        """Increment attempts counter; event stays in queue for retry."""
        if not ids:
            return
        ph = ",".join("?" * len(ids))
        with self._lock:
            self._conn.execute(
                f"UPDATE event_buffer SET attempts = attempts + 1 WHERE id IN ({ph})",
                ids,
            )
            self._conn.commit()

    # ── reads ────────────────────────────────────────────────────────────────

    def dequeue_batch(self, limit: int = 500) -> list[dict]:
        """Return up to *limit* unsent events ordered chronologically (FIFO)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, event_type, camera_id, payload, created_at, attempts"
                " FROM event_buffer"
                " WHERE sent_at IS NULL"
                " ORDER BY created_at ASC, id ASC"
                " LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "event_type": row["event_type"],
                "camera_id": row["camera_id"],
                "payload": json.loads(row["payload"]),
                "created_at": row["created_at"],
                "attempts": row["attempts"],
            }
            for row in rows
        ]

    def count_unsent(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM event_buffer WHERE sent_at IS NULL"
            ).fetchone()
        return row[0]

    # ── maintenance ──────────────────────────────────────────────────────────

    def purge_old(self, days: int = 7) -> int:
        """Delete sent events older than *days*. Returns number of rows deleted."""
        cutoff = time.time() - days * 86_400
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM event_buffer WHERE sent_at IS NOT NULL AND sent_at < ?",
                (cutoff,),
            )
            self._conn.commit()
            return cur.rowcount

    def close(self) -> None:
        with self._lock:
            self._conn.close()
