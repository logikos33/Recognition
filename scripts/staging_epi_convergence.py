"""
Convergência E2E — detectar EPI real com modelo treinado na Vast.ai.

Pré-requisitos (PRs B2+B3 mergeados):
  - Modelo YOLOX/RF-DETR treinado no PPE dataset e registrado no registry
    (source=vast_ai, is_default=True no tenant de teste)
  - PRs A1-A3, C1, C2 mergeados e em staging

Fluxo:
  1. GET /models → selecionar modelo EPI (vast_ai ou fallback: primeiro modelo)
  2. Tier 4 câmeras → iniciar harness com modelo EPI → aguardar alertas → parar
  3. Tier 28 câmeras → idem
  4. Escrever docs/evidence/e2e-epi/report.json

Uso:
  export STAGING_URL=https://api-v3-production-2b22.up.railway.app
  export ADMIN_EMAIL=test-admin@epi-ci.internal
  export ADMIN_PASSWORD=...
  python3 scripts/staging_epi_convergence.py [--model-id <uuid>] [--timeout 300]
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

STAGING_URL    = os.environ.get("STAGING_URL",    "https://api-v3-production-2b22.up.railway.app")
ADMIN_EMAIL    = os.environ.get("ADMIN_EMAIL",    "test-admin@epi-ci.internal")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
EVIDENCE_DIR   = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "e2e-epi"

TIERS = [4, 28]


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

    def list_models(self) -> list[dict]:
        return self._req("GET", "/api/v1/admin/test-console/models").get("data", {}).get("models", [])

    def start_harness(self, cameras: int, model_id: str) -> dict:
        return self._req(
            "POST", "/api/v1/admin/test-console/harness/start",
            {"cameras": cameras, "model_id": model_id},
        ).get("data", {})

    def status(self) -> dict:
        return self._req("GET", "/api/v1/admin/test-console/status").get("data", {})

    def evidence(self, limit: int = 50) -> list[dict]:
        return self._req("GET", f"/api/v1/admin/test-console/evidence?limit={limit}").get(
            "data", {}
        ).get("evidence", [])

    def stop_harness(self) -> dict:
        return self._req("POST", "/api/v1/admin/test-console/harness/stop", {}).get("data", {})


def pick_epi_model(models: list[dict], preferred_id: str | None) -> dict | None:
    """Seleciona: preferred_id → vast_ai is_default → primeiro vast_ai → primeiro modelo."""
    if preferred_id:
        for m in models:
            if str(m.get("id")) == preferred_id:
                return m
        logger.warning("model_id=%s não encontrado nos modelos disponíveis", preferred_id)

    # Prefer vast_ai default
    for m in models:
        meta = m.get("metrics", {})
        if m.get("is_default") and meta.get("source") == "vast_ai":
            return m

    # Any vast_ai
    for m in models:
        if m.get("metrics", {}).get("source") == "vast_ai":
            return m

    # Fallback: first available
    return models[0] if models else None


def run_tier(
    client: StagingClient, cameras: int, model_id: str, timeout: int, poll: int = 15,
) -> dict:
    logger.info("── Tier %d câmeras (model_id=%s) ──", cameras, model_id)
    start = client.start_harness(cameras, model_id)
    logger.info("Harness: %s", start)

    deadline    = time.time() + timeout
    final_status: dict = {}
    while time.time() < deadline:
        s = client.status()
        final_status = s
        alerts = s.get("alerts_generated", 0)
        logger.info(
            "  active=%s streams=%d alerts=%d",
            s.get("active"), s.get("active_streams", 0), alerts,
        )
        if alerts >= 1:
            logger.info("  Primeira detecção EPI confirmada (%d alertas).", alerts)
            break
        time.sleep(poll)
    else:
        logger.warning("  Timeout — nenhum alerta EPI em %ds.", timeout)

    ev   = client.evidence(limit=20)
    stop = client.stop_harness()

    return {
        "cameras":         cameras,
        "alerts_generated": final_status.get("alerts_generated", 0),
        "active_streams":  final_status.get("active_streams", 0),
        "evidence":        ev,
        "harness_start":   start,
        "harness_stop":    stop,
        "final_status":    final_status,
    }


def write_report(results: list[dict], model: dict, args: argparse.Namespace) -> dict:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "proof":          "e2e-epi",
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "staging_url":    args.staging_url,
        "model": {
            "id":      model.get("id"),
            "name":    model.get("name"),
            "source":  model.get("metrics", {}).get("source"),
            "map50":   model.get("metrics", {}).get("mAP50"),
            "license": model.get("metrics", {}).get("license"),
        },
        "tiers":          results,
        "pass": all(r.get("alerts_generated", 0) >= 1 for r in results),
    }
    path = EVIDENCE_DIR / "report.json"
    path.write_text(json.dumps(report, indent=2))
    logger.info("Relatório: %s", path)
    return report  # type: ignore[return-value]


def main() -> None:
    parser = argparse.ArgumentParser(description="Convergência E2E com modelo EPI treinado")
    parser.add_argument("--model-id",   default=None,
                        help="UUID do modelo no registry (auto-seleciona vast_ai se omitido)")
    parser.add_argument("--timeout",    type=int, default=300,
                        help="Timeout por tier para primeira detecção (segundos)")
    parser.add_argument("--tiers",      default="4,28",
                        help="Tiers de câmeras a testar")
    parser.add_argument("--staging-url", default=STAGING_URL)
    args = parser.parse_args()

    if not ADMIN_PASSWORD:
        logger.error("ADMIN_PASSWORD não definido")
        sys.exit(1)

    tiers  = [int(t.strip()) for t in args.tiers.split(",")]
    client = StagingClient(args.staging_url)
    client.login(ADMIN_EMAIL, ADMIN_PASSWORD)

    # Selecionar modelo EPI
    models = client.list_models()
    logger.info("Modelos disponíveis: %d", len(models))
    for m in models:
        logger.info("  %s | %s | source=%s map50=%s",
                    m.get("id"), m.get("name"),
                    m.get("metrics", {}).get("source", "?"),
                    m.get("metrics", {}).get("mAP50", "?"))

    model = pick_epi_model(models, args.model_id)
    if not model:
        logger.error("Nenhum modelo encontrado. Execute B3 para registrar o modelo EPI treinado.")
        sys.exit(1)

    logger.info(
        "Modelo selecionado: %s (%s) — source=%s mAP50=%s",
        model.get("name"), model.get("id"),
        model.get("metrics", {}).get("source"),
        model.get("metrics", {}).get("mAP50"),
    )

    # Executar tiers
    results = []
    for cameras in tiers:
        try:
            r = run_tier(client, cameras, str(model["id"]), args.timeout)
            results.append(r)
        except Exception as exc:
            logger.error("Tier %d falhou: %s", cameras, exc, exc_info=True)
            results.append({"cameras": cameras, "error": str(exc), "alerts_generated": 0})
            try:
                client.stop_harness()
            except Exception:
                pass

    report = write_report(results, model, args)

    if report["pass"]:
        logger.info("PASSED — detector EPI detectou em todos os tiers: %s", tiers)
    else:
        failed = [r["cameras"] for r in results if r.get("alerts_generated", 0) < 1]
        logger.error("FAILED — sem detecção EPI nos tiers: %s", failed)
        sys.exit(1)


if __name__ == "__main__":
    main()
