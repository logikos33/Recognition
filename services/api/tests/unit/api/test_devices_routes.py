"""Testes — POST /api/devices/claim-codes e POST /api/devices/claim.

Repositório mockado (FakeClaimRepo em memória) — valida o contrato dos
endpoints: geração (admin only), troca, expiração e single-use.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from flask_jwt_extended import create_access_token, decode_token

import app.api.v1.devices.routes as devices_routes
from app.core.device_auth import hash_claim_code

TENANT = "11111111-1111-1111-1111-111111111111"


class FakeClaimRepo:
    """Simula public.device_claim_codes em memória (hash → row)."""

    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def create(self, tenant_id, code_hash, created_by, ttl_minutes):
        row = {
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "code_hash": code_hash,
            "created_by": created_by,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
            "used_at": None,
        }
        self.rows[code_hash] = row
        return row

    def redeem(self, code_hash, device_name):
        row = self.rows.get(code_hash)
        if not row:
            return None
        if row["used_at"] is not None:
            return None
        if row["expires_at"] <= datetime.now(timezone.utc):
            return None
        row["used_at"] = datetime.now(timezone.utc)
        row["used_by_device"] = device_name
        return {"id": row["id"], "tenant_id": row["tenant_id"]}


@pytest.fixture
def claim_repo(monkeypatch):
    repo = FakeClaimRepo()
    monkeypatch.setattr(devices_routes, "_get_claim_repo", lambda: repo)
    return repo


def _auth_header(app, role="admin", tenant_id=TENANT):
    with app.app_context():
        token = create_access_token(
            identity=str(uuid.uuid4()),
            additional_claims={
                "tenant_id": tenant_id,
                "tenant_schema": "tenant_test",
                "role": role,
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


class TestCreateClaimCode:
    def test_admin_generates_code(self, app, client, claim_repo):
        resp = client.post("/api/devices/claim-codes", headers=_auth_header(app))
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert len(data["claim_code"]) == 8
        assert data["expires_in_minutes"] == 15
        # Banco guarda apenas o hash — nunca o plaintext
        stored_hashes = set(claim_repo.rows.keys())
        assert hash_claim_code(data["claim_code"]) in stored_hashes
        assert data["claim_code"] not in stored_hashes

    def test_non_admin_forbidden(self, app, client, claim_repo):
        resp = client.post(
            "/api/devices/claim-codes", headers=_auth_header(app, role="operator")
        )
        assert resp.status_code == 403
        assert claim_repo.rows == {}

    def test_requires_jwt(self, client, claim_repo):
        resp = client.post("/api/devices/claim-codes")
        assert resp.status_code == 401


class TestClaimDevice:
    def _generate(self, app, client):
        resp = client.post("/api/devices/claim-codes", headers=_auth_header(app))
        return resp.get_json()["data"]["claim_code"]

    def test_valid_code_returns_enrollment_token(self, app, client, claim_repo):
        code = self._generate(app, client)
        resp = client.post(
            "/api/devices/claim",
            json={"code": code, "device_name": "edge-box-1"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["tenant_id"] == TENANT
        with app.app_context():
            payload = decode_token(data["enrollment_token"])
        assert payload["token_type"] == "device_enrollment"
        assert payload["tenant_id"] == TENANT

    def test_code_is_single_use(self, app, client, claim_repo):
        code = self._generate(app, client)
        first = client.post("/api/devices/claim", json={"code": code})
        second = client.post("/api/devices/claim", json={"code": code})
        assert first.status_code == 200
        assert second.status_code == 404

    def test_expired_code_rejected(self, app, client, claim_repo):
        code = self._generate(app, client)
        # Forçar expiração no fake repo
        row = claim_repo.rows[hash_claim_code(code)]
        row["expires_at"] = datetime.now(timezone.utc) - timedelta(minutes=1)
        resp = client.post("/api/devices/claim", json={"code": code})
        assert resp.status_code == 404

    def test_unknown_code_rejected(self, client, claim_repo):
        resp = client.post("/api/devices/claim", json={"code": "ZZZZ9999"})
        assert resp.status_code == 404

    def test_missing_code_returns_400(self, client, claim_repo):
        resp = client.post("/api/devices/claim", json={})
        assert resp.status_code == 400

    def test_code_normalization_on_claim(self, app, client, claim_repo):
        code = self._generate(app, client)
        resp = client.post(
            "/api/devices/claim", json={"code": f" {code.lower()} "}
        )
        assert resp.status_code == 200
