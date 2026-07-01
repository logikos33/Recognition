"""
Benchmark de escala staging — 4→8→16→28 câmeras, mede ponto de degradação.

Para cada tier:
  1. Inicia harness com N câmeras (POST /harness/start)
  2. Aguarda warmup (WARMUP_SEC) para estabilização
  3. Coleta K amostras de status (poll a cada POLL_INTERVAL)
  4. Para harness (POST /harness/stop)
  5. Registra: alerts/min, streams ativos, erros

Ponto de degradação = primeiro tier onde alerts/min cai >50% do pico.

Uso:
  export STAGING_URL=https://api-v3-production-2b22.up.railway.app
  export ADMIN_EMAIL=test-admin@epi-ci.internal
  export ADMIN_PASSWORD=...
  python3 scripts/staging_scale_bench.py [--tiers 4,8,16,28] [--warmup 30] [--samples 5]

Entregável: docs/evidence/e2e-scale/REPORT.md + raw.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

STAGING_URL  = os.environ.get("STAGING_URL", "https://api-v3-production-2b22.up.railway.app")
ADMIN_EMAIL  = os.environ.get("ADMIN_EMAIL",  "test-admin@epi-ci.internal")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
EVIDENCE_DIR = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "e2e-scale"

DEFAULT_TIERS = [4, 8, 16, 28]


class StagingClient:
    def __init__(self, base_url: str) -> None:
        self.base  = base_url.rstrip("/")
        self.token: str | None = None

    def _req(self, method: str, path: str, body: dict | None = None) -> dict:
        url  = f"{self.base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        hdrs: dict = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            hdrs["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)  # noqa: S310
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode() if exc.fp else ""
            raise RuntimeError(f"HTTP {exc.code} {method} {url}: {body_text[:300]}") from exc

    def login(self, email: str, password: str) -> None:
        resp  = self._req("POST", "/api/auth/login", {"email": email, "password": password})
        token = resp.get("token") or resp.get("data", {}).get("token")
        if not token:
            raise RuntimeError(f"Login falhou: {resp}")
        self.token = token
        logger.info("Login OK: %s", email)

    def start_harness(self, cameras: int, model_id: str | None = None) -> dict:
        body: dict = {"cameras": cameras}
        if model_id:
            body["model_id"] = model_id
        return self._req("POST", "/api/v1/admin/test-console/harness/start", body).get("data", {})

    def status(self) -> dict:
        return self._req("GET", "/api/v1/admin/test-console/status").get("data", {})

    def stop_harness(self) -> dict:
        return self._req("POST", "/api/v1/admin/test-console/harness/stop", {}).get("data", {})


def measure_tier(
    client: StagingClient,
    cameras: int,
    warmup: int,
    n_samples: int,
    poll_interval: int,
    model_id: str | None,
) -> dict:
    logger.info("═══ Tier %d câmeras ═══", cameras)

    # Start
    t0 = time.monotonic()
    start_result = client.start_harness(cameras, model_id)
    logger.info("Harness iniciado: %s", start_result)

    # Warmup
    logger.info("Warmup %ds...", warmup)
    time.sleep(warmup)

    # Collect samples
    alerts_baseline = client.status().get("alerts_generated", 0)
    samples: list[dict] = []
    for i in range(n_samples):
        time.sleep(poll_interval)
        s = client.status()
        samples.append(s)
        logger.info(
            "  [%d/%d] active=%s streams=%d alerts=%d",
            i + 1, n_samples,
            s.get("active"), s.get("active_streams", 0), s.get("alerts_generated", 0),
        )

    duration_sec = time.monotonic() - t0

    # Compute metrics
    alerts_end = samples[-1].get("alerts_generated", 0) if samples else 0
    alerts_delta = max(0, alerts_end - alerts_baseline)
    observation_sec = n_samples * poll_interval
    alerts_per_min = (alerts_delta / observation_sec * 60) if observation_sec > 0 else 0
    active_streams = samples[-1].get("active_streams", 0) if samples else 0
    stream_ratio   = (active_streams / cameras) if cameras > 0 else 0

    # Stop
    stop_result = client.stop_harness()
    logger.info("Harness parado: %s", stop_result)

    return {
        "cameras": cameras,
        "alerts_per_min": round(alerts_per_min, 2),
        "alerts_delta": alerts_delta,
        "active_streams": active_streams,
        "stream_ratio": round(stream_ratio, 3),
        "duration_sec": round(duration_sec, 1),
        "samples": samples,
        "start_result": start_result,
    }


def find_degradation(results: list[dict], threshold: float = 0.5) -> int | None:
    """Retorna índice do primeiro tier com alerts/min < threshold * peak."""
    peak = max((r["alerts_per_min"] for r in results), default=0.0)
    if peak == 0:
        return None
    for i, r in enumerate(results):
        if r["alerts_per_min"] < peak * threshold:
            return i
    return None


def write_report(results: list[dict], degradation_idx: int | None, args: argparse.Namespace) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    # Raw JSON
    raw_path = EVIDENCE_DIR / "raw.json"
    raw_path.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "staging_url": args.staging_url,
        "warmup_sec": args.warmup,
        "n_samples": args.samples,
        "poll_interval_sec": args.poll_interval,
        "results": results,
        "degradation_tier_index": degradation_idx,
        "degradation_cameras": results[degradation_idx]["cameras"] if degradation_idx is not None else None,
    }, indent=2))

    # Markdown report
    md_lines = [
        "# Benchmark de Escala — Staging",
        "",
        f"**Gerado em**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**URL staging**: `{args.staging_url}`",
        f"**Warmup por tier**: {args.warmup}s | **Amostras**: {args.samples} × {args.poll_interval}s",
        "",
        "## Resultados por Tier",
        "",
        "| Câmeras | Alerts/min | Streams ativos | Stream ratio | Dur. (s) |",
        "|--------:|-----------:|---------------:|-------------:|---------:|",
    ]
    for i, r in enumerate(results):
        marker = " ⚠️ DEGRADAÇÃO" if i == degradation_idx else ""
        md_lines.append(
            f"| {r['cameras']} | {r['alerts_per_min']:.1f} | {r['active_streams']} "
            f"| {r['stream_ratio']:.2f} | {r['duration_sec']:.0f} |{marker}"
        )

    if degradation_idx is not None:
        deg = results[degradation_idx]
        prev = results[degradation_idx - 1] if degradation_idx > 0 else None
        md_lines += [
            "",
            "## Ponto de Degradação",
            "",
            f"- **Detectado em**: {deg['cameras']} câmeras",
            f"- **Alerts/min neste tier**: {deg['alerts_per_min']:.1f}",
            f"- **Alerts/min tier anterior**: {prev['alerts_per_min']:.1f if prev else 'N/A'}",
            f"- **Queda**: {((1 - deg['alerts_per_min'] / (prev['alerts_per_min'] or 1)) * 100):.0f}%",
            "",
            "> Alimenta task-053 (PgBouncer + pooling): investigar conexões PG esgotadas neste nível.",
        ]
    else:
        peak_cam = max(results, key=lambda r: r["alerts_per_min"])["cameras"] if results else "N/A"
        md_lines += [
            "",
            "## Ponto de Degradação",
            "",
            f"Nenhuma degradação >50% detectada até {peak_cam} câmeras.",
            "Sistema sustentou carga máxima testada.",
        ]

    md_lines += [
        "",
        "## Observações",
        "",
        "- `stream_ratio` = streams ativos / câmeras configuradas (< 1.0 indica falhas de conexão RTSP)",
        "- Alertas/min = alertas gerados durante período de observação (pós-warmup)",
        "- Arquivo de dados brutos: `raw.json`",
    ]

    report_path = EVIDENCE_DIR / "REPORT.md"
    report_path.write_text("\n".join(md_lines) + "\n")
    logger.info("Relatório salvo em %s", report_path)
    logger.info("Raw JSON salvo em %s", raw_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark de escala staging")
    parser.add_argument("--tiers",         default="4,8,16,28",
                        help="Tiers de câmeras separados por vírgula")
    parser.add_argument("--warmup",        type=int, default=30,
                        help="Segundos de warmup por tier")
    parser.add_argument("--samples",       type=int, default=5,
                        help="Número de amostras por tier")
    parser.add_argument("--poll-interval", type=int, default=10,
                        help="Intervalo entre amostras (segundos)")
    parser.add_argument("--model-id",      default=None)
    parser.add_argument("--staging-url",   default=STAGING_URL)
    parser.add_argument("--degradation-threshold", type=float, default=0.5,
                        help="Fração de queda em alerts/min para marcar degradação (default 0.5 = 50%%)")
    args = parser.parse_args()

    if not ADMIN_PASSWORD:
        logger.error("ADMIN_PASSWORD não definido")
        sys.exit(1)

    tiers = [int(t.strip()) for t in args.tiers.split(",")]
    client = StagingClient(args.staging_url)
    client.login(ADMIN_EMAIL, ADMIN_PASSWORD)

    results: list[dict] = []
    for cameras in tiers:
        try:
            result = measure_tier(
                client, cameras,
                warmup=args.warmup,
                n_samples=args.samples,
                poll_interval=args.poll_interval,
                model_id=args.model_id,
            )
            results.append(result)
            logger.info(
                "Tier %d: alerts/min=%.1f streams=%d/%d",
                cameras, result["alerts_per_min"],
                result["active_streams"], cameras,
            )
        except Exception as exc:
            logger.error("Tier %d falhou: %s", cameras, exc, exc_info=True)
            results.append({
                "cameras": cameras, "error": str(exc),
                "alerts_per_min": 0.0, "active_streams": 0,
                "stream_ratio": 0.0, "duration_sec": 0, "samples": [],
            })
            # Try to stop any running harness before next tier
            try:
                client.stop_harness()
            except Exception:
                pass

    degradation_idx = find_degradation(results, args.degradation_threshold)
    write_report(results, degradation_idx, args)

    if degradation_idx is not None:
        logger.warning(
            "Ponto de degradação: %d câmeras (alerts/min=%.1f)",
            results[degradation_idx]["cameras"],
            results[degradation_idx]["alerts_per_min"],
        )
    else:
        logger.info("Sem degradação detectada até %d câmeras.", tiers[-1])


if __name__ == "__main__":
    main()
