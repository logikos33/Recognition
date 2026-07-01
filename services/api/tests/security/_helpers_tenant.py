"""
Helpers de isolamento multi-tenant para testes das rotas /api/v1/edge/.

REGRA: toda task de endpoint /edge DEVE incluir ao menos um teste cross-tenant
usando os helpers deste módulo (make_two_tenant_contexts + assert_response_only_contains_tenant).

Padrão de uso:
    def test_tenant_b_cannot_see_tenant_a_sites(client, app):
        ctx_a, ctx_b = make_two_tenant_contexts(app)
        # ... seed data para ctx_a via mock ...
        resp = client.get(
            "/api/v1/edge/sites",
            headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
        )
        assert_response_only_contains_tenant(resp.get_json(), ctx_b.tenant_id)
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from uuid import UUID, uuid4

import jwt as pyjwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask
from flask_jwt_extended import create_access_token


@dataclass
class TenantContext:
    """Estado mínimo de um tenant para testes de isolamento."""

    tenant_id: UUID
    site_id: UUID
    device_id: str
    jwt_token: str  # Bearer token JWT de usuário admin


def make_user_jwt(
    app: Flask,
    tenant_id: UUID | str,
    role: str = "admin",
    user_id: UUID | str | None = None,
) -> str:
    """Cria JWT de usuário com tenant_id e role nos additional_claims.

    Reúsa o mesmo padrão de test_edge_admin_sites.py para consistência.
    """
    uid = str(user_id or uuid4())
    with app.app_context():
        return create_access_token(
            identity=uid,
            additional_claims={"tenant_id": str(tenant_id), "role": role},
        )


def make_device_token(
    tenant_id: UUID | str,
    site_id: UUID | str,
    device_id: str | None = None,
    exp_offset: int = 3600,
) -> tuple[str, str]:
    """Cria RS256 device token para testes. Retorna (token_str, public_key_pem).

    Keypair é gerado em memória — sem persistência no banco.
    O chamador deve injetar public_key_pem no mock do repositório
    (device_record["public_key_pem"]).

    Padrão retirado de test_edge_heartbeat.py para consistência.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    did = device_id or f"device-{str(uuid4())[:8]}"
    now = int(time.time())
    token = pyjwt.encode(
        {
            "device_id": did,
            "tenant_id": str(tenant_id),
            "site_id": str(site_id),
            "scopes": ["heartbeat:write"],
            "iat": now,
            "exp": now + exp_offset,
        },
        private_pem,
        algorithm="RS256",
    )
    return token, public_pem


def make_two_tenant_contexts(app: Flask) -> tuple[TenantContext, TenantContext]:
    """Fabrica dois TenantContext independentes para testes de isolamento.

    Ambos têm tenant_id, site_id e jwt_token distintos.
    """
    tenant_a, site_a = uuid4(), uuid4()
    tenant_b, site_b = uuid4(), uuid4()

    return (
        TenantContext(
            tenant_id=tenant_a,
            site_id=site_a,
            device_id=f"device-{str(tenant_a)[:8]}",
            jwt_token=make_user_jwt(app, tenant_a),
        ),
        TenantContext(
            tenant_id=tenant_b,
            site_id=site_b,
            device_id=f"device-{str(tenant_b)[:8]}",
            jwt_token=make_user_jwt(app, tenant_b),
        ),
    )


def assert_response_only_contains_tenant(
    resp_json: dict,
    tenant_id: UUID | str,
) -> None:
    """Garante que a resposta JSON não contém registros de outro tenant.

    Verifica o campo 'tenant_id' em cada item das listas conhecidas do
    blueprint /edge ('sites', 'devices', 'heartbeats') e no objeto
    'data' direto quando for um único recurso.

    Levanta AssertionError com mensagem "Cross-tenant leak" se detectar vazamento.
    """
    expected = str(tenant_id)
    data = resp_json.get("data", {})

    for list_key in ("sites", "devices", "heartbeats"):
        for item in data.get(list_key, []):
            found = str(item.get("tenant_id", ""))
            assert found == expected, (
                f"Cross-tenant leak em '{list_key}': "
                f"tenant_id={found!r} diverge do esperado={expected!r}"
            )

    if isinstance(data, dict) and "tenant_id" in data:
        found = str(data["tenant_id"])
        assert found == expected, (
            f"Cross-tenant leak em data: tenant_id={found!r} != {expected!r}"
        )
