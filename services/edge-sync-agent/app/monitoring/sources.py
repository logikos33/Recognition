"""Fontes de métrica do box — tegrastats, /sys, /proc, systemctl --user.

⛔ SEM jtop/jetson-stats: é AGPL-3.0 e este código é distribuído para o site
do cliente — o gate de licença do CI não olha este caminho, então a disciplina
é aqui. `tegrastats` é binário da NVIDIA (sem encargo) e /sys//proc são kernel.

Cada leitor recebe os paths como parâmetro (default = paths reais do Jetson)
para ser testável offline com uma árvore fake. Regra de honestidade herdada da
telemetria (task-100): sensor indisponível → campo ausente/None, nunca valor
inventado; leitor nenhum levanta — telemetria quebrada não pode derrubar o
coletor.

Confirmado no box real (Orin NX, JetPack 6.2, 2026-08-11):
  - cooling devices `*-throttle-alert` com cur_state>0 = throttling ativo —
    o sinal direto que o tegrastats não dá;
  - `/sys/class/devfreq/17000000.gpu/{cur,max}_freq` — frequência da GPU;
  - `nvpmodel -q` roda sem sudo (power mode; MAXN_SUPER no box);
  - `oom_kill` em /proc/vmstat — contador de OOM kills sem dmesg/sudo.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_THERMAL_ROOT = "/sys/devices/virtual/thermal"
_DEVFREQ_GPU = "/sys/class/devfreq/17000000.gpu"
_NET_ROOT = "/sys/class/net"
_SECTOR_BYTES = 512


def _read_text(path: str | Path) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _read_int(path: str | Path) -> int | None:
    raw = _read_text(path)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


# ── térmica / throttling ─────────────────────────────────────────────────────


def read_thermal_zones(root: str = _THERMAL_ROOT) -> dict[str, float]:
    """{'cpu-thermal': 51.7, ...} — temperatura por zona, em °C."""
    zones: dict[str, float] = {}
    try:
        entries = sorted(Path(root).glob("thermal_zone*"))
    except OSError:
        return zones
    for zone in entries:
        name = _read_text(zone / "type")
        temp = _read_int(zone / "temp")
        if name and temp is not None and temp > -100_000:  # sensor offline: -256000
            zones[name] = round(temp / 1000.0, 1)
    return zones


def read_throttle_state(root: str = _THERMAL_ROOT) -> dict[str, Any]:
    """Throttling térmico AGORA: cooling devices `*-throttle-alert` (e o
    hot-surface-alert) com cur_state > 0. O suspeito nº 1 de "ficou lento e
    ninguém sabe por quê" num Jetson dentro de fábrica."""
    active_devices: list[str] = []
    try:
        entries = sorted(Path(root).glob("cooling_device*"))
    except OSError:
        entries = []
    for dev in entries:
        name = _read_text(dev / "type") or ""
        if "alert" not in name:
            continue  # pwm-fan/cpufreq/devfreq têm cur_state>0 em operação normal
        cur = _read_int(dev / "cur_state")
        if cur is not None and cur > 0:
            active_devices.append(name)
    return {"active": bool(active_devices), "devices": active_devices}


def read_gpu_freq(devfreq_dir: str = _DEVFREQ_GPU) -> dict[str, int]:
    out: dict[str, int] = {}
    cur = _read_int(Path(devfreq_dir) / "cur_freq")
    mx = _read_int(Path(devfreq_dir) / "max_freq")
    if cur is not None:
        out["gpu_freq_hz"] = cur
    if mx is not None:
        out["gpu_freq_max_hz"] = mx
    return out


def read_power_mode(binary: str = "nvpmodel", timeout_s: float = 5.0) -> str | None:
    """`nvpmodel -q` → 'MAXN_SUPER' etc. Roda sem sudo no box (confirmado).
    Chamado 1x/min pelo sampler (não a cada tick) — custo desprezível."""
    try:
        proc = subprocess.run(  # noqa: S603
            [binary, "-q"], capture_output=True, text=True, timeout=timeout_s
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"NV Power Mode:\s*(\S+)", proc.stdout or "")
    return m.group(1) if m else None


