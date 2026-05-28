"""
Worker On-Premise — Heartbeat service.

Coleta métricas GPU via nvidia-smi e envia para a API a cada 30s.
Autenticado por X-Worker-Secret header (sem JWT).

Se a resposta contiver {"command": "restart"} → sys.exit(1) e o
Docker restart:always cuida do reinício automático do container.

Env vars requeridas:
  API_URL         ex: https://api-v3-production-2b22.up.railway.app
  WORKER_SECRET   shared secret configurado no Railway
  TENANT_SCHEMA   ex: rvb
  SOFTWARE_VERSION ex: 1.0.0 (opcional, default: unknown)
"""
import json
import logging
import os
import subprocess
import sys
import time

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [heartbeat] %(message)s")
logger = logging.getLogger(__name__)

API_URL       = os.environ["API_URL"].rstrip("/")
WORKER_SECRET = os.environ["WORKER_SECRET"]
TENANT_SCHEMA = os.environ["TENANT_SCHEMA"]
SOFTWARE_VER  = os.environ.get("SOFTWARE_VERSION", "unknown")
HOSTNAME      = os.environ.get("HOSTNAME", "unknown")
INTERVAL      = int(os.environ.get("HEARTBEAT_INTERVAL", "30"))

ENDPOINT = f"{API_URL}/api/v1/admin/workers/heartbeat"


def _collect_gpu_metrics() -> dict:
    """Coleta métricas via nvidia-smi. Retorna zeros se GPU indisponível."""
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,name",
                "--format=csv,noheader,nounits",
            ],
            timeout=5,
            text=True,
        ).strip()
        parts = [p.strip() for p in out.split(",")]
        gpu_pct      = float(parts[0])
        vram_used_mb = float(parts[1])
        vram_total_mb = float(parts[2])
        gpu_model    = parts[3]
        return {
            "gpu_pct":       gpu_pct,
            "vram_used_gb":  round(vram_used_mb / 1024, 2),
            "gpu_vram_gb":   round(vram_total_mb / 1024, 2),
            "gpu_model":     gpu_model,
        }
    except Exception as exc:
        logger.warning("nvidia-smi failed: %s", exc)
        return {"gpu_pct": 0.0, "vram_used_gb": 0.0, "gpu_model": "unknown"}


def send_heartbeat() -> str | None:
    """Envia heartbeat para a API. Retorna command string ou None."""
    metrics = _collect_gpu_metrics()
    payload = {
        "tenant_schema":    TENANT_SCHEMA,
        "hostname":         HOSTNAME,
        "software_version": SOFTWARE_VER,
        "fps_avg":          0.0,
        "cameras_active":   0,
        **metrics,
    }

    try:
        resp = requests.post(
            ENDPOINT,
            json=payload,
            headers={"X-Worker-Secret": WORKER_SECRET, "Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            command = data.get("data", {}).get("command")
            logger.info("heartbeat ok | gpu=%.1f%% vram=%.1fGB command=%s",
                        metrics.get("gpu_pct", 0), metrics.get("vram_used_gb", 0), command)
            return command
        logger.warning("heartbeat rejected: %d %s", resp.status_code, resp.text[:200])
    except requests.RequestException as exc:
        logger.warning("heartbeat request failed: %s", exc)

    return None


def main() -> None:
    logger.info("starting heartbeat | schema=%s api=%s interval=%ds", TENANT_SCHEMA, API_URL, INTERVAL)
    while True:
        command = send_heartbeat()
        if command == "restart":
            logger.info("received restart command — exiting (Docker will restart container)")
            sys.exit(1)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
