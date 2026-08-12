"""Tests dos leitores de /sys//proc/systemctl (app/monitoring/sources.py).

Tudo offline: árvore sysfs/procfs fake em tmp_path — mesmo espírito do parser
de tegrastats (testável sem Jetson)."""

from __future__ import annotations

from app.monitoring import sources

# ── térmica / throttle ───────────────────────────────────────────────────────


def _make_zone(root, idx, name, temp_milli):
    zone = root / f"thermal_zone{idx}"
    zone.mkdir(parents=True)
    (zone / "type").write_text(name)
    (zone / "temp").write_text(str(temp_milli))


def _make_cooling(root, idx, name, cur):
    dev = root / f"cooling_device{idx}"
    dev.mkdir(parents=True)
    (dev / "type").write_text(name)
    (dev / "cur_state").write_text(str(cur))
    (dev / "max_state").write_text("3")


def test_read_thermal_zones(tmp_path):
    _make_zone(tmp_path, 0, "cpu-thermal", 51687)
    _make_zone(tmp_path, 1, "gpu-thermal", 48500)
    _make_zone(tmp_path, 2, "cv0-thermal", -256000)  # sensor offline
    zones = sources.read_thermal_zones(str(tmp_path))
    assert zones == {"cpu-thermal": 51.7, "gpu-thermal": 48.5}


def test_throttle_only_alert_devices_count(tmp_path):
    """pwm-fan em cur_state alto é operação normal; só *-alert é throttle."""
    _make_cooling(tmp_path, 0, "pwm-fan", 3)
    _make_cooling(tmp_path, 1, "gpu-throttle-alert", 0)
    assert sources.read_throttle_state(str(tmp_path)) == {"active": False, "devices": []}

    _make_cooling(tmp_path, 2, "cpu-throttle-alert", 1)
    state = sources.read_throttle_state(str(tmp_path))
    assert state["active"] is True
    assert state["devices"] == ["cpu-throttle-alert"]


# ── /proc ────────────────────────────────────────────────────────────────────


def test_read_oom_kill_total(tmp_path):
    vmstat = tmp_path / "vmstat"
    vmstat.write_text("nr_free_pages 100\noom_kill 7\n")
    assert sources.read_oom_kill_total(str(vmstat)) == 7


def test_read_oom_kill_missing_field(tmp_path):
    vmstat = tmp_path / "vmstat"
    vmstat.write_text("nr_free_pages 100\n")
    assert sources.read_oom_kill_total(str(vmstat)) is None


def test_read_disk_sectors_written(tmp_path):
    diskstats = tmp_path / "diskstats"
    diskstats.write_text(
        " 259 0 nvme0n1 310686 36030 29426338 128873 110573373 2528131"
        " 1306504450 215042529 0 1 2\n"
        " 259 1 nvme0n1p1 1 2 3 4 5 6 7 8 9 10 11\n"
    )
    assert sources.read_disk_sectors_written("nvme0n1", str(diskstats)) == 1306504450


def test_read_loadavg(tmp_path):
    p = tmp_path / "loadavg"
    p.write_text("1.50 2.25 3.00 2/1234 99999\n")
    assert sources.read_loadavg(str(p)) == {"load1": 1.5, "load5": 2.25, "load15": 3.0}


def test_read_default_gateway_little_endian(tmp_path):
    route = tmp_path / "route"
    # 192.168.35.1 → hex little-endian 0123A8C0
    route.write_text(
        "Iface\tDestination\tGateway\tFlags\n"
        "enP8p1s0\t00000000\t0123A8C0\t0003\n"
    )
    assert sources.read_default_gateway(str(route)) == "192.168.35.1"


# ── rede via sysfs ───────────────────────────────────────────────────────────


def test_read_nic_counters(tmp_path):
    stats = tmp_path / "eth0" / "statistics"
    stats.mkdir(parents=True)
    (stats / "tx_bytes").write_text("12345")
    (stats / "rx_bytes").write_text("67890")
    counters = sources.read_nic_counters("eth0", str(tmp_path))
    assert counters["tx_bytes"] == 12345
    assert counters["rx_bytes"] == 67890


def test_read_iface_up_tun_unknown_uses_flags(tmp_path):
    iface = tmp_path / "tailscale0"
    iface.mkdir(parents=True)
    (iface / "operstate").write_text("unknown")
    (iface / "flags").write_text("0x1")
    assert sources.read_iface_up("tailscale0", str(tmp_path)) is True


# ── systemctl show ───────────────────────────────────────────────────────────

_SHOW_OUTPUT = """\
Id=edge-live-view.service
ActiveState=active
SubState=running
NRestarts=2
ExecMainStartTimestampMonotonic=123456789
MemoryCurrent=104857600
MemoryMax=805306368
CPUUsageNSec=5000000000

Id=edge-sync-agent.service
ActiveState=active
SubState=running
NRestarts=0
ExecMainStartTimestampMonotonic=0
MemoryCurrent=[not set]
MemoryMax=18446744073709551615
CPUUsageNSec=1000000000
"""


def test_parse_systemctl_show_two_units():
    units = sources.parse_systemctl_show(_SHOW_OUTPUT)
    lv = units["edge-live-view"]
    assert lv["active"] == "active"
    assert lv["nrestarts"] == 2
    assert lv["mem_mb"] == 100.0
    assert lv["mem_max_mb"] == 768.0
    assert lv["cpu_usage_ns_total"] == 5_000_000_000

    sa = units["edge-sync-agent"]
    assert "mem_mb" not in sa  # [not set]
    assert "mem_max_mb" not in sa  # infinity (2^64-1) não é teto real
    assert "uptime_s" not in sa  # timestamp monotônico zerado


# ── artefatos JSON / release ─────────────────────────────────────────────────


def test_read_json_file_adds_age(tmp_path):
    p = tmp_path / "status.json"
    p.write_text('{"cameras": {}}')
    data = sources.read_json_file(p)
    assert data is not None
    assert "_age_s" in data


def test_read_json_file_corrupt_returns_none(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{nope")
    assert sources.read_json_file(p) is None


def test_read_current_release_from_symlink(tmp_path):
    sha = "224f1fb3c820beced88d39f509decb363802576e"
    target = tmp_path / "releases" / sha / "services" / "edge-sync-agent"
    target.mkdir(parents=True)
    link = tmp_path / "current"
    link.symlink_to(target)
    assert sources.read_current_release(link) == sha


def test_read_current_release_missing_symlink(tmp_path):
    assert sources.read_current_release(tmp_path / "current") is None
