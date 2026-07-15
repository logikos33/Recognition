"""RecorderClient — abstract interface over the site's NVR/gravador.

ADR-0045 (recorder-first): evidence lives on the gravador at the site, not on
the edge's 128GB (SO+app only, never storage). This module defines the
*contract* the evidence API uses to query the recorder's timeline and pull a
clip on demand — it does NOT talk ONVIF/RTSP itself.

The real ONVIF/RTSP implementation is task-091 ("índice ONVIF do gravador"),
which is the next task in the queue and depends on this one. Until it lands,
`NotConfiguredRecorderClient` is wired as the default so a misconfigured
deployment fails loud instead of silently serving nothing. `InMemoryRecorderClient`
is a deterministic stub for tests and local development only.

No implementation in this module may persist clip bytes to disk — streaming is
pass-through (generator of chunks). Anything transient MUST be cleaned up by the
caller; see evidence_api.py for the streaming response wiring.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecorderEvent:
    """One timeline entry reported by the recorder (motion, alarm, manual mark, ...)."""

    event_id: str
    camera_id: str
    started_at: datetime
    ended_at: datetime
    event_type: str
    description: str | None = None


@dataclass(frozen=True)
class RecorderHealth:
    """Result of a connectivity probe against the recorder."""

    reachable: bool
    detail: str = ""


class RecorderError(Exception):
    """Raised when the recorder cannot fulfil a request (unreachable, bad window, ...)."""


@runtime_checkable
class RecorderClient(Protocol):
    """Contract every recorder backend (ONVIF, vendor SDK, mock) must satisfy.

    Implementations are injected into the evidence API (see evidence_api.create_app);
    the API layer never talks to the recorder protocol directly.
    """

    def list_events(
        self, camera_id: str, start: datetime, end: datetime
    ) -> list[RecorderEvent]:
        """Return timeline events for *camera_id* within [start, end]."""
        ...

    def stream_clip(
        self, camera_id: str, start: datetime, end: datetime
    ) -> Iterator[bytes]:
        """Yield the requested clip as a sequence of byte chunks.

        MUST NOT write the clip to disk — pure pass-through generator so the
        evidence API can stream the response without ever caching it on the
        edge's 128GB (ADR-0033/0045 — reserva de disco intocável).
        """
        ...

    def health(self) -> RecorderHealth:
        """Cheap connectivity probe used by GET /health."""
        ...


class NotConfiguredRecorderClient:
    """Default RecorderClient — fails loud until a real backend is wired.

    Prevents the mini-API from silently pretending to serve evidence when no
    recorder integration exists yet (task-091). Every method raises
    RecorderError with a clear pointer to the missing dependency.
    """

    _MESSAGE = (
        "Nenhum RecorderClient real configurado — a integração ONVIF/RTSP com "
        "o gravador é escopo da task-091. Injete uma implementação concreta em "
        "create_app(recorder_client=...) antes de servir tráfego real."
    )

    def list_events(
        self, camera_id: str, start: datetime, end: datetime
    ) -> list[RecorderEvent]:
        raise RecorderError(self._MESSAGE)

    def stream_clip(
        self, camera_id: str, start: datetime, end: datetime
    ) -> Iterator[bytes]:
        raise RecorderError(self._MESSAGE)
        yield b""  # pragma: no cover — makes this a generator function

    def health(self) -> RecorderHealth:
        return RecorderHealth(reachable=False, detail=self._MESSAGE)


class InMemoryRecorderClient:
    """Deterministic stub RecorderClient for tests and local dev.

    Not wired as the production default — callers must opt in explicitly.
    """

    def __init__(
        self,
        events: list[RecorderEvent] | None = None,
        clip_chunks: list[bytes] | None = None,
        reachable: bool = True,
    ) -> None:
        self._events = events if events is not None else []
        self._clip_chunks = clip_chunks if clip_chunks is not None else [b"fake-clip-bytes"]
        self._reachable = reachable

    def list_events(
        self, camera_id: str, start: datetime, end: datetime
    ) -> list[RecorderEvent]:
        return [
            e
            for e in self._events
            if e.camera_id == camera_id and e.started_at >= start and e.ended_at <= end
        ]

    def stream_clip(
        self, camera_id: str, start: datetime, end: datetime
    ) -> Iterator[bytes]:
        if not self._reachable:
            raise RecorderError(f"gravador inacessível para camera_id={camera_id}")
        yield from self._clip_chunks

    def health(self) -> RecorderHealth:
        if self._reachable:
            return RecorderHealth(reachable=True, detail="mock ok")
        return RecorderHealth(reachable=False, detail="mock unreachable")
