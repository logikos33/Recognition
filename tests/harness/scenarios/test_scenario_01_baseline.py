"""
Harness D2 — Cenário 1: Baseline end-to-end (task-027).

EVAL: Evento sintético (heartbeat) parte do edge simulado, chega ao cloud e
      aparece via /api/v1/edge/sites/health em < 5 segundos.

Passos:
  1. Criar tenant + admin + site + enrollment token (psycopg2 direto)
  2. Enrollar dispositivo via POST /api/v1/edge/enroll
  3. Enviar heartbeat via POST /api/v1/edge/heartbeat (JWT RS256)
  4. Logar como admin + consultar GET /api/v1/edge/sites/health
     → site deve aparecer com derived_status != 'offline' em < 5 s

GAP reportado (liga com task-028): edge-sync-agent completo não necessário —
heartbeat é simulado diretamente via HTTP+JWT. RTSP não é validado na ingestão.
"""
import time

import requests

from helpers.device_sim import DeviceSim
from helpers.tenant_setup import (
    create_admin_user,
    create_edge_site,
    create_enrollment_token,
    create_tenant,
)

_MAX_EVENT_SECONDS = 5.0


def test_scenario_01_event_reaches_cloud(api_url, db_conn):
    """Evento ponta-a-ponta: heartbeat sintético aparece via API em < 5 s."""
    # ── Setup ──────────────────────────────────────────────────────────────
    tenant = create_tenant(db_conn, "Scenario 01 Baseline")
    user = create_admin_user(
        db_conn,
        tenant["id"],
        f"admin-s01-{tenant['id'][:8]}@harness.test",
        "harness-pass-s01",
    )
    site = create_edge_site(db_conn, tenant["id"], "Site Baseline S01")
    enrollment_token = create_enrollment_token(db_conn, str(site["id"]), tenant["id"])

    sim = DeviceSim(f"dev-s01-{tenant['id'][:8]}")

    # ── Enrollment ─────────────────────────────────────────────────────────
    enroll_resp = requests.post(
        f"{api_url}/api/v1/edge/enroll",
        json={
            "enrollment_token": enrollment_token,
            "device_id": sim.device_id,
            "device_name": "Synthetic Device — Scenario 01",
            "public_key_pem": sim.public_key_pem,
        },
        timeout=10,
    )
    assert enroll_resp.status_code == 201, (
        f"Enrollment falhou: {enroll_resp.status_code}\n{enroll_resp.text}"
    )
    enroll_data = enroll_resp.json()["data"]
    sim.set_enrollment(enroll_data["tenant_id"], enroll_data["site_id"])

    # ── Enviar heartbeat (evento sintético) ────────────────────────────────
    device_token = sim.build_token()
    hb_resp = requests.post(
        f"{api_url}/api/v1/edge/heartbeat",
        headers={"Authorization": f"Bearer {device_token}"},
        json=sim.heartbeat_payload(),
        timeout=10,
    )
    assert hb_resp.status_code == 201, (
        f"Heartbeat falhou: {hb_resp.status_code}\n{hb_resp.text}"
    )
    sent_at = time.monotonic()

    # ── Login como admin para consultar /sites/health ──────────────────────
    login_resp = requests.post(
        f"{api_url}/api/auth/login",
        json={"email": user["email"], "password": "harness-pass-s01"},
        timeout=10,
    )
    assert login_resp.status_code == 200, (
        f"Login falhou: {login_resp.status_code}\n{login_resp.text}"
    )
    resp_body = login_resp.json()
    data = resp_body.get("data", resp_body)
    jwt_token = data.get("access_token") or data.get("token")
    assert jwt_token, f"access_token ausente na resposta de login: {resp_body}"

    # ── Verificar evento no cloud ──────────────────────────────────────────
    health_resp = requests.get(
        f"{api_url}/api/v1/edge/sites/health",
        headers={"Authorization": f"Bearer {jwt_token}"},
        timeout=10,
    )
    assert health_resp.status_code == 200, (
        f"/sites/health falhou: {health_resp.status_code}\n{health_resp.text}"
    )

    elapsed = time.monotonic() - sent_at
    assert elapsed < _MAX_EVENT_SECONDS, (
        f"Evento demorou {elapsed:.2f}s > {_MAX_EVENT_SECONDS}s para aparecer via API"
    )

    sites = health_resp.json()["data"]["sites"]
    target = next((s for s in sites if s["site_id"] == str(site["id"])), None)
    assert target is not None, (
        f"Site {site['id']} não encontrado em /sites/health. "
        f"Sites retornados: {[s['site_id'] for s in sites]}"
    )
    assert target["derived_status"] != "offline", (
        f"Site aparece como 'offline' após heartbeat (derived_status={target['derived_status']})"
    )