# ── disco / memória / carga ──────────────────────────────────────────────────


def read_disk_usage(path: str = "/") -> dict[str, float]:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return {}
    return {
        "free_gb": round(usage.free / 1024**3, 2),
        "total_gb": round(usage.total / 1024**3, 2),
        "used_pct": round(100.0 * (usage.total - usage.free) / usage.total, 1),
    }


def read_disk_sectors_written(
    device: str = "nvme0n1", diskstats: str = "/proc/diskstats"
) -> int | None:
    """Setores escritos (campo 10 do /proc/diskstats) — o delta entre ticks
    vira taxa de escrita. Contador monotônico do kernel."""
    raw = _read_text(diskstats)
    if raw is None:
        return None
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) >= 10 and fields[2] == device:
            try:
                return int(fields[9])
            except ValueError:
                return None
    return None


def read_loadavg(path: str = "/proc/loadavg") -> dict[str, float]:
    raw = _read_text(path)
    if raw is None:
        return {}
    parts = raw.split()
    try:
        return {"load1": float(parts[0]), "load5": float(parts[1]), "load15": float(parts[2])}
    except (IndexError, ValueError):
        return {}


def read_uptime_s(path: str = "/proc/uptime") -> float | None:
    raw = _read_text(path)
    if raw is None:
        return None
    try:
        return float(raw.split()[0])
    except (IndexError, ValueError):
        return None


def read_oom_kill_total(path: str = "/proc/vmstat") -> int | None:
    """Contador acumulado de OOM kills do kernel — sem dmesg, sem sudo.
    Com 16 GB compartilhados por ffmpeg+sync+coleta+inferência, o delta > 0
    é o evento que ninguém pode descobrir tarde demais."""
    raw = _read_text(path)
    if raw is None:
        return None
    for line in raw.splitlines():
        if line.startswith("oom_kill "):
            try:
                return int(line.split()[1])
            except (IndexError, ValueError):
                return None
    return None


# ── rede ─────────────────────────────────────────────────────────────────────


def read_nic_counters(nic: str, net_root: str = _NET_ROOT) -> dict[str, int]:
    base = Path(net_root) / nic / "statistics"
    out: dict[str, int] = {}
    for key in ("rx_bytes", "tx_bytes", "rx_dropped", "tx_dropped"):
        value = _read_int(base / key)
        if value is not None:
            out[key] = value
    return out


def read_iface_up(iface: str, net_root: str = _NET_ROOT) -> bool | None:
    state = _read_text(Path(net_root) / iface / "operstate")
    if state is None:
        return None
    # tailscale0 (tun) reporta "unknown" mesmo UP — flags decidem.
    if state == "unknown":
        flags = _read_text(Path(net_root) / iface / "flags")
        if flags is None:
            return None
        try:
            return bool(int(flags, 16) & 0x1)  # IFF_UP
        except ValueError:
            return None
    return state == "up"


def read_default_gateway(route_path: str = "/proc/net/route") -> str | None:
    """IP do gateway default (hex little-endian no /proc/net/route) — alvo do
    ping LAN de perda/RTT local. Ping ao gateway NÃO é egress WAN."""
    raw = _read_text(route_path)
    if raw is None:
        return None
    for line in raw.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 3 and fields[1] == "00000000":
            try:
                gw = int(fields[2], 16)
            except ValueError:
                continue
            return f"{gw & 0xFF}.{(gw >> 8) & 0xFF}.{(gw >> 16) & 0xFF}.{(gw >> 24) & 0xFF}"
    return None


