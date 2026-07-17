#!/usr/bin/env python3
"""
scripts/seed_dashboard_observability.py — seed end-to-end do Dashboard Integrado.

task-112 / ADR-0053. Lê os DADOS REAIS já versionados no repo e os injeta via
os endpoints de ingest tenant-scoped (o tenant sai do JWT, C-01 — o script
nunca inventa tenant_id):

  docs/edge/train_metrics/*.jsonl
      → POST /api/v1/dashboard/training-metrics  (curvas por época por modelo)
  docs/edge/evidence/mm-2026-07-17/telemetry_mm.jsonl
      → POST /api/v1/dashboard/edge-telemetry    (telemetria do Jetson por site)

Usa só a stdlib (urllib) — nenhuma dependência nova.

Autenticação (uma das duas):
  --token <JWT>                    token já emitido (claims tenant_id/schema)
  --email <e> --password <p>       faz login em /api/auth/login e usa o token

Uso:
  # contra API local (dev)
  python3 scripts/seed_dashboard_observability.py \
      --api-url http://localhost:5001 \
      --email dev@rvb.local --password ****** \
      --site-id 00000000-0000-0000-0000-000000000000

  # contra staging (produção Railway), token já em mãos
  python3 scripts/seed_dashboard_observability.py \
      --api-url https://api-v3-production-2b22.up.railway.app \
      --token "$TOKEN"

Sem DB/API acessível o script não faz nada destrutivo — só reporta o erro de
conexão. Os endpoints de READ servem exatamente o que este seed grava.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Raiz do repo: services/api/scripts/ → sobe 3 níveis
REPO_ROOT = Path(__file__).resolve().parents[3]
TRAIN_METRICS_DIR = REPO_ROOT / "docs" / "edge" / "train_metrics"
TELEMETRY_FILE = (
    REPO_ROOT / "docs" / "edge" / "evidence" / "mm-2026-07-17" / "telemetry_mm.jsonl"
)

# Chunk de telemetria por request (respeita _MAX_TELEMETRY_SAMPLES da rota).
TELEMETRY_CHUNK = 500


def _post(api_url: str, path: str, token: str, body: dict[str, Any]) -> dict[str, Any]:
    """POST JSON autenticado. Levanta em erro HTTP com corpo legível."""
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{api_url.rstrip('/')}{path}",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise SystemExit(f"HTTP {exc.code} em {path}: {detail}") from exc


def _login(api_url: str, email: str, password: str) -> str:
    """Faz login e retorna o token JWT (com claims de tenant)."""
    body = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        f"{api_url.rstrip('/')}/api/auth/login",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise SystemExit(f"Login falhou (HTTP {exc.code}): {detail}") from exc
    # Envelope {success, data:{token}} ou {token} — tolera ambos.
    token = payload.get("token") or payload.get("data", {}).get("token")
    if not token:
        raise SystemExit(f"Login não retornou token: {payload}")
    return token


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def seed_training_metrics(api_url: str, token: str) -> None:
    """Agrupa cada *.jsonl por modelo e faz upsert das épocas."""
    files = sorted(TRAIN_METRICS_DIR.glob("*.jsonl"))
    if not files:
        print(f"[seed] nenhum *.jsonl em {TRAIN_METRICS_DIR}", file=sys.stderr)
        return
    for f in files:
        rows = _load_jsonl(f)
        if not rows:
            continue
        model_name = rows[0].get("model") or f.stem
        framework = rows[0].get("framework")
        epochs = []
        for r in rows:
            metrics = {k: v for k, v in r.items() if k not in ("model", "framework", "epoch")}
            epochs.append({"epoch": r["epoch"], "metrics": metrics})
        resp = _post(
            api_url,
            "/api/v1/dashboard/training-metrics",
            token,
            {"model_name": model_name, "framework": framework, "epochs": epochs},
        )
        upserted = resp.get("data", {}).get("upserted", "?")
        print(f"[seed] training {model_name}: {upserted} épocas upsertadas")


def seed_edge_telemetry(api_url: str, token: str, site_id: str | None) -> None:
    """Envia as amostras de telemetria em chunks (sampled_at=ts, payload=linha)."""
    if not TELEMETRY_FILE.exists():
        print(f"[seed] telemetria ausente: {TELEMETRY_FILE}", file=sys.stderr)
        return
    rows = _load_jsonl(TELEMETRY_FILE)
    total = 0
    for i in range(0, len(rows), TELEMETRY_CHUNK):
        chunk = rows[i : i + TELEMETRY_CHUNK]
        samples = [
            {"sampled_at": r["ts"], "label": r.get("label"), "payload": r}
            for r in chunk
        ]
        resp = _post(
            api_url,
            "/api/v1/dashboard/edge-telemetry",
            token,
            {"site_id": site_id, "samples": samples},
        )
        total += resp.get("data", {}).get("inserted", 0)
    print(f"[seed] telemetria: {total} amostras inseridas (site_id={site_id})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url",
        default=os.environ.get("API_URL", "http://localhost:5001"),
        help="Base URL da API (default: http://localhost:5001)",
    )
    parser.add_argument("--token", help="JWT já emitido (claims de tenant)")
    parser.add_argument("--email", help="E-mail para login (alternativa a --token)")
    parser.add_argument("--password", help="Senha para login")
    parser.add_argument("--site-id", help="site_id (UUID) da telemetria — opcional")
    parser.add_argument(
        "--only",
        choices=["training", "telemetry"],
        help="Semeia só uma das séries (default: ambas)",
    )
    args = parser.parse_args()

    token = args.token
    if not token:
        if not (args.email and args.password):
            raise SystemExit(
                "Forneça --token OU --email/--password para autenticar."
            )
        token = _login(args.api_url, args.email, args.password)

    if args.only in (None, "training"):
        seed_training_metrics(args.api_url, token)
    if args.only in (None, "telemetry"):
        seed_edge_telemetry(args.api_url, token, args.site_id)

    print("[seed] concluído.")


if __name__ == "__main__":
    main()
