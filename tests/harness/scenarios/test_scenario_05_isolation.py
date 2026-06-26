"""
Harness D2 — Cenário 5: Isolamento multi-tenant (task-027).

EVAL:
  5a) Tenant B não vê sites/heartbeats do Tenant A em /sites/health (C-01).
  5b) Device token do Tenant A com claims de Tenant B → 403 (defense-in-depth C-01/C-05).

Valida isolamento em runtime, não apenas no banco.
"""
import requests

from helpers.device_sim import DeviceSim
from helpers.tenant_setup import (
    create_admin_user,
    create_edge_site,
    create_enrollment_token,
    create_tenant,
)


# ── Helpers locais ─────────────────────────────────────────────────────────────


def _login(api_url: str, email: str, password: str) -> str:
    """Retorna JWT access_token após login bem-sucedido."""
    resp = requests.post(
        f"{api_url}/api/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    assert resp.status_code == 200, f"Login falhou: {resp.status_code}\n{resp.text}"
    body = resp.json()
    data = body.get("data", body)
    token = data.get("access_token") or data.get("token")
    assert token, f"access_token ausente: {body}"
    return token


def _enroll_device(api_url: str, db_conn, tenant: dict, site: dict) -> DeviceSim:
    """Enrolla dispositivo e retorna DeviceSim configurado."""
    device_id = f"dev-s05-{tenant['id'][:8]}"
    enrollment_token = create_enrollment_token(db_conn, str(site["id"]), tenant["id"])
    sim = DeviceSim(device_id)

    resp = requests.post(
        f"{api_url}/api/v1/edge/enroll",
        json={
            "enrollment_token": enrollment_token,
            "device_id": device_id,
            "device_name": f"Synthetic Device Tenant {tenant['id'][:8]}",
            "public_key_pem": sim.public_key_pem,
        },
        timeout=10,
    )
    assert resp.status_code == 201, f"Enrollment falhou: {resp.status_code}\n{resp.text}"
    data = resp.json()["data"]
    sim.set_enrollment(data["tenant_id"], data["site_id"])
    return sim


def _send_heartbeat(api_url: str, sim: DeviceSim) -> None:
    """Envia heartbeat e garante 201."""
    token = sim.build_token()
    resp = requests.post(
        f"{api_url}/api/v1/edge/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
        json=sim.heartbeat_payload(),
        timeout=10,
    )
    assert resp.status_code == 201, f"Heartbeat falhou: {resp.status_code}\n{resp.text}"


# ── Cenário 5a ─────────────────────────────────────────────────────────────────


def test_scenario_05a_tenant_data_isolation(api_url, db_conn):
    """Tenant B não enxerga sites nem heartbeats do Tenant A (C-01)."""
    tenant_a = create_tenant(db_conn, "Scenario 05 Tenant A")
    tenant_b = create_tenant(db_conn, "Scenario 05 Tenant B")

    site_a = create_edge_site(db_conn, tenant_a["id"], "Site A S05")
    create_edge_site(db_conn, tenant_b["id"], "Site B S05")

    user_b = create_admin_user(
        db_conn,
        tenant_b["id"],
        f"admin-b-s05-{tenant_b['id'][:8]}@harness.test",
        "harness-pass-s05b",
    )

    # Enrollar e enviar heartbeat apenas do Tenant A
    sim_a = _enroll_device(api_url, db_conn, tenant_a, site_a)
    _send_heartbeat(api_url, sim_a)

    # Tenant B consulta /sites/health — não deve ver nada do Tenant A
    token_b = _login(api_url, user_b["email"], "harness-pass-s05b")
    health_resp = requests.get(
        f"{api_url}/api/v1/edge/sites/health",
        headers={"Authorization": f"Bearer {token_b}"},
        timeout=10,
    )
    assert health_resp.status_code == 200, (
        f"/sites/health (Tenant B) falhou: {health_resp.status_code}\n{health_resp.text}"
    )

    sites_b = health_resp.json()["data"]["sites"]
    leaked = [s for s in sites_b if s["site_id"] == str(site_a["id"])]
    assert not leaked, (
        f"VIOLAÇÃO C-01: Site do Tenant A visível para Tenant B! "
        f"site_id={site_a['id']} vazou: {leaked}"
    )


# ── Cenário 5b ─────────────────────────────────────────────────────────────────


def test_scenario_05b_cross_tenant_device_token_403(api_url, db_conn):
    """Device A com claims de Tenant B → 403 (defense-in-depth cross-tenant C-01/C-05).

    Mecanismo: o servidor encontra Device A (enrollment = Tenant A) mas as claims
    do JWT dizem Tenant B → mismatch → 403. Valida a linha 157-165 de edge/routes.py.
    """
    tenant_a = create_tenant(db_conn, "Cross Tenant A S05b")
    tenant_b = create_tenant(db_conn, "Cross Tenant B S05b")

    site_a = create_edge_site(db_conn, tenant_a["id"], "Site Cross A")
    site_b = create_edge_site(db_conn, tenant_b["id"], "Site Cross B")

    # Enrollar Device A no Tenant A
    sim_a = _enroll_device(api_url, db_conn, tenant_a, site_a)

    # Forjar token: device_id de A, assinado com chave de A, mas claims = Tenant B / Site B
    forged_token = sim_a.build_token(
        tenant_id=str(tenant_b["id"]),
        site_id=str(site_b["id"]),
    )

    # Enviar heartbeat com token adulterado → 403 esperado
    hb_resp = requests.post(
        f"{api_url}/api/v1/edge/heartbeat",
        headers={"Authorization": f"Bearer {forged_token}"},
        json=sim_a.heartbeat_payload(),
        timeout=10,
    )
    assert hb_resp.status_code == 403, (
        f"VIOLAÇÃO C-01: esperado 403 (token adulterado cross-tenant), "
        f"obtido {hb_resp.status_code}.\nResponse: {hb_resp.text}"
    )
