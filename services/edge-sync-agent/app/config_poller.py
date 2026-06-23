"""Config poller: pulls scenario / model manifest from cloud, applies in memory.

State is held in a thread-safe ConfigState.  Callers read cameras/rules/scenario
via accessors.  When a new model is available, get_model_manifest() returns the
manifest; call ack_model_applied() after download to clear the pending entry.

No restart is needed to apply new config — the poller updates in-process state.
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DEFAULT_INTERVAL = 300.0  # 5 minutes


@dataclass
class ModelManifest:
    sha256: str
    url: str
    engine_type: str


@dataclass
class _ConfigState:
    cameras: list[dict] = field(default_factory=list)
    rules: list[dict] = field(default_factory=list)
    scenario: dict = field(default_factory=dict)
    pending_model: Optional[ModelManifest] = None
    current_model_sha256: str = ""


class ConfigPoller:
    """Periodically fetches edge config from the cloud and applies it in memory."""

    def __init__(
        self,
        http_client: Any,
        cloud_url: str,
        device_id: str,
        token: str,
        poll_interval_s: float = _DEFAULT_INTERVAL,
    ) -> None:
        self._http = http_client
        self._url = f"{cloud_url.rstrip('/')}/api/v1/edge/config/poll"
        self._device_id = device_id
        self._token = token
        self._interval = poll_interval_s
        self._state = _ConfigState()
        self._lock = threading.RLock()

    # ── public accessors (thread-safe) ───────────────────────────────────────

    def get_cameras(self) -> list[dict]:
        with self._lock:
            return list(self._state.cameras)

    def get_rules(self) -> list[dict]:
        with self._lock:
            return list(self._state.rules)

    def get_scenario(self) -> dict:
        with self._lock:
            return dict(self._state.scenario)

    def get_model_manifest(self) -> Optional[ModelManifest]:
        """Returns the pending manifest if a new model is available, else None."""
        with self._lock:
            return self._state.pending_model

    def get_current_model_sha256(self) -> str:
        with self._lock:
            return self._state.current_model_sha256

    def ack_model_applied(self, sha256: str) -> None:
        """Call after model_manager swaps the model — clears pending entry."""
        with self._lock:
            self._state.current_model_sha256 = sha256
            self._state.pending_model = None

    # ── internal ─────────────────────────────────────────────────────────────

    def _poll_once(self) -> bool:
        """Issue one config poll. Returns True if cloud responded OK."""
        try:
            resp = self._http.get(
                self._url,
                params={
                    "device_id": self._device_id,
                    "current_model_sha256": self._state.current_model_sha256,
                },
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=15.0,
            )
            if resp.status_code != 200:
                logger.warning("config_poll_failed status=%d", resp.status_code)
                return False
            self._apply(resp.json())
            return True
        except Exception as exc:
            logger.warning("config_poll_error %s", exc)
            return False

    def _apply(self, data: dict) -> None:
        with self._lock:
            # Partial updates: only keys present in the response are applied.
            if "cameras" in data:
                self._state.cameras = list(data["cameras"])
            if "rules" in data:
                self._state.rules = list(data["rules"])
            if "scenario" in data:
                self._state.scenario = dict(data["scenario"])

            model_data = data.get("model")
            if model_data and model_data.get("sha256") != self._state.current_model_sha256:
                self._state.pending_model = ModelManifest(
                    sha256=model_data["sha256"],
                    url=model_data["url"],
                    engine_type=model_data.get("engine_type", "pt"),
                )
                logger.info("new_model_available sha256=%s", self._state.pending_model.sha256)
            else:
                # No new model (null response or same sha256)
                self._state.pending_model = None

    # ── main loop ────────────────────────────────────────────────────────────

    def run(self, stop_event: threading.Event) -> None:
        """Poll config continuously until *stop_event* is set."""
        while not stop_event.is_set():
            self._poll_once()
            stop_event.wait(timeout=self._interval)
