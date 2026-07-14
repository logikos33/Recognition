"""
Prova E2E em staging — 4 câmeras sintéticas via console admin.

Fluxo:
  1. Login como admin de teste → obter JWT
  2. POST /api/v1/admin/test-console/harness/start (N câmeras)
  3. Poll /status até alerts_generated >= MIN_ALERTS ou timeout
  4. GET /evidence → coletar chaves R2
  5. POST /harness/stop
  6. Escrever relatório em docs/evidence/e2e-Ncam/report.json

Uso:
  export STAGING_URL=https://api-v3-production-2b22.up.railway.app
  export ADMIN_EMAIL=test-admin@epi-ci.internal
  export ADMIN_PASSWORD=...
  python3 scripts/staging_e2e_proof.py [--cameras 4] [--min-alerts 2] [--timeout 300]

Pré-requisitos:
  - PRs A1, A2, A3, C1 mergeados e deployados em staging
  - Tenant de teste semeado (scripts/seed_test_tenant.py)
  - Worker com DETECTOR_BACKEND=yolox_onnx e modelo registrado
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

STAGING_URL = os.environ.get("STAGING_URL", "https://api-v3-production-2b22.up.railway.app")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "test-admin@epi-ci.internal")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
EVIDENCE_BASE = Path(__file__).resolve().parents[1] / "docs" / "evidence"


class StagingClient:
    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")
        self.token: str | None = None

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers: dict = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)  # noqa: S310
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                raw = resp.read().decode()
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode() if exc.fp else ""
            raise RuntimeError(f"HTTP {exc.code} {method} {url}: {body_text[:300]}") from exc

    def login(self, email: str, password: str) -> None:
        resp = self._request("POST", "/api/auth/login", {"email": email, "password": password})
        token = resp.get("token") or resp.get("data", {}).get("token")
        if not token:
            raise RuntimeError(f"Login falhou: {resp}")
        self.token = token
        logger.info("Login bem-sucedido como %s", email)

    def start_harness(self, cameras: int, model_id: str | None = None) -> dict:
        body: dict = {"cameras": cameras}
        if model_id:
            body["model_id"] = model_id
        resp = self._request("POST", "/api/v1/admin/test-console/harness/start", body)
        return resp.get("data", resp)

    def get_status(self) -> dict:
        resp = self._request("GET", "/api/v1/admin/test-console/harness/status")
        return resp.get("data", resp)

    def get_evidence(self, limit: int = 20) -> list[dict]:
        resp = self._request("GET", f"/api/v1/admin/test-console/evidence?limit={limit}")
        return resp.get("data", {}).get("evidence", [])

    def stop_harness(self) -> dict:
        resp = self._request("POST", "/api/v1/admin/test-console/harness/stop", {})
        return resp.get("data", resp)

    def health(self) -> dict:
        try:
            return self._request("GET", "/health")
        except Exception as exc:
            return {"error": str(exc)}


def wait_for_alerts(client: StagingClient, min_alerts: int, timeout: int, poll: int = 15) -> dict:
    """Aguarda até min_alerts serem gerados ou timeout atingido."""
    deadline = time.time() + timeout
    last_status: dict = {}

    while time.time() < deadline:
        status = client.get_status()
        last_status = status
        generated = status.get("alerts_generated", 0)
        active = status.get("active_streams", 0)
        logger.info(
            "status: active=%s streams=%d alerts=%d (aguardando >=%d)...",
            status.get("active"), active, generated, min_alerts,
        )
        if generated >= min_alerts:
            logger.info("Alertas suficientes (%d >= %d). Continuando.", generated, min_alerts)
            return last_status
        time.sleep(poll)

    logger.warning("Timeout atingido (%ds) — alerts=%d", timeout, last_status.get("alerts_generated", 0))
    return last_status


def write_report(evidence_dir: Path, data: dict) -> Path:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    report_path = evidence_dir / "report.json"
    report_path.write_text(json.dumps(data, indent=2))
    logger.info("Relatório salvo em %s", report_path)
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Prova E2E staging")
    parser.add_argument("--cameras", type=int, default=4)
    parser.add_argument("--min-alerts", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--staging-url", default=STAGING_URL)
    args = parser.parse_args()

    if not ADMIN_PASSWORD:
        logger.error("ADMIN_PASSWORD não definido")
        sys.exit(1)

    client = StagingClient(args.staging_url)
    started_at = datetime.now(timezone.utc).isoformat()
    evidence_dir = EVIDENCE_BASE / f"e2e-{args.cameras}cam"

    # 1. Health check
    health = client.health()
    logger.info("Health check: %s", health)

    # 2. Login
    client.login(ADMIN_EMAIL, ADMIN_PASSWORD)

    # 3. Iniciar harness
    logger.info("Iniciando harness com %d câmeras...", args.cameras)
    start_result = client.start_harness(args.cameras, args.model_id)
    logger.info("Harness iniciado: %s", start_result)

    # 4. Aguardar alertas
    final_status = wait_for_alerts(client, args.min_alerts, args.timeout)

    # 5. Coletar evidências
    evidence = client.get_evidence(limit=50)
    logger.info("Evidências coletadas: %d items", len(evidence))

    # 6. Parar harness
    stop_result = client.stop_harness()
    logger.info("Harness parado: %s", stop_result)

    finished_at = datetime.now(timezone.utc).isoformat()

    # 7. Relatório
    report = {
        "proof": f"e2e-{args.cameras}cam",
        "staging_url": args.staging_url,
        "started_at": started_at,
        "finished_at": finished_at,
        "cameras": args.cameras,
        "min_alerts_required": args.min_alerts,
        "alerts_generated": final_status.get("alerts_generated", 0),
        "active_streams_peak": final_status.get("active_streams", 0),
        "model_id": start_result.get("model_id"),
        "violation_classes": start_result.get("violation_classes"),
        "evidence": evidence,
        "harness_start": start_result,
        "harness_stop": stop_result,
        "final_status": final_status,
        "health": health,
        "pass": final_status.get("alerts_generated", 0) >= args.min_alerts,
    }

    report_path = write_report(evidence_dir, report)

    # Resultado
    if report["pass"]:
        logger.info("PASSED — prova E2E %d câmeras bem-sucedida", args.cameras)
        logger.info("Relatório: %s", report_path)
    else:
        logger.error(
            "FAILED — alertas gerados (%d) < mínimo (%d)",
            report["alerts_generated"], args.min_alerts,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
