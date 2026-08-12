"""Command poller: consumes edge_commands from the cloud and acks results.

Polls GET /api/v1/edge/commands/pending (device auth) and applies supported
command types:

  - update_camera_config → ConfigPoller.apply_camera_config (in-memory, no restart)
  - capture_snapshot → SnapshotExecutor.capture_and_upload (ONVIF/RTSP
    capture + multipart upload — see snapshot_executor.py). Processed
    SEQUENTIALLY within a poll batch (never concurrently — the gravador is a
    single device serving the whole site's recording, not just triage
    snapshots) with a short delay between successive captures
    (*snapshot_delay_s*) so a batch of 29 draft cameras never hammers it.
    Anti-lockout: once `snapshot_executor.circuit_open` trips (a 401/403 from
    the recorder), every remaining/future capture_snapshot command is failed
    immediately with reason="auth" WITHOUT even attempting the recorder
    again — see snapshot_executor.py's docstring.

Unknown command types are acked as failed with result={'reason': 'unsupported'}
so the queue never clogs. Every command is acked exactly once per poll cycle
via PATCH /api/v1/edge/commands/<command_id>.

Same pattern as ConfigPoller: injected http_client, run(stop_event) loop.
"""

import logging
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DEFAULT_INTERVAL = 60.0  # 1 minute
_DEFAULT_SNAPSHOT_DELAY_S = 2.0
_CAPTURE_SNAPSHOT = "capture_snapshot"


class CommandPoller:
    """Periodically fetches pending edge commands and executes them."""

    def __init__(
        self,
        http_client: Any,
        cloud_url: str,
        token: str,
        config_poller: Any,
        poll_interval_s: float = _DEFAULT_INTERVAL,
        snapshot_executor: Any = None,
        snapshot_delay_s: float = _DEFAULT_SNAPSHOT_DELAY_S,
        sleep_fn: Any = time.sleep,
    ) -> None:
        self._http = http_client
        base = cloud_url.rstrip("/")
        self._pending_url = f"{base}/api/v1/edge/commands/pending"
        self._ack_url_base = f"{base}/api/v1/edge/commands"
        self._token = token
        self._config_poller = config_poller
        self._interval = poll_interval_s
        self._snapshot_executor = snapshot_executor
        self._snapshot_delay_s = snapshot_delay_s
        self._sleep = sleep_fn

    # ── internal ─────────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    def _poll_once(self) -> int:
        """Fetch and handle pending commands. Returns number handled."""
        try:
            resp = self._http.get(
                self._pending_url,
                headers=self._headers(),
                timeout=15.0,
            )
            if resp.status_code != 200:
                logger.warning("command_poll_failed status=%d", resp.status_code)
                return 0
            body = resp.json() or {}
            # API envelope: {"status": "success", "data": {"commands": [...]}}
            data = body.get("data") if isinstance(body.get("data"), dict) else body
            commands = data.get("commands") or []
        except Exception as exc:
            logger.warning("command_poll_error %s", exc)
            return 0

        handled = 0
        snapshots_seen = 0
        for cmd in commands:
            if cmd.get("command_type") == _CAPTURE_SNAPSHOT:
                breaker_open = (
                    self._snapshot_executor is not None and self._snapshot_executor.circuit_open
                )
                # Sequential, never a burst: sleep BETWEEN successive
                # captures in this batch (not before the first one, not
                # after the last command overall) — the recorder is shared
                # with actual site recording, not just triage snapshots.
                # Skipped once the breaker is open: no recorder call is
                # about to happen (fail-fast ack in _handle_capture_snapshot),
                # so there is nothing left to rate-limit.
                if snapshots_seen > 0 and not breaker_open:
                    self._sleep(self._snapshot_delay_s)
                snapshots_seen += 1
            self._handle(cmd)
            handled += 1
        return handled

    def _handle(self, cmd: dict) -> None:
        command_id = cmd.get("command_id")
        if not command_id:
            logger.warning("command_without_id ignored")
            return
        command_type = cmd.get("command_type")
        payload = cmd.get("payload") or {}

        if command_type == "update_camera_config":
            try:
                applied = self._config_poller.apply_camera_config(
                    payload.get("camera_id"),
                    payload.get("fps_target"),
                    payload.get("quality_preset"),
                    payload.get("collection_subtype"),
                )
                self._ack(command_id, "done", {"applied": bool(applied)})
            except Exception as exc:
                logger.warning("command_apply_error id=%s %s", command_id, exc)
                self._ack(command_id, "failed", {"reason": str(exc)})
        elif command_type == _CAPTURE_SNAPSHOT:
            self._handle_capture_snapshot(command_id, payload)
        else:
            # Unknown type: ack failed so the queue never clogs.
            logger.warning("command_unsupported type=%s id=%s", command_type, command_id)
            self._ack(command_id, "failed", {"reason": "unsupported"})

    def _handle_capture_snapshot(self, command_id: str, payload: dict) -> None:
        if self._snapshot_executor is None:
            logger.warning("command_capture_snapshot_no_executor id=%s", command_id)
            self._ack(command_id, "failed", {"reason": "unsupported"})
            return

        camera_id = payload.get("camera_id")
        if not camera_id:
            self._ack(command_id, "failed", {"reason": "invalid_payload"})
            return

        if self._snapshot_executor.circuit_open:
            # Breaker already tripped (this batch or an earlier poll cycle):
            # fail fast, never touch the recorder again until restart.
            logger.warning(
                "command_capture_snapshot_circuit_open id=%s reason=%s — pulando sem tentar",
                command_id, self._snapshot_executor.circuit_reason,
            )
            self._ack(
                command_id, "failed",
                {"reason": "auth", "detail": self._snapshot_executor.circuit_reason},
            )
            return

        result = self._snapshot_executor.capture_and_upload(camera_id, payload.get("channel"))
        if result.get("ok"):
            self._ack(command_id, "done", {"captured": True})
        else:
            self._ack(
                command_id, "failed",
                {"reason": result.get("reason", "capture_failed"), "detail": result.get("detail")},
            )

    def _ack(self, command_id: str, status: str, result: Optional[dict]) -> None:
        try:
            resp = self._http.patch(
                f"{self._ack_url_base}/{command_id}",
                json={"status": status, "result": result},
                headers=self._headers(),
                timeout=15.0,
            )
            if resp.status_code != 200:
                logger.warning(
                    "command_ack_failed id=%s status=%d", command_id, resp.status_code
                )
        except Exception as exc:
            logger.warning("command_ack_error id=%s %s", command_id, exc)

    # ── main loop ────────────────────────────────────────────────────────────

    def run(self, stop_event: threading.Event) -> None:
        """Poll commands continuously until *stop_event* is set."""
        while not stop_event.is_set():
            self._poll_once()
            stop_event.wait(timeout=self._interval)
