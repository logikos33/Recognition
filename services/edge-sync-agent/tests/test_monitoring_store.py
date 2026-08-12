"""Tests do ring buffer de métricas (app/monitoring/store.py)."""

from __future__ import annotations

import json
import sqlite3

from app.monitoring.store import (
    MetricsReader,
    MetricsStore,
    aggregate_records,
)

# ── agregação (a semântica do downsample) ────────────────────────────────────


def test_aggregate_numbers_mean():
    merged = aggregate_records([{"cpu_pct": 10.0}, {"cpu_pct": 20.0}])
    assert merged["cpu_pct"] == 15.0


def test_aggregate_bool_becomes_fraction_of_window():
    """throttle.active True em 1 de 4 amostras → 0.25 (duração, não OR)."""
    records = [{"active": False}, {"active": True}, {"active": False}, {"active": False}]
    assert aggregate_records(records)["active"] == 0.25


def test_aggregate_total_counter_keeps_last():
    merged = aggregate_records([{"oom_kills_total": 2}, {"oom_kills_total": 3}])
    assert merged["oom_kills_total"] == 3


def test_aggregate_nested_dicts_recurse():
    merged = aggregate_records(
        [{"hw": {"ram_pct": 50.0}}, {"hw": {"ram_pct": 70.0}}]
    )
    assert merged["hw"]["ram_pct"] == 60.0


def test_aggregate_string_keeps_last():
    merged = aggregate_records([{"power_mode": "MAXN"}, {"power_mode": "MAXN_SUPER"}])
    assert merged["power_mode"] == "MAXN_SUPER"


def test_aggregate_number_lists_elementwise():
    merged = aggregate_records(
        [{"cpu_cores_pct": [10, 20]}, {"cpu_cores_pct": [30, 40]}]
    )
    assert merged["cpu_cores_pct"] == [20.0, 30.0]


def test_aggregate_mismatched_lists_keep_last():
    merged = aggregate_records([{"cores": [1, 2, 3]}, {"cores": [4, 5]}])
    assert merged["cores"] == [4, 5]


def test_aggregate_missing_field_does_not_zero_the_mean():
    """Campo ausente numa amostra não entra como 0 na média."""
    merged = aggregate_records([{"gpu_pct": 80.0}, {}, {"gpu_pct": 40.0}])
    assert merged["gpu_pct"] == 60.0


# ── escrita, rollup e retenção ───────────────────────────────────────────────


def _fill(store: MetricsStore, *, start: int, count: int, step: int = 10):
    for i in range(count):
        store.insert_sample(start + i * step, {"hw": {"cpu_pct": float(i % 50)}})


def test_insert_and_latest_roundtrip(tmp_path):
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    store.insert_sample(1000, {"hw": {"cpu_pct": 12.5}})
    reader = MetricsReader(db)
    latest = reader.latest()
    assert latest["ts"] == 1000
    assert latest["hw"]["cpu_pct"] == 12.5
    store.close()


def test_rollup_creates_1m_and_5m_buckets(tmp_path):
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    base = 1_000_000 - (1_000_000 % 600)  # alinhado em 10 min
    _fill(store, start=base, count=60)  # 10 minutos de amostras 10s
    store.maintain(base + 700)

    conn = sqlite3.connect(db)
    one_min = conn.execute("SELECT COUNT(*) FROM samples WHERE res='1m'").fetchone()[0]
    five_min = conn.execute("SELECT COUNT(*) FROM samples WHERE res='5m'").fetchone()[0]
    row = conn.execute(
        "SELECT data FROM samples WHERE res='1m' ORDER BY ts LIMIT 1"
    ).fetchone()
    conn.close()
    store.close()

    assert one_min >= 9  # buckets completos fecham; o corrente não
    assert five_min >= 1
    merged = json.loads(row[0])
    assert merged["agg_n"] == 6  # 6 amostras de 10s por bucket de 1m


