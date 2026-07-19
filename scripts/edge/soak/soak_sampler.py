#!/usr/bin/env python3
"""soak_sampler.py — sampler do soak co-residente (task-113).

Complementa o coletor tegrastats (services/edge-sync-agent/app/telemetry, task-100),
que já cobre RAM/swap/EMC/GPU/temps/potência. Aqui coletamos o DELTA que o soak
de co-residência exige e que o tegrastats NÃO dá:

  - PSI (Pressure Stall Information): /proc/pressure/{memory,cpu,io}  → pressão real
  - swap in/out RATE: /proc/vmstat pswpin/pswpout (delta/s)          → thrashing
  - RAM por serviço: cgroup v2 memory.current por unit systemd       → quem cresce
  - OOM kills por cgroup: memory.events oom_kill                     → o pesadelo
  - latência da API: GET /api/v1/health, janela p50/p95              → SLA no soak
  - profundidade de fila Redis (opcional, via redis-cli)            → backpressure

Stdlib pura (roda no python3 de sistema do box — Ubuntu minimized, sem venv).
Cada probe é tolerante a falha (retorna None) — um /proc ausente não derruba a coleta.
Saída: 1 linha JSON por intervalo, etiquetada, append em --out. Testável offline
(as funções aceitam `root=` para apontar a uma árvore /proc/cgroup fake).

Uso no box:
    python3 soak_sampler.py --out /var/log/recognition/soak/soak_sampler.jsonl \
        --interval 5 --label soak \
        --units postgresql.service redis-server.service recognition-api.service \
                recognition-edge-sync.service recognition-edge-telemetry.service \
                recognition-deepstream@epi.service recognition-deepstream@parking.service \
                recognition-deepstream@quality-aux.service recognition-deepstream@quality-main.service \
        --api-url http://127.0.0.1:8000/api/v1/health --api-probes 5
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── PSI ─────────────────────────────────────────────────────────────────────────
def read_psi(resource: str, *, root: str = "/proc/pressure") -> dict[str, Any] | None:
    """Lê /proc/pressure/<resource>. Retorna {some_avg10, some_avg60, some_total,
    full_avg10, ...} ou None se PSI não estiver disponível (precisa psi=1)."""
    path = Path(root) / resource
    try:
        text = path.read_text()
    except OSError:
        return None
    out: dict[str, Any] = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        kind = parts[0]  # 'some' | 'full'
        for tok in parts[1:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                try:
                    out[f"{kind}_{k}"] = float(v)
                except ValueError:
                    pass
    return out or None


# ── vmstat / meminfo ─────────────────────────────────────────────────────────────
def _read_kv(path: Path, sep_colon: bool) -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        for line in path.read_text().splitlines():
            if sep_colon:
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                m = re.search(r"\d+", v)
                if m:
                    out[k.strip()] = int(m.group())
            else:
                parts = line.split()
                if len(parts) == 2 and parts[1].isdigit():
                    out[parts[0]] = int(parts[1])
    except OSError:
        pass
    return out


def read_vmstat(*, root: str = "/proc") -> dict[str, int]:
    return _read_kv(Path(root) / "vmstat", sep_colon=False)


def read_meminfo(*, root: str = "/proc") -> dict[str, int]:
    return _read_kv(Path(root) / "meminfo", sep_colon=True)  # valores em kB


# ── cgroup v2: RAM por serviço + OOM kills ───────────────────────────────────────
def _cgroup_unit_dir(unit: str, *, root: str = "/sys/fs/cgroup") -> Path:
    # systemd coloca services de sistema em system.slice/<unit>.
    return Path(root) / "system.slice" / unit


def read_service_mem(unit: str, *, root: str = "/sys/fs/cgroup") -> dict[str, Any] | None:
    """RAM atual (MB) + contador de oom_kill do cgroup do serviço, ou None."""
    d = _cgroup_unit_dir(unit, root=root)
    cur = d / "memory.current"
    try:
        current_mb = round(int(cur.read_text().strip()) / (1024 * 1024), 1)
    except OSError:
        return None
    oom_kill = 0
    try:
        for line in (d / "memory.events").read_text().splitlines():
            if line.startswith("oom_kill "):
                oom_kill = int(line.split()[1])
    except OSError:
        pass
    peak_mb = None
    try:
        peak_mb = round(int((d / "memory.peak").read_text().strip()) / (1024 * 1024), 1)
    except OSError:
        pass
    return {"ram_mb": current_mb, "peak_mb": peak_mb, "oom_kill": oom_kill}


# ── API latency ──────────────────────────────────────────────────────────────────
def probe_api_latency(url: str, *, probes: int = 5, timeout: float = 5.0) -> dict[str, Any] | None:
    """Faz N GETs e retorna min/p50/p95/max em ms + taxa de erro. None se url vazia."""
    if not url:
        return None
    samples_ms: list[float] = []
    errors = 0
    for _ in range(max(1, probes)):
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                resp.read(64)
                if resp.status >= 500:
                    errors += 1
        except Exception:
            errors += 1
            continue
        samples_ms.append((time.perf_counter() - t0) * 1000.0)
    if not samples_ms:
        return {"count": 0, "errors": errors, "err_rate": 1.0}
    s = sorted(samples_ms)
    return {
        "count": len(s),
        "errors": errors,
        "err_rate": round(errors / max(1, probes), 3),
        "min_ms": round(s[0], 1),
        "p50_ms": round(s[len(s) // 2], 1),
        "p95_ms": round(s[min(len(s) - 1, int(len(s) * 0.95))], 1),
        "max_ms": round(s[-1], 1),
    }


# ── Redis queue depth (opcional, via redis-cli) ──────────────────────────────────
def probe_redis(redis_url: str | None) -> dict[str, Any] | None:
    """INFO memory + nº de canais pub/sub. Usa redis-cli se existir; senão None."""
    if not redis_url or not shutil.which("redis-cli"):
        return None
    try:
        out = subprocess.run(
            ["redis-cli", "-u", redis_url, "INFO", "memory"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        used = None
        for line in out.splitlines():
            if line.startswith("used_memory:"):
                used = int(line.split(":", 1)[1])
        pubsub = subprocess.run(
            ["redis-cli", "-u", redis_url, "PUBSUB", "CHANNELS", "detections:*"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        n_channels = len([x for x in pubsub.splitlines() if x.strip()])
        return {"used_memory_mb": round((used or 0) / (1024 * 1024), 1),
                "detections_channels": n_channels}
    except Exception:
        return None


# ── loop ─────────────────────────────────────────────────────────────────────────
def build_sample(
    args: argparse.Namespace,
    prev_vmstat: dict[str, int],
    dt_s: float,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    vmstat = read_vmstat()
    meminfo = read_meminfo()

    def rate(key: str) -> float | None:
        if key in vmstat and key in prev_vmstat and dt_s > 0:
            return round((vmstat[key] - prev_vmstat[key]) / dt_s, 1)
        return None

    services = {}
    for unit in args.units:
        m = read_service_mem(unit)
        if m is not None:
            services[unit] = m

    rec: dict[str, Any] = {
        "ts": now.isoformat(),
        "label": args.label,
        "psi_mem": read_psi("memory"),
        "psi_cpu": read_psi("cpu"),
        "psi_io": read_psi("io"),
        "swap_in_per_s": rate("pswpin"),
        "swap_out_per_s": rate("pswpout"),
        "mem_total_mb": round(meminfo.get("MemTotal", 0) / 1024, 1),
        "mem_available_mb": round(meminfo.get("MemAvailable", 0) / 1024, 1),
        "swap_total_mb": round(meminfo.get("SwapTotal", 0) / 1024, 1),
        "swap_free_mb": round(meminfo.get("SwapFree", 0) / 1024, 1),
        "services": services,
        "services_oom_kill_total": sum(s.get("oom_kill", 0) for s in services.values()),
        "api": probe_api_latency(args.api_url, probes=args.api_probes),
        "redis": probe_redis(args.redis_url),
    }
    return rec


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Soak sampler (task-113)")
    p.add_argument("--out", required=True)
    p.add_argument("--interval", type=float, default=5.0)
    p.add_argument("--label", default="soak")
    p.add_argument("--units", nargs="*", default=[])
    p.add_argument("--api-url", default="")
    p.add_argument("--api-probes", type=int, default=5)
    p.add_argument("--redis-url", default="redis://127.0.0.1:6379/0")
    p.add_argument("--max-samples", type=int, default=0, help="0 = infinito")
    args = p.parse_args(argv)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    prev_vmstat = read_vmstat()
    prev_t = time.monotonic()
    n = 0
    try:
        while True:
            time.sleep(args.interval)
            now_t = time.monotonic()
            rec = build_sample(args, prev_vmstat, now_t - prev_t)
            prev_vmstat = read_vmstat()
            prev_t = now_t
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
            # alerta imediato no stderr se OOM kill aparecer (o pesadelo do soak)
            if rec["services_oom_kill_total"] > 0:
                print(f"[ALERTA] oom_kill detectado: {rec['services']}", file=sys.stderr)
            n += 1
            if args.max_samples and n >= args.max_samples:
                break
    except KeyboardInterrupt:
        pass
    print(f"soak_sampler: {n} amostras -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