def ping_stats(
    target: str, *, count: int = 3, timeout_s: float = 4.0, binary: str = "ping"
) -> dict[str, float]:
    """RTT médio e perda (%) via ping. Usado 1x/min contra o GATEWAY LOCAL
    (zero egress WAN). O RTT até a API vem de carona no heartbeat
    (status_file.py) — nunca de um probe próprio, que seria egress."""
    try:
        proc = subprocess.run(  # noqa: S603
            [binary, "-c", str(count), "-W", "1", "-n", "-q", target],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    out: dict[str, float] = {}
    if m := re.search(r"(\d+(?:\.\d+)?)% packet loss", proc.stdout or ""):
        out["loss_pct"] = float(m.group(1))
    if m := re.search(r"= [\d.]+/([\d.]+)/", proc.stdout or ""):
        out["rtt_ms"] = float(m.group(1))
    return out


# ── serviços (units systemd --user) ──────────────────────────────────────────

_SYSTEMCTL_PROPS = (
    "Id,ActiveState,SubState,NRestarts,ExecMainStartTimestampMonotonic,"
    "MemoryCurrent,MemoryMax,CPUUsageNSec"
)


def read_user_units(
    units: list[str], *, binary: str = "systemctl", timeout_s: float = 10.0
) -> dict[str, dict[str, Any]]:
    """Estado das units --user num ÚNICO fork de systemctl por tick (blocos
    separados por linha em branco). Restart-loop é falha mascarada de "está
    rodando" — NRestarts é o campo que a denuncia."""
    if not units:
        return {}
    try:
        proc = subprocess.run(  # noqa: S603
            [binary, "--user", "show", *units, "--property", _SYSTEMCTL_PROPS],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("systemctl_show_falhou %s", exc)
        return {}
    return parse_systemctl_show(proc.stdout or "")


def parse_systemctl_show(output: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for block in output.strip().split("\n\n"):
        props: dict[str, str] = {}
        for line in block.splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                props[key] = value
        unit_id = props.get("Id", "").removesuffix(".service")
        if not unit_id:
            continue
        entry: dict[str, Any] = {
            "active": props.get("ActiveState"),
            "sub": props.get("SubState"),
        }
        if (raw := props.get("NRestarts", "")).isdigit():
            entry["nrestarts"] = int(raw)
        mem = props.get("MemoryCurrent", "")
        if mem.isdigit() and int(mem) < 2**62:  # [not set] vira 2^64-1
            entry["mem_mb"] = round(int(mem) / 1024 / 1024, 1)
        mem_max = props.get("MemoryMax", "")
        if mem_max.isdigit() and int(mem_max) < 2**62:
            entry["mem_max_mb"] = round(int(mem_max) / 1024 / 1024, 1)
        cpu_ns = props.get("CPUUsageNSec", "")
        if cpu_ns.isdigit():
            entry["cpu_usage_ns_total"] = int(cpu_ns)
        start_mono = props.get("ExecMainStartTimestampMonotonic", "")
        if start_mono.isdigit() and int(start_mono) > 0:
            try:
                mono_now_us = time.clock_gettime(time.CLOCK_MONOTONIC) * 1_000_000
                entry["uptime_s"] = max(0, round((mono_now_us - int(start_mono)) / 1_000_000))
            except (OSError, ValueError):
                pass
        result[unit_id] = entry
    return result


# ── artefatos de estado de outros processos ─────────────────────────────────


def read_json_file(path: str | Path) -> dict[str, Any] | None:
    """Lê um artefato JSON (status do live_view, net do heartbeat, estado do
    collector, status de inferência). Ausente/corrompido → None, com a idade
    do arquivo anexada em `_age_s` quando legível."""
    import json

    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        data["_age_s"] = max(0, round(time.time() - p.stat().st_mtime))
    except OSError:
        pass
    return data


def read_current_release(symlink: str | Path) -> str | None:
    """Release atual do OTA: o symlink `current` resolve para
    releases/<ref>/services/edge-sync-agent — devolve o <ref>."""
    try:
        target = Path(os.readlink(symlink))
    except OSError:
        return None
    for part in target.parts:
        if len(part) == 40 and all(c in "0123456789abcdef" for c in part.lower()):
            return part
    # fallback: o diretório logo abaixo de releases/
    parts = target.parts
    if "releases" in parts:
        idx = parts.index("releases")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return None
