"""Heartbeat loop: POST /api/v1/edge/heartbeat, signed by the device's own key.

Reuses `telemetry.build_heartbeat_payload` + `tegrastats_parser` (task-100) for
the payload — this module adds what that pipeline doesn't do: fetch a fresh
bearer via `TokenManager.get_bearer()` (PR-A) on every send, treat `403` as a
terminal "device revoked" condition (`mark_revoked()` + stop, no retry), and
retry/backoff only on network failure. Contract per `scripts/edge_artery_probe.py`
(#227, proven): `201 {id, received_at}` on success, `403` when the cloud has
revoked the device — the cloud never issues a token, so there's nothing to
refresh, just re-sign.

Same `run(stop_event)` idiom as `config_poller`/`command_poller`/`uploader` —
this module doesn't daemonize itself; threading it alongside the other loops
is PR-C's job.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable, Protocol

from .telemetry.collector import build_heartbeat_payload
from .telemetry.tegrastats_parser import TegrastatsSample, parse_tegrastats_line

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://api-v3-desenvolvimento.up.railway.app"  # DEV — nunca produção
_DEFAULT_INTERVAL_S = 45.0
_BACKOFF_STEPS: tuple[float, ...] = (10.0, 30.0, 60.0, 120.0)
_DEFAULT_SAMPLE_TIMEOUT_S = 6.0


class DeviceRevokedError(Exception):
    """The cloud rejected this device (403) — the heartbeat loop stops, no retry."""


class TokenSource(Protocol):
    def get_bearer(self, ttl_s: int = 300) -> str: ...
    def mark_revoked(self) -> None: ...


def read_tegrastats_sample(
    binary: str = "tegrastats", timeout_s: float = _DEFAULT_SAMPLE_TIMEOUT_S
) -> TegrastatsSample:
    """One-shot tegrastats read (not `telemetry.tegrastats_source`'s continuous stream).

    `tegrastats --interval` never exits on its own — `subprocess.run` here
    ALWAYS hits `timeout_s` by design; the sample is the partial output
    `TimeoutExpired` buffered before the kill (same pattern as
    `scripts/edge_artery_probe.py`'s `_jetson_gpu()`, proven on the real
    Jetson — confirmed on pandora during gate 1.6 that treating the timeout
    as "no data" instead of reading `exc.stdout` silently dropped every
    sample). Missing binary (off-Jetson) or genuinely empty output -> an
    empty `TegrastatsSample` (every field `None`) — the honesty rule from the
    telemetry module applies here too: never invent a metric, and never let
    missing host telemetry block the heartbeat itself from being sent.
    """
    lines: list[str] = []
    try:
        proc = subprocess.run(  # noqa: S603
            [binary, "--interval", "1000"], capture_output=True, text=True, timeout=timeout_s
        )
        lines = (proc.stdout or "").strip().splitlines()
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        lines = stdout.strip().splitlines()
    except OSError as exc:
        logger.warning("tegrastats indisponível (%s) — heartbeat sem telemetria de host", exc)
        return TegrastatsSample()
    if not lines:
        logger.warning(
            "tegrastats sem saída em %.1fs — heartbeat sem telemetria de host", timeout_s
        )
        return TegrastatsSample()
    return parse_tegrastats_line(lines[-1])


class HeartbeatLoop:
    """Sends a signed heartbeat every `interval_s` until stopped or revoked."""

    def __init__(
        self,
        http_client: Any,
        cloud_url: str,
        device_id: str,
        token_source: TokenSource,
        sample_provider: Callable[[], TegrastatsSample] = read_tegrastats_sample,
        edge_version: str | None = None,
        interval_s: float = _DEFAULT_INTERVAL_S,
        backoff_steps: tuple[float, ...] = _BACKOFF_STEPS,
        sentinel_path: str | None = None,
    ) -> None:
        self._http = http_client
        self._url = f"{cloud_url.rstrip('/')}/api/v1/edge/heartbeat"
        self._device_id = device_id
        self._token_source = token_source
        self._sample_provider = sample_provider
        self._edge_version = edge_version
        self._interval = interval_s
        self._backoff_steps = backoff_steps
        self._backoff_idx = 0
        # Touched on every successful send — the OTA updater (a SEPARATE
        # process/unit, see app/ota/updater.py) reads its mtime as
        # proof-of-life after restarting this daemon, since it can't observe
        # this process's state directly. Optional: None preserves old
        # behavior for callers/tests that don't care about OTA.
        self._sentinel_path = sentinel_path

    # ── backoff helpers (same idiom as Uploader) ────────────────────────────

    def current_backoff(self) -> float:
        return self._backoff_steps[min(self._backoff_idx, len(self._backoff_steps) - 1)]

    def _advance_backoff(self) -> None:
        self._backoff_idx = min(self._backoff_idx + 1, len(self._backoff_steps) - 1)

    def _reset_backoff(self) -> None:
        self._backoff_idx = 0

    # ── send ─────────────────────────────────────────────────────────────────

    def send_once(self) -> bool:
        """Sends one heartbeat. Returns True on 201/False on retryable failure.

        Raises DeviceRevokedError on 403 — the caller (`run`) must not retry.
        """
        sample = self._sample_provider()
        payload = build_heartbeat_payload(
            sample, device_id=self._device_id, edge_version=self._edge_version
        )
        token = self._token_source.get_bearer()
        try:
            resp = self._http.post(
                self._url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=30.0,
            )
        except Exception as exc:  # network / timeout — retryable
            logger.warning("heartbeat_network_error %s", exc)
            self._advance_backoff()
            return False

        if resp.status_code == 201:
            self._reset_backoff()
            logger.info("heartbeat_sent device_id=%s", self._device_id)
            if self._sentinel_path:
                self._touch_sentinel()
            return True
        if resp.status_code == 403:
            logger.error("heartbeat_403_revoked device_id=%s", self._device_id)
            self._token_source.mark_revoked()
            raise DeviceRevokedError(f"device {self._device_id!r} revogado (403)")

        logger.warning("heartbeat_rejected status=%s", getattr(resp, "status_code", None))
        self._advance_backoff()
        return False

    def _touch_sentinel(self) -> None:
        try:
            path = Path(self._sentinel_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        except OSError as exc:
            logger.warning("heartbeat_sentinel_write_failed %s", exc)

    # ── main loop ────────────────────────────────────────────────────────────

    def run(self, stop_event: threading.Event) -> None:
        """Sends heartbeats until `stop_event` is set. Stops (no retry) on revocation."""
        while not stop_event.is_set():
            try:
                ok = self.send_once()
            except DeviceRevokedError:
                logger.error("heartbeat_loop_stopped device_id=%s (revogado)", self._device_id)
                return
            wait_s = self._interval if ok else self.current_backoff()
            stop_event.wait(timeout=wait_s)


def build_heartbeat_loop_from_env(
    http_client: Any,
    token_source: TokenSource,
    env: dict[str, str] | None = None,
    device_id: str | None = None,
) -> HeartbeatLoop:
    """Reads EDGE_API_URL (default DEV), EDGE_VERSION, EDGE_HEARTBEAT_INTERVAL_S,
    DEVICE_ID, EDGE_HEARTBEAT_SENTINEL_PATH (optional — see HeartbeatLoop's
    sentinel_path docstring; unset means no sentinel, same as before OTA)."""
    source = env if env is not None else os.environ
    resolved_device_id = device_id or source.get("DEVICE_ID", "")
    if not resolved_device_id:
        raise ValueError("device_id (ou DEVICE_ID em env) é obrigatório")

    cloud_url = (source.get("EDGE_API_URL") or _DEFAULT_API_URL).rstrip("/")
    edge_version = source.get("EDGE_VERSION") or None
    interval_s = float(source.get("EDGE_HEARTBEAT_INTERVAL_S", str(_DEFAULT_INTERVAL_S)))
    sentinel_path = source.get("EDGE_HEARTBEAT_SENTINEL_PATH") or None

    return HeartbeatLoop(
        http_client=http_client,
        cloud_url=cloud_url,
        device_id=resolved_device_id,
        token_source=token_source,
        edge_version=edge_version,
        interval_s=interval_s,
        sentinel_path=sentinel_path,
    )
