"""Sampler — monta uma amostra completa (7 camadas) por tick de 10s.

Camadas e fontes:
  hw          tegrastats contínuo (thread do daemon atualiza `latest_tegra`)
              + /sys (térmica, throttle, devfreq GPU) + /proc (disco, load,
              uptime, OOM) + nvpmodel (1x/min, cacheado)
  svc         systemctl --user show (um fork por tick, todas as units juntas)
  net         contadores do NIC + tailscale up + ping ao GATEWAY local (1x/min)
              + RTT da API de carona no heartbeat (net.json)
  pipeline    live_view.json (escrito pelo edge-live-view via LiveViewStatus)
  collection  collector_state.json do edge-frame-collector (contadores por
              câmera; "frames hoje" = delta calculado sobre o histórico)
  versions    symlink `current` do OTA + OTA_CHANNEL + EDGE_VERSION
  inference   inference.json (contrato pronto; vazio até os modelos ligarem —
              o arquivo é a interface que o runtime de inferência preenche)

Eventos discretos detectados por transição entre ticks: throttle_start/end,
oom_kill (delta do contador), power_mode_change, service_restart (delta de
NRestarts). São o que a página mostra como "aconteceu X" — não podem se
perder no downsample, por isso vão para a tabela `events`, não para a amostra.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable

from ..telemetry.tegrastats_parser import TegrastatsSample
from . import sources

logger = logging.getLogger(__name__)

_SECTOR_BYTES = 512
_SLOW_REFRESH_S = 60.0  # power mode + ping ao gateway: 1x/min, não por tick

DEFAULT_UNITS = [
    "edge-sync-agent",
    "edge-live-view",
    "edge-frame-collector",
    "edge-monitoring-collector",
    "edge-sync-agent-updater",
]


class MonitoringSampler:
    """Estado entre ticks (deltas de contadores) + montagem da amostra."""

    def __init__(
        self,
        *,
        units: list[str],
        nic: str,
        live_view_status_path: str | Path,
        net_status_path: str | Path,
        inference_status_path: str | Path,
        collector_state_path: str | Path,
        ota_current_symlink: str | Path,
        ota_channel: str,
        edge_version: str | None,
        disk_min_free_gb: float,
        on_event: Callable[[int, str, str], None],
    ) -> None:
        self._units = units
        self._nic = nic
        self._live_view_status_path = live_view_status_path
        self._net_status_path = net_status_path
        self._inference_status_path = inference_status_path
        self._collector_state_path = collector_state_path
        self._ota_current_symlink = ota_current_symlink
        self._ota_channel = ota_channel
        self._edge_version = edge_version
        self._disk_min_free_gb = disk_min_free_gb
        self._on_event = on_event

        self._lock = threading.Lock()
        self._latest_tegra: TegrastatsSample | None = None
        self._latest_tegra_ts = 0.0

        # deltas entre ticks
        self._prev_tick_ts: float | None = None
        self._prev_disk_sectors: int | None = None
        self._prev_nic: dict[str, int] = {}
        self._prev_cpu_ns: dict[str, int] = {}
        self._prev_nrestarts: dict[str, int] = {}
        self._prev_oom_total: int | None = None
        self._prev_throttle_active = False
        self._prev_power_mode: str | None = None

        # refresh lento (1x/min)
        self._slow_refresh_ts = 0.0
        self._power_mode: str | None = None
        self._gw_ping: dict[str, float] = {}

    # ── alimentação pelo thread do tegrastats ────────────────────────────────

    def update_tegra(self, sample: TegrastatsSample) -> None:
        with self._lock:
            self._latest_tegra = sample
            self._latest_tegra_ts = time.time()

    # ── montagem ─────────────────────────────────────────────────────────────

    def build_sample(self, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        ts = int(now)
        self._maybe_slow_refresh(now)

        record = {
            "ts": ts,
            "hw": self._layer_hw(now),
            "svc": self._layer_svc(ts),
            "net": self._layer_net(now),
            "pipeline": self._layer_pipeline(),
            "collection": self._layer_collection(),
            "versions": self._layer_versions(),
            "inference": self._layer_inference(),
        }
        self._prev_tick_ts = now
        return record

    def _maybe_slow_refresh(self, now: float) -> None:
        if now - self._slow_refresh_ts < _SLOW_REFRESH_S:
            return
        self._slow_refresh_ts = now
        mode = sources.read_power_mode()
        if mode is not None:
            if self._prev_power_mode is not None and mode != self._prev_power_mode:
                self._on_event(
                    int(now),
                    "power_mode_change",
                    f"{self._prev_power_mode} -> {mode}",
                )
            self._prev_power_mode = mode
            self._power_mode = mode
        gateway = sources.read_default_gateway()
        self._gw_ping = sources.ping_stats(gateway) if gateway else {}

    # ── camadas ──────────────────────────────────────────────────────────────

    def _layer_hw(self, now: float) -> dict[str, Any]:
        hw: dict[str, Any] = {}
        with self._lock:
            tegra = self._latest_tegra
            tegra_age = now - self._latest_tegra_ts if self._latest_tegra_ts else None
        if tegra is not None and tegra_age is not None and tegra_age < 60:
            hw.update(
                {
                    "cpu_pct": tegra.cpu_pct,
                    "cpu_cores_pct": tegra.cpu_cores_pct,
                    "ram_used_mb": tegra.ram_used_mb,
                    "ram_total_mb": tegra.ram_total_mb,
                    "ram_pct": tegra.ram_pct,
                    "swap_used_mb": tegra.swap_used_mb,
                    "swap_total_mb": tegra.swap_total_mb,
                    "emc_pct": tegra.emc_pct,
                    "gpu_pct": tegra.gpu_pct,
                    "power_mw": tegra.power_mw or None,
                }
            )

        temps = sources.read_thermal_zones()
        if temps:
            hw["temps_c"] = temps
        elif tegra is not None and tegra.temps_c:
            hw["temps_c"] = tegra.temps_c  # fora do Jetson real (testes)

        throttle = sources.read_throttle_state()
        hw["throttle"] = throttle
        if throttle["active"] and not self._prev_throttle_active:
            self._on_event(int(now), "throttle_start", ",".join(throttle["devices"]))
        elif not throttle["active"] and self._prev_throttle_active:
            self._on_event(int(now), "throttle_end", "")
        self._prev_throttle_active = bool(throttle["active"])

        hw.update(sources.read_gpu_freq())
        if self._power_mode:
            hw["power_mode"] = self._power_mode

        disk = sources.read_disk_usage("/")
        sectors = sources.read_disk_sectors_written()
        if sectors is not None and self._prev_disk_sectors is not None and self._prev_tick_ts:
            elapsed = max(1e-3, now - self._prev_tick_ts)
            delta = max(0, sectors - self._prev_disk_sectors)
            disk["write_mbps"] = round(delta * _SECTOR_BYTES / elapsed / 1024 / 1024, 3)
        self._prev_disk_sectors = sectors
        if disk:
            disk["min_free_gb"] = self._disk_min_free_gb
            if "free_gb" in disk:
                disk["distance_to_reserve_gb"] = round(
                    disk["free_gb"] - self._disk_min_free_gb, 2
                )
            hw["disk"] = disk

        hw.update(sources.read_loadavg())
        uptime = sources.read_uptime_s()
        if uptime is not None:
            hw["uptime_s"] = round(uptime)

        oom = sources.read_oom_kill_total()
        if oom is not None:
            hw["oom_kills_total"] = oom
            if self._prev_oom_total is not None and oom > self._prev_oom_total:
                self._on_event(
                    int(now), "oom_kill", f"+{oom - self._prev_oom_total} (total {oom})"
                )
            self._prev_oom_total = oom
        return hw

    def _layer_svc(self, ts: int) -> dict[str, Any]:
        units = sources.read_user_units(self._units)
        for name, entry in units.items():
            cpu_ns = entry.get("cpu_usage_ns_total")
            prev_ns = self._prev_cpu_ns.get(name)
            if (
                cpu_ns is not None
                and prev_ns is not None
                and self._prev_tick_ts is not None
            ):
                elapsed_ns = max(1.0, (ts - self._prev_tick_ts) * 1e9)
                entry["cpu_pct"] = round(100.0 * max(0, cpu_ns - prev_ns) / elapsed_ns, 2)
            if cpu_ns is not None:
                self._prev_cpu_ns[name] = cpu_ns

            nrestarts = entry.get("nrestarts")
            prev_restarts = self._prev_nrestarts.get(name)
            if (
                nrestarts is not None
                and prev_restarts is not None
                and nrestarts > prev_restarts
            ):
                self._on_event(
                    ts, "service_restart", f"{name} (+{nrestarts - prev_restarts})"
                )
            if nrestarts is not None:
                self._prev_nrestarts[name] = nrestarts
        return units

    def _layer_net(self, now: float) -> dict[str, Any]:
        net: dict[str, Any] = {"nic": self._nic}
        counters = sources.read_nic_counters(self._nic)
        if counters and self._prev_nic and self._prev_tick_ts:
            elapsed = max(1e-3, now - self._prev_tick_ts)
            for key, out_key in (("tx_bytes", "tx_kbps"), ("rx_bytes", "rx_kbps")):
                if key in counters and key in self._prev_nic:
                    delta = max(0, counters[key] - self._prev_nic[key])
                    net[out_key] = round(delta * 8 / elapsed / 1000, 1)
        if counters:
            net["tx_bytes_total"] = counters.get("tx_bytes")
            net["rx_bytes_total"] = counters.get("rx_bytes")
            self._prev_nic = counters

        ts_up = sources.read_iface_up("tailscale0")
        if ts_up is not None:
            net["tailscale_up"] = ts_up
        if self._gw_ping:
            net["gw_rtt_ms"] = self._gw_ping.get("rtt_ms")
            net["gw_loss_pct"] = self._gw_ping.get("loss_pct")

        api_status = sources.read_json_file(self._net_status_path)
        if api_status is not None:
            net["api_rtt_ms"] = api_status.get("api_rtt_ms")
            net["api_ok"] = bool(api_status.get("ok"))
            net["api_status_age_s"] = api_status.get("_age_s")
        return net

    def _layer_pipeline(self) -> dict[str, Any]:
        status = sources.read_json_file(self._live_view_status_path)
        if status is None:
            return {"available": False}
        return {
            "available": True,
            "cameras": status.get("cameras") or {},
            "source_age_s": status.get("_age_s"),
        }

    def _layer_collection(self) -> dict[str, Any]:
        state = sources.read_json_file(self._collector_state_path)
        if state is None:
            return {"available": False}
        counts = state.get("frames_uploaded") or {}
        cameras = {cam: {"frames_uploaded": count} for cam, count in counts.items()}
        return {
            "available": True,
            "cameras": cameras,
            "state_age_s": state.get("_age_s"),
        }

    def _layer_versions(self) -> dict[str, Any]:
        versions: dict[str, Any] = {"ota_channel": self._ota_channel}
        ref = sources.read_current_release(self._ota_current_symlink)
        if ref:
            versions["current_ref"] = ref
        if self._edge_version:
            versions["edge_version"] = self._edge_version
        return versions

    def _layer_inference(self) -> dict[str, Any]:
        """Contrato do runtime de inferência (operação assistida): quando os
        modelos ligarem, o runtime escreve inference.json com
        {ts, cameras: {<id>: {model, model_version, fps, latency_ms,
        dropped_total, detections_per_min: {<classe>: n},
        last_detection_ts}}}. Até lá: available=False — o painel existe e diz
        honestamente que está vazio (silêncio ≠ boa notícia)."""
        status = sources.read_json_file(self._inference_status_path)
        if status is None:
            return {"available": False}
        return {
            "available": True,
            "cameras": status.get("cameras") or {},
            "source_age_s": status.get("_age_s"),
        }
