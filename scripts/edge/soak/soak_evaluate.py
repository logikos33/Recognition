#!/usr/bin/env python3
"""soak_evaluate.py — veredito GO/NO-GO do soak (task-113 FASE 5).

Lê o JSONL do soak_sampler (e opcionalmente o do coletor tegrastats) e decide:

  GO  se, na janela: SEM oom_kill · RAM estável (sem leak monotônico) · SEM swap
      thrashing sustentado · PSI de memória sob controle · API respondendo
      (err_rate baixo, p95 aceitável) · [tegrastats] sem throttle térmico.
  NO-GO caso contrário — listando EXATAMENTE o que falhou.

Stdlib pura. Imprime tabela markdown + veredito. Exit 0=GO, 1=NO-GO, 2=sem dados.

Uso:
    python3 soak_evaluate.py --sampler soak_sampler.jsonl \
        [--tegrastats telemetry.jsonl] [--min-hours 4] [--json]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _load(path: str) -> list[dict]:
    recs = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return recs


def _slope_per_hour(xs_iso: list[str], ys: list[float]) -> float | None:
    """Regressão linear simples: MB por hora. Positivo em mem_available = OK;
    negativo sustentado = leak (memória sumindo)."""
    pts = []
    t0 = None
    for iso, y in zip(xs_iso, ys):
        if y is None:
            continue
        try:
            t = datetime.fromisoformat(iso)
        except ValueError:
            continue
        if t0 is None:
            t0 = t
        pts.append(((t - t0).total_seconds() / 3600.0, y))
    if len(pts) < 3:
        return None
    n = len(pts)
    sx = sum(x for x, _ in pts); sy = sum(y for _, y in pts)
    sxx = sum(x * x for x, _ in pts); sxy = sum(x * y for x, y in pts)
    denom = n * sxx - sx * sx
    if denom == 0:
        return None
    return (n * sxy - sx * sy) / denom


def _stat(vals: list[float]) -> dict[str, float] | None:
    v = [x for x in vals if x is not None]
    if not v:
        return None
    s = sorted(v)
    return {"min": round(s[0], 1),
            "avg": round(sum(s) / len(s), 1),
            "p95": round(s[min(len(s) - 1, int(len(s) * 0.95))], 1),
            "max": round(s[-1], 1)}


def evaluate(sampler: list[dict], tegrastats: list[dict], min_hours: float) -> dict[str, Any]:
    reasons_fail: list[str] = []
    reasons_ok: list[str] = []
    metrics: dict[str, Any] = {}

    if not sampler:
        return {"verdict": "NO-DATA", "reasons_fail": ["JSONL do sampler vazio"],
                "reasons_ok": [], "metrics": {}}

    ts_list = [r.get("ts") for r in sampler]
    # duração
    try:
        dur_h = (datetime.fromisoformat(ts_list[-1]) - datetime.fromisoformat(ts_list[0])
                 ).total_seconds() / 3600.0
    except Exception:
        dur_h = 0.0
    metrics["duration_hours"] = round(dur_h, 2)
    if dur_h + 1e-9 < min_hours:
        reasons_fail.append(f"duração {dur_h:.2f}h < alvo {min_hours}h")
    else:
        reasons_ok.append(f"duração {dur_h:.2f}h ≥ {min_hours}h")

    # OOM kills (o pesadelo)
    oom = max((r.get("services_oom_kill_total", 0) or 0) for r in sampler)
    metrics["oom_kill_total"] = oom
    if oom > 0:
        reasons_fail.append(f"OOM kill detectado ({oom}) — INTOLERÁVEL")
    else:
        reasons_ok.append("zero OOM kills")

    # leak: slope de mem_available (MB/h). Queda > 5% do total por hora = suspeita.
    mem_avail = [r.get("mem_available_mb") for r in sampler]
    mem_total = next((r.get("mem_total_mb") for r in sampler if r.get("mem_total_mb")), 16000.0)
    slope = _slope_per_hour(ts_list, mem_avail)
    metrics["mem_available"] = _stat(mem_avail)
    metrics["mem_available_slope_mb_per_h"] = round(slope, 1) if slope is not None else None
    leak_thresh = -0.03 * (mem_total or 16000.0)  # -3%/h sustentado
    if slope is not None and slope < leak_thresh and dur_h >= 1:
        reasons_fail.append(
            f"RAM disponível caindo {slope:.0f} MB/h (< {leak_thresh:.0f}) — possível leak")
    elif slope is not None:
        reasons_ok.append(f"RAM disponível estável ({slope:+.0f} MB/h)")

    # per-service leak (o serviço que cresce)
    svc_growth = {}
    svc_names = set()
    for r in sampler:
        svc_names.update((r.get("services") or {}).keys())
    for name in sorted(svc_names):
        ys = [(r.get("services", {}).get(name) or {}).get("ram_mb") for r in sampler]
        sl = _slope_per_hour(ts_list, ys)
        if sl is not None:
            svc_growth[name] = round(sl, 1)
    metrics["service_ram_slope_mb_per_h"] = svc_growth
    leaky = {k: v for k, v in svc_growth.items() if v > 50 and dur_h >= 1}
    if leaky:
        reasons_fail.append(f"serviço(s) crescendo >50 MB/h: {leaky}")

    # swap thrashing: swap_out_per_s sustentado alto
    swap_out = [r.get("swap_out_per_s") for r in sampler]
    metrics["swap_out_per_s"] = _stat(swap_out)
    so = [x for x in swap_out if x is not None]
    # >20% das amostras com swap-out > 1000 páginas/s = thrashing
    if so and sum(1 for x in so if x > 1000) / len(so) > 0.2:
        reasons_fail.append("swap thrashing sustentado (>20% das amostras >1000 pg/s)")
    elif so:
        reasons_ok.append("sem swap thrashing sustentado")

    # PSI memória
    psi_full = [(r.get("psi_mem") or {}).get("full_avg60") for r in sampler]
    metrics["psi_mem_full_avg60"] = _stat(psi_full)
    pf = [x for x in psi_full if x is not None]
    if pf and max(pf) > 20:
        reasons_fail.append(f"PSI memória full_avg60 pico {max(pf):.1f}% (>20% = stall real)")
    elif pf:
        reasons_ok.append(f"PSI memória controlada (pico {max(pf):.1f}%)")
    elif not pf:
        reasons_ok.append("PSI indisponível (psi=1?) — não bloqueia, mas medir no próximo soak")

    # API
    api_p95 = [(r.get("api") or {}).get("p95_ms") for r in sampler]
    api_err = [(r.get("api") or {}).get("err_rate") for r in sampler]
    metrics["api_p95_ms"] = _stat(api_p95)
    ae = [x for x in api_err if x is not None]
    err_avg = round(sum(ae) / len(ae), 3) if ae else None
    metrics["api_err_rate_avg"] = err_avg
    if err_avg is not None and err_avg > 0.02:
        reasons_fail.append(f"API err_rate médio {err_avg:.1%} (>2%)")
    elif err_avg is not None:
        reasons_ok.append(f"API respondendo (err_rate {err_avg:.1%})")
    p95s = [x for x in api_p95 if x is not None]
    if p95s and (sum(1 for x in p95s if x > 1000) / len(p95s)) > 0.1:
        reasons_fail.append("API p95 > 1s em >10% das amostras")

    # tegrastats: throttle térmico (opcional)
    if tegrastats:
        gpu_t = [r.get("gpu_temp_c") for r in tegrastats]
        metrics["gpu_temp_c"] = _stat(gpu_t)
        gt = [x for x in gpu_t if x is not None]
        if gt and max(gt) >= 90:
            reasons_fail.append(f"throttle térmico: GPU {max(gt):.0f}°C (≥90)")
        elif gt:
            reasons_ok.append(f"térmica folgada (GPU máx {max(gt):.0f}°C)")
        ram_used = [r.get("ram_used_mb") for r in tegrastats]
        metrics["ram_used_mb"] = _stat(ram_used)

    verdict = "GO" if not reasons_fail else "NO-GO"
    return {"verdict": verdict, "reasons_fail": reasons_fail,
            "reasons_ok": reasons_ok, "metrics": metrics}


def _fmt_stat(s: dict | None) -> str:
    return f"{s['min']} / {s['avg']} / {s['p95']} / {s['max']}" if s else "—"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Soak GO/NO-GO evaluator (task-113)")
    p.add_argument("--sampler", required=True)
    p.add_argument("--tegrastats", default="")
    p.add_argument("--min-hours", type=float, default=4.0)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    sampler = _load(args.sampler)
    tegrastats = _load(args.tegrastats) if args.tegrastats else []
    res = evaluate(sampler, tegrastats, args.min_hours)

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        m = res["metrics"]
        print(f"\n{'='*60}\n VEREDITO SOAK: {res['verdict']}\n{'='*60}")
        print(f"Duração: {m.get('duration_hours')}h · amostras: {len(sampler)}")
        print("\n| Métrica | min / avg / p95 / max |")
        print("|---|---|")
        print(f"| RAM disponível (MB) | {_fmt_stat(m.get('mem_available'))} |")
        print(f"| swap-out (pg/s) | {_fmt_stat(m.get('swap_out_per_s'))} |")
        print(f"| PSI mem full_avg60 (%) | {_fmt_stat(m.get('psi_mem_full_avg60'))} |")
        print(f"| API p95 (ms) | {_fmt_stat(m.get('api_p95_ms'))} |")
        if m.get("ram_used_mb"):
            print(f"| RAM usada tegrastats (MB) | {_fmt_stat(m.get('ram_used_mb'))} |")
        if m.get("gpu_temp_c"):
            print(f"| GPU temp (°C) | {_fmt_stat(m.get('gpu_temp_c'))} |")
        print(f"\nOOM kills: {m.get('oom_kill_total')} · API err_rate médio: {m.get('api_err_rate_avg')}")
        print(f"slope RAM disp.: {m.get('mem_available_slope_mb_per_h')} MB/h")
        print(f"slope por serviço (MB/h): {m.get('service_ram_slope_mb_per_h')}")
        if res["reasons_fail"]:
            print("\n❌ FALHAS:")
            for r in res["reasons_fail"]:
                print(f"  - {r}")
        print("\n✅ OK:")
        for r in res["reasons_ok"]:
            print(f"  - {r}")

    if res["verdict"] == "NO-DATA":
        return 2
    return 0 if res["verdict"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
