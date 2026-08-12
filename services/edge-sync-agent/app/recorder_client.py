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


class RecorderAuthError(RecorderError):
    """Raised specifically for a 401/403 from the recorder (bad credential).

    Distinct from the generic RecorderError so callers that need to react to
    *auth* failures differently — namely the snapshot capture anti-lockout
    circuit breaker (services/edge-sync-agent/app/snapshot_executor.py) —
    don't have to string-match error messages for the one case where the
    reaction MUST be deterministic: the gravador (Intelbras iNVD 3032 at
    RVB) applies anti-brute-force lockout to repeated failed-auth attempts
    (CLAUDE.md), so a 401/403 must never be treated as "just retry via
    another transport" (e.g. falling back from ONVIF to RTSP with the same
    bad credential is still hammering the same device).
    """


class RecorderChannelError(RecorderError):
    """Raised when a snapshot capture cannot resolve WHICH recorder channel
    to hit: the camera is not in the box's channel_map AND the command
    carried no usable channel hint.

    Distinct subtype (same rationale as RecorderAuthError: no string
    matching) so snapshot_executor.py can surface a truthful, specific
    reason ("câmera fora do channel_map e sem canal no comando") instead of
    letting this fall into the generic "sem sinal no canal" bucket — which
    is a lie: the channel was never even contacted. Found in the field (RVB,
    canal 9 draft): the config_poller only feeds ACTIVE cameras into the
    channel_map, so every draft camera used to die here mislabeled as
    "no signal".
    """


def resolve_snapshot_channel(
    channel_map: dict[str, int], camera_id: str, channel_hint: "int | None"
) -> int:
    """Resolves camera_id -> recorder channel for a SNAPSHOT capture.

    Resolution order (deliberate, Bloco A):
      1. channel_map — the box's LIVE source of truth (cloud-polled config,
         ADR-0058). Always wins when present, so an ACTIVE camera can never
         desync from the mapping the rest of the box (live view, collector)
         is using, even if a stale queued command carries an old channel.
      2. *channel_hint* — the `channel` field of the capture_snapshot
         command payload (straight from `public.cameras.channel` in the
         cloud). This is what makes DRAFT cameras photographable at all:
         draft (is_active=false) never enters the channel_map BY DESIGN
         (config_poller filters on is_active — drafts must not join the
         HLS/collector pipelines), so the hint is the only channel source
         for exactly the triage case this feature exists for.
      3. Neither -> RecorderChannelError (specific, never the generic
         "no signal" bucket).

    Shared by both RecorderClient backends (ONVIF and RTSP fallback) —
    snapshot-only: evidence/collector paths keep the strict map-only
    `_channel_for` (ADR-0017, no silent fallback), because for those flows
    an unmapped camera IS a misconfiguration, not an expected draft state.
    """
    if camera_id in channel_map:
        return channel_map[camera_id]
    if channel_hint is not None:
        logger.info(
            "snapshot_channel_from_hint camera_id=%s channel=%d — câmera fora do "
            "channel_map (draft por desenho); usando o canal do comando",
            camera_id, channel_hint,
        )
        return channel_hint
    raise RecorderChannelError(
        f"camera_id={camera_id!r} fora do channel_map e sem canal no comando — "
        "sem como resolver o canal do gravador para o snapshot"
    )


def is_auth_failure_message(text: str) -> bool:
    """Best-effort heuristic for a 401/403 surfaced through a transport with
    no structured status code (e.g. ffmpeg's RTSP stderr, which has no HTTP
    status object to inspect — only free text). Used by RecorderClient
    backends that talk RTSP-only (no SOAP/HTTP status code available) to
    decide whether a capture failure should be reclassified as
    RecorderAuthError for the snapshot anti-lockout breaker.

    Best-effort by nature: a false negative just means the breaker doesn't
    trip on that particular failure (falls back to the generic "capture
    failed" reason instead) — never a false positive that would wrongly open
    the breaker for an unrelated network error.
    """
    if not text:
        return False
    lowered = text.lower()
    return (
        "401" in lowered
        or "403" in lowered
        or "unauthorized" in lowered
        or "forbidden" in lowered
    )


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

    def capture_frame(self, camera_id: str) -> bytes:
        """Returns JPEG bytes for one frame off *camera_id*'s LIVE feed, now.

        Unlike stream_clip (a recorded/playback window), this hits the
        camera's current live stream — used by the motion-triggered frame
        collector (Onda 2 shadow mode) to pull training frames, not evidence
        clips. MUST NOT write to disk (ADR-0033/0045 — reserva de disco
        intocável no edge).
        """
        ...

    def get_snapshot(self, camera_id: str, channel_hint: "int | None" = None) -> bytes:
        """Returns JPEG bytes for a snapshot of *camera_id*, for the camera
        triage/thumbnail flow (CameraTriagePage — Bloco A).

        Prefers a dedicated recorder-side snapshot mechanism (ONVIF
        GetSnapshotUri, D-85: a single GET, never touches the channel_map or
        starts an HLS pipeline) over a live-frame RTSP grab
        (`capture_frame`), falling back to it only when the recorder doesn't
        support/errors resolving a snapshot URI for a reason OTHER than
        authentication.

        *channel_hint* — the `channel` from the capture_snapshot command
        payload; used ONLY when the camera is absent from the channel_map
        (draft cameras never enter the map by design — see
        `resolve_snapshot_channel`). The map always wins when present.

        Raises RecorderAuthError on 401/403 from the recorder — callers MUST
        NOT retry with the same credential over a different transport (see
        RecorderAuthError docstring, anti-lockout). Raises
        RecorderChannelError when neither map nor hint can resolve a channel.
        Raises the generic RecorderError for any other failure (channel with
        no signal, timeout, ...).
        """
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

    def capture_frame(self, camera_id: str) -> bytes:
        raise RecorderError(self._MESSAGE)

    def get_snapshot(self, camera_id: str, channel_hint: "int | None" = None) -> bytes:
        raise RecorderError(self._MESSAGE)


class InMemoryRecorderClient:
    """Deterministic stub RecorderClient for tests and local dev.

    Not wired as the production default — callers must opt in explicitly.
    """

    def __init__(
        self,
        events: list[RecorderEvent] | None = None,
        clip_chunks: list[bytes] | None = None,
        reachable: bool = True,
        frame_bytes: bytes = b"fake-frame-bytes",
        snapshot_bytes: bytes | None = None,
        snapshot_auth_error: bool = False,
    ) -> None:
        self._events = events if events is not None else []
        self._clip_chunks = clip_chunks if clip_chunks is not None else [b"fake-clip-bytes"]
        self._reachable = reachable
        self._frame_bytes = frame_bytes
        self._snapshot_bytes = snapshot_bytes if snapshot_bytes is not None else frame_bytes
        self._snapshot_auth_error = snapshot_auth_error

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

    def capture_frame(self, camera_id: str) -> bytes:
        if not self._reachable:
            raise RecorderError(f"gravador inacessível para camera_id={camera_id}")
        return self._frame_bytes

    def get_snapshot(self, camera_id: str, channel_hint: "int | None" = None) -> bytes:
        if self._snapshot_auth_error:
            raise RecorderAuthError(f"mock auth failure for camera_id={camera_id}")
        if not self._reachable:
            raise RecorderError(f"gravador inacessível para camera_id={camera_id}")
        return self._snapshot_bytes