def test_rollup_is_idempotent(tmp_path):
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    base = 600_000
    _fill(store, start=base, count=30)
    store.maintain(base + 400)
    store.maintain(base + 400)  # segunda passada não duplica

    conn = sqlite3.connect(db)
    counts = conn.execute(
        "SELECT res, COUNT(*) FROM samples GROUP BY res ORDER BY res"
    ).fetchall()
    conn.close()
    store.close()
    assert len([c for c in counts if c[0] == "1m"]) == 1


def test_retention_prunes_old_samples(tmp_path):
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    now = 10_000_000
    store.insert_sample(now - 3 * 3600, {"hw": {}})  # mais velho que 2h
    store.insert_sample(now - 60, {"hw": {}})
    store.maintain(now)

    conn = sqlite3.connect(db)
    remaining = conn.execute(
        "SELECT ts FROM samples WHERE res='10s' ORDER BY ts"
    ).fetchall()
    conn.close()
    store.close()
    assert [r[0] for r in remaining] == [now - 60]


def test_events_survive_and_are_pruned_at_30d(tmp_path):
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    now = 10_000_000
    store.insert_event(now - 31 * 86400, "throttle_start", "gpu")
    store.insert_event(now - 60, "oom_kill", "+1")
    store.maintain(now)
    reader = MetricsReader(db)
    result = reader.query("2h", now=now)
    store.close()
    assert [e["kind"] for e in result["events"]] == ["oom_kill"]


def test_disk_guard_blocks_writes(tmp_path, monkeypatch):
    db = tmp_path / "metrics.db"
    store = MetricsStore(db, min_free_gb=1.0)
    import shutil as _shutil

    fake = _shutil.disk_usage(tmp_path)._replace(free=100)  # ~0 livre
    monkeypatch.setattr("app.monitoring.store.shutil.disk_usage", lambda _: fake)
    store.maintain(1000)
    assert store.disk_guard_active is True
    assert store.insert_sample(2000, {"hw": {}}) is False
    store.close()


# ── leitura ──────────────────────────────────────────────────────────────────


def test_query_picks_resolution_by_window(tmp_path):
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    now = 5_000_000
    _fill(store, start=now - 1200, count=120)
    store.maintain(now)
    reader = MetricsReader(db)

    assert reader.query("2h", now=now)["resolution"] == "10s"
    assert reader.query("24h", now=now)["resolution"] == "1m"
    assert reader.query("30d", now=now)["resolution"] == "5m"
    store.close()


def test_query_thins_to_max_points_keeping_last(tmp_path):
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    now = 5_000_000
    _fill(store, start=now - 6000, count=600)
    reader = MetricsReader(db)
    result = reader.query("2h", max_points=50, now=now)
    assert len(result["samples"]) <= 51
    assert result["samples"][-1]["ts"] == now - 6000 + 599 * 10  # última preservada
    store.close()


def test_query_no_cap_keeps_all_samples(tmp_path):
    """max_points=None (default do reader) = sem corte: comportamento anterior
    de manter a resolução inteira."""
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    now = 5_000_000
    _fill(store, start=now - 6000, count=600)
    reader = MetricsReader(db)
    result = reader.query("2h", now=now)  # sem max_points
    assert len(result["samples"]) == 600
    assert result["thinned_stride"] == 1
    assert result["downsample"]["method"] == "none"
    assert result["layers"] is None
    store.close()


def test_query_max_points_caps_length(tmp_path):
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    now = 5_000_000
    _fill(store, start=now - 6000, count=600)
    reader = MetricsReader(db)
    result = reader.query("2h", max_points=100, now=now)
    assert len(result["samples"]) <= 100
    assert result["samples"][0]["ts"] == now - 6000  # primeira preservada
    assert result["samples"][-1]["ts"] == now - 6000 + 599 * 10  # última preservada
    assert result["downsample"]["method"] == "stride+extrema"
    assert result["downsample"]["input_points"] == 600
    assert result["downsample"]["output_points"] == len(result["samples"])
    store.close()


