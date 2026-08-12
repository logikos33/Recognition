"""Command poller: consumes edge_commands from the cloud and acks results.

Polls GET /api/v1/edge/commands/pending (device auth) and applies supported
command types:

  - update_camera_config → ConfigPoller.apply_camera_config (in-memory, no restart)

Unknown command types are acked as failed with result={'reason': 'unsupported'}
so the queue never clogs. Every command is acked exactly once per poll cycle
via PATCH /api/v1/edge/commands/<command_id>.

Same pattern as ConfigPoller: injected http_client, run(stop_event) loop.
"""

import logging
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DEFAULT_INTERVAL = 60.0  # 1 minute


class CommandPoller:
    """Periodically fetches pending edge commands and executes them."""

    def __init__(
        self,
        http_client: Any,
        cloud_url: str,
        token: str,
        config_poller: Any,
        poll_interval_s: float = _DEFAULT_INTERVAL,
    ) -> None:
        self._http = http_client
        base = cloud_url.rstrip("/")
        self._pending_url = f"{base}/api/v1/edge/commands/pending"
        self._ack_url_base = f"{base}/api/v1/edge/commands"
        self._token = token
        self._config_poller = config_poller
        self._interval = poll_interval_s

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
        for cmd in commands:
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
        else:
            # Unknown type: ack failed so the queue never clogs.
            logger.warning("command_unsupported type=%s id=%s", command_type, command_id)
            self._ack(command_id, "failed", {"reason": "unsupported"})

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
