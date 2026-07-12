"""Batch uploader: drains SQLite buffer → cloud API.

Idempotency: every batch carries a deterministic X-Batch-Id derived from the
sorted event IDs.  Resending the same events produces the identical header so
the cloud can deduplicate without storing extra state on the edge.

Backoff: 30 s → 60 s → 120 s → 300 s (capped), resets on first success.
"""

import hashlib
import logging
import threading
from typing import Any

from .sqlite_buffer import SQLiteBuffer

logger = logging.getLogger(__name__)

_BACKOFF_STEPS: tuple[float, ...] = (30.0, 60.0, 120.0, 300.0)
_DEFAULT_INTERVAL = 30.0


def _batch_id(ids: list[int]) -> str:
    """SHA-256 of sorted IDs → deterministic, collision-resistant batch key."""
    key = ",".join(str(i) for i in sorted(ids))
    return hashlib.sha256(key.encode()).hexdigest()[:32]


class Uploader:
    """Uploads buffered events to the cloud in idempotent batches with backoff."""

    def __init__(
        self,
        buffer: SQLiteBuffer,
        http_client: Any,
        cloud_url: str,
        device_id: str,
        token: str,
        batch_size: int = 500,
        upload_interval_s: float = _DEFAULT_INTERVAL,
        backoff_steps: tuple[float, ...] = _BACKOFF_STEPS,
    ) -> None:
        self._buffer = buffer
        self._http = http_client
        self._url = f"{cloud_url.rstrip('/')}/api/v1/edge/detections"
        self._device_id = device_id
        self._token = token
        self._batch_size = batch_size
        self._interval = upload_interval_s
        self._backoff_steps = backoff_steps
        self._backoff_idx = 0

    # ── backoff helpers ──────────────────────────────────────────────────────

    def current_backoff(self) -> float:
        """Current wait duration (seconds) before the next retry."""
        return self._backoff_steps[min(self._backoff_idx, len(self._backoff_steps) - 1)]

    def _advance_backoff(self) -> None:
        self._backoff_idx = min(self._backoff_idx + 1, len(self._backoff_steps) - 1)

    def _reset_backoff(self) -> None:
        self._backoff_idx = 0

    # ── upload logic ─────────────────────────────────────────────────────────

    def _try_upload(self, batch: list[dict]) -> bool:
        """Attempt one batch upload. Returns True on success."""
        ids = [e["id"] for e in batch]
        bid = _batch_id(ids)
        try:
            resp = self._http.post(
                self._url,
                json={"device_id": self._device_id, "detections": batch},
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "X-Batch-Id": bid,
                },
                timeout=30.0,
            )
            if resp.status_code == 200:
                self._buffer.mark_sent(ids)
                self._reset_backoff()
                logger.info("batch_uploaded batch_id=%s count=%d", bid, len(ids))
                return True
            logger.warning(
                "upload_rejected status=%d batch_id=%s", resp.status_code, bid
            )
        except Exception as exc:  # network / timeout
            logger.warning("upload_error %s batch_id=%s", exc, bid)

        self._buffer.mark_failed(ids)
        self._advance_backoff()
        return False

    # ── main loop ────────────────────────────────────────────────────────────

    def run(self, stop_event: threading.Event) -> None:
        """Drain buffer continuously until *stop_event* is set."""
        while not stop_event.is_set():
            batch = self._buffer.dequeue_batch(limit=self._batch_size)
            if not batch:
                stop_event.wait(timeout=self._interval)
                continue
            success = self._try_upload(batch)
            if not success:
                stop_event.wait(timeout=self.current_backoff())
