"""CollectorLoop — motion-triggered continuous frame collector (Onda 2, task-093).

Polls each configured camera's LIVE feed via RecorderClient.capture_frame()
(task-092), runs it through MotionDetector, and on a motion trigger captures
a short burst of frames (spaced burst_interval_s apart, deduped against the
last uploaded frame) and uploads each kept frame via POST /api/v1/edge/frames
(task-089) — building the initial training pool from RVB's 2 real cameras.

No ONVIF motion events are used (task-092's investigation found none
confirmed available on RVB's Intelbras hardware) — frame-diffing is the only
signal.

Sequential per-tick polling across all configured cameras, single thread, no
per-camera concurrency — correct and simple for the pilot's 2 cameras. A
slow/hung capture_frame() call on one camera delays the others' poll tick by
up to rtsp_frame_capture's timeout (10s default); this would matter at RVB's
eventual full ~28-camera scale but is explicitly out of scope here (this is
the 2-camera shadow-mode pilot — scale is a documented future concern, not
solved speculatively).

Deliberately its OWN process (`python -m app.collector`), NOT a 5th thread in
main.py's run_daemon() — explicit product decision at Onda 2 kickoff: this
workload is bursty/CPU-heavier (JPEG decode + diff every poll tick) and
independently restartable/stoppable without touching the identity/heartbeat/
config-sync daemon. Own systemd --user unit
(deploy/edge-frame-collector.service), same Type=simple/Restart=always shape
as edge-sync-agent.service.

Per-camera "target frames reached" is an in-memory counter — resets to 0 on
process restart. Acceptable simplification for a short, bounded pilot: worst
case a restart makes the process collect somewhat MORE than the target, never
less, and there's no other consumer of a persisted count today. Revisit if
the collector needs to survive across many restarts without re-drifting past
the target.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

from ..recorder_client import RecorderClient, RecorderError
from .frame_uploader import FrameUploadError, upload_frame
from .motion_detector import MotionDetector, frame_diff_score

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://api-v3-desenvolvimento.up.railway.app"  # DEV — nunca produção
_DEFAULT_POLL_INTERVAL_S = 3.0
_DEFAULT_BURST_COUNT = 8
_DEFAULT_BURST_INTERVAL_S = 1.0
_DEFAULT_COOLDOWN_S = 30.0
_DEFAULT_TARGET_FRAMES_PER_CAMERA = 1000
_DEFAULT_MODULE_CODE = "epi"
# Much stricter than MotionDetector's own trigger threshold — burst frames
# are already time-spaced (burst_interval_s apart), this only catches a
# near-exact repeat (e.g. the scene went still mid-burst), not "similar".
_DEDUP_THRESHOLD = 2.0


class TokenSource(Protocol):
    def get_bearer(self, ttl_s: int = 300) -> str: ...


@dataclass
class _CameraState:
    detector: MotionDetector
    frames_uploaded: int = 0
    cooldown_until: float | None = None
    last_uploaded_bytes: bytes | None = None


class CollectorLoop:
    """Runs the motion→burst→cooldown state machine for every configured camera."""

    def __init__(
        self,
        recorder: RecorderClient,
        camera_ids: list[str],
        api_base_url: str,
        recorder_id: str,
        token_source: TokenSource,
        http_client: Any = None,
        module_code: str = _DEFAULT_MODULE_CODE,
        poll_interval_s: float = _DEFAULT_POLL_INTERVAL_S,
        burst_count: int = _DEFAULT_BURST_COUNT,
        burst_interval_s: float = _DEFAULT_BURST_INTERVAL_S,
        cooldown_s: float = _DEFAULT_COOLDOWN_S,
        target_frames_per_camera: int = _DEFAULT_TARGET_FRAMES_PER_CAMERA,
        motion_threshold: float = MotionDetector.DEFAULT_MIN_AREA,
        upload_fn: Any = upload_frame,
        clock: Any = time.monotonic,
    ) -> None:
        self._recorder = recorder
        self._camera_ids = list(camera_ids)
        self._api_base_url = api_base_url
        self._recorder_id = recorder_id
        self._token_source = token_source
        self._http = http_client if http_client is not None else httpx.Client()
        self._module_code = module_code
        self._poll_interval_s = poll_interval_s
        self._burst_count = burst_count
        self._burst_interval_s = burst_interval_s
        self._cooldown_s = cooldown_s
        self._target = target_frames_per_camera
        self._upload_fn = upload_fn
        self._clock = clock
        self._states: dict[str, _CameraState] = {
            camera_id: _CameraState(detector=MotionDetector(threshold=motion_threshold))
            for camera_id in self._camera_ids
        }

    @property
    def camera_ids(self) -> list[str]:
        return list(self._camera_ids)

    # ── upload ───────────────────────────────────────────────────────────────

    def _upload(self, camera_id: str, frame_bytes: bytes) -> bool:
        try:
            bearer = self._token_source.get_bearer()
            frame_id = self._upload_fn(
                self._http,
                self._api_base_url,
                bearer,
                camera_id,
                self._recorder_id,
                frame_bytes,
                self._module_code,
                datetime.now(timezone.utc),
            )
        except FrameUploadError as exc:
            logger.warning("collector_upload_failed camera=%s err=%s", camera_id, exc)
            return False
        logger.info("collector_frame_uploaded camera=%s frame_id=%s", camera_id, frame_id)
        return True

    # ── burst ────────────────────────────────────────────────────────────────

    def _run_burst(
        self,
        camera_id: str,
        state: _CameraState,
        first_frame: bytes,
        stop_event: threading.Event,
    ) -> int:
        uploaded = 0
        frame = first_frame
        for i in range(self._burst_count):
            if state.frames_uploaded + uploaded >= self._target:
                break
            if i > 0:
                if stop_event.wait(timeout=self._burst_interval_s):
                    break  # shutdown requested mid-burst
                try:
                    frame = self._recorder.capture_frame(camera_id)
                except RecorderError as exc:
                    logger.warning(
                        "collector_burst_capture_failed camera=%s err=%s", camera_id, exc
                    )
                    continue
            if state.last_uploaded_bytes is not None:
                score = frame_diff_score(frame, state.last_uploaded_bytes)
                if score < _DEDUP_THRESHOLD:
                    logger.debug(
                        "collector_burst_frame_deduped camera=%s score=%.2f", camera_id, score
                    )
                    continue
            if self._upload(camera_id, frame):
                state.last_uploaded_bytes = frame
                uploaded += 1
        return uploaded

    # ── main loop ────────────────────────────────────────────────────────────

    def tick(self, stop_event: threading.Event) -> None:
        now = self._clock()
        for camera_id in self._camera_ids:
            state = self._states[camera_id]
            if state.frames_uploaded >= self._target:
                continue
            if state.cooldown_until is not None and now < state.cooldown_until:
                continue
            try:
                frame = self._recorder.capture_frame(camera_id)
            except RecorderError as exc:
                logger.warning("collector_capture_failed camera=%s err=%s", camera_id, exc)
                continue
            motion = state.detector.detect(frame)
            if not motion.changed:
                # Score dos ticks que NÃO dispararam é o que permite calibrar
                # o limiar sem adivinhar (debug pra não poluir o log normal).
                logger.debug(
                    "collector_no_motion camera=%s area=%.4f", camera_id, motion.score
                )
                continue
            logger.info(
                "collector_motion_detected camera=%s area=%.4f (limiar=%.4f)",
                camera_id, motion.score, state.detector._threshold,
            )
            uploaded = self._run_burst(camera_id, state, frame, stop_event)
            state.frames_uploaded += uploaded
            state.cooldown_until = self._clock() + self._cooldown_s
            if state.frames_uploaded >= self._target:
                logger.info(
                    "collector_target_reached camera=%s frames=%d", camera_id, state.frames_uploaded
                )

    def run(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            self.tick(stop_event)
            stop_event.wait(timeout=self._poll_interval_s)


def build_collector_loop_from_env(
    recorder: RecorderClient,
    token_source: TokenSource,
    env: dict[str, str] | None = None,
) -> CollectorLoop:
    """Reads RECORDER_CHANNEL_MAP (same var recorder_factory.py uses — its
    keys ARE the camera_id list this collector monitors, no separate list to
    keep in sync), RECORDER_CLOUD_ID (new: the public.recorders UUID in the
    cloud DB — a different identity than RECORDER_HOST/PORT's edge-local
    connection details), EDGE_API_URL, and the COLLECTOR_* tuning knobs (all
    optional, sensible defaults)."""
    source = env if env is not None else os.environ

    camera_ids = _parse_camera_ids(source.get("RECORDER_CHANNEL_MAP", ""))

    recorder_id = source.get("RECORDER_CLOUD_ID", "")
    if not recorder_id:
        raise ValueError(
            "RECORDER_CLOUD_ID é obrigatório (UUID do public.recorders na nuvem) "
            "— sem ele o upload não sabe a qual gravador associar o frame."
        )

    api_base_url = (source.get("EDGE_API_URL") or _DEFAULT_API_URL).rstrip("/")

    return CollectorLoop(
        recorder=recorder,
        camera_ids=camera_ids,
        api_base_url=api_base_url,
        recorder_id=recorder_id,
        token_source=token_source,
        module_code=source.get("COLLECTOR_MODULE_CODE", _DEFAULT_MODULE_CODE),
        poll_interval_s=float(
            source.get("COLLECTOR_POLL_INTERVAL_S", str(_DEFAULT_POLL_INTERVAL_S))
        ),
        burst_count=int(source.get("COLLECTOR_BURST_COUNT", str(_DEFAULT_BURST_COUNT))),
        burst_interval_s=float(
            source.get("COLLECTOR_BURST_INTERVAL_S", str(_DEFAULT_BURST_INTERVAL_S))
        ),
        cooldown_s=float(source.get("COLLECTOR_COOLDOWN_S", str(_DEFAULT_COOLDOWN_S))),
        target_frames_per_camera=int(
            source.get(
                "COLLECTOR_TARGET_FRAMES_PER_CAMERA", str(_DEFAULT_TARGET_FRAMES_PER_CAMERA)
            )
        ),
        motion_threshold=float(
            source.get("COLLECTOR_MOTION_THRESHOLD", str(MotionDetector.DEFAULT_MIN_AREA))
        ),
    )


def _parse_camera_ids(raw: str) -> list[str]:
    if not raw.strip():
        raise ValueError(
            "RECORDER_CHANNEL_MAP é obrigatório (mesma var do recorder_factory) "
            "— o coletor usa as chaves (camera_id) como lista de câmeras a monitorar."
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"RECORDER_CHANNEL_MAP não é JSON válido: {exc}") from exc
    if not isinstance(parsed, dict) or not parsed:
        raise ValueError(
            "RECORDER_CHANNEL_MAP deve ser um objeto JSON não vazio {camera_id: canal}"
        )
    return list(parsed.keys())