def test_query_downsample_preserves_spike(tmp_path):
    """Um pico isolado de cpu_pct entre pontos do stride TEM de sobreviver ao
    afinamento — é o requisito central do encolhimento server-side."""
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    now = 5_000_000
    spike_idx = 137
    for i in range(600):
        cpu = 99.9 if i == spike_idx else float(i % 7)  # pico solitário
        store.insert_sample(now - 6000 + i * 10, {"hw": {"cpu_pct": cpu}})
    reader = MetricsReader(db)
    result = reader.query("2h", max_points=40, now=now)
    cpus = [s["hw"]["cpu_pct"] for s in result["samples"]]
    assert 99.9 in cpus  # o pico não sumiu apesar do stride grosso
    assert len(result["samples"]) <= 40
    store.close()


def test_query_downsample_preserves_max_temp_spike(tmp_path):
    """Pico do MÁXIMO de temps_c (dict por zona) também sobrevive."""
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    now = 5_000_000
    hot_idx = 200
    for i in range(600):
        hot = 95.0 if i == hot_idx else 40.0
        store.insert_sample(
            now - 6000 + i * 10,
            {"hw": {"temps_c": {"cpu-thermal": hot, "gpu-thermal": 38.0}}},
        )
    reader = MetricsReader(db)
    result = reader.query("2h", max_points=30, now=now)
    max_temps = [max(s["hw"]["temps_c"].values()) for s in result["samples"]]
    assert 95.0 in max_temps
    store.close()


def test_query_layers_filter_drops_other_layers(tmp_path):
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    now = 5_000_000
    for i in range(20):
        store.insert_sample(
            now - 200 + i * 10,
            {
                "hw": {"cpu_pct": float(i)},
                "net": {"tx_kbps": float(i)},
                "svc": {"edge-sync-agent": {"active": "active"}},
                "versions": {"ota_channel": "stable"},
            },
        )
    reader = MetricsReader(db)
    result = reader.query("2h", layers=["hw", "net"], now=now)
    for sample in result["samples"]:
        assert set(sample.keys()) == {"ts", "hw", "net"}
        assert "svc" not in sample
        assert "versions" not in sample
    assert result["layers"] == ["hw", "net"]
    store.close()


def test_query_layers_filter_combined_with_max_points(tmp_path):
    """Filtro de camada e cap coexistem: extremos são achados ANTES do filtro,
    então o pico de cpu ainda sobrevive mesmo pedindo só ['hw']."""
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    now = 5_000_000
    for i in range(600):
        cpu = 88.0 if i == 300 else float(i % 5)
        store.insert_sample(
            now - 6000 + i * 10,
            {"hw": {"cpu_pct": cpu}, "net": {"tx_kbps": 1.0}, "svc": {"x": 1}},
        )
    reader = MetricsReader(db)
    result = reader.query("2h", layers=["hw"], max_points=40, now=now)
    assert len(result["samples"]) <= 40
    assert all(set(s.keys()) == {"ts", "hw"} for s in result["samples"])
    assert 88.0 in [s["hw"]["cpu_pct"] for s in result["samples"]]
    store.close()


def test_query_invalid_window_raises():
    reader = MetricsReader("/nonexistent/metrics.db")
    try:
        reader.query("6h")
        raise AssertionError("deveria ter levantado ValueError")
    except ValueError:
        pass


def test_reader_status_reports_down_without_db(tmp_path):
    reader = MetricsReader(tmp_path / "missing.db")
    status = reader.status()
    assert status["alive"] is False
    assert status["status"] == "down"


def test_reader_status_ok_and_stale(tmp_path):
    db = tmp_path / "metrics.db"
    store = MetricsStore(db)
    now = 5_000_000
    store.insert_sample(now - 5, {"hw": {}})
    reader = MetricsReader(db)
    assert reader.status(now=now)["status"] == "ok"
    assert reader.status(now=now + 200)["status"] == "stale"
    assert reader.status(now=now + 4000)["status"] == "down"
    store.close()
