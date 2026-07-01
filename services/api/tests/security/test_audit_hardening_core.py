"""Regressão de segurança (auditoria 2026-07) — núcleo auth/config/headers.

Cobre achados P1 corrigidos:
  - Validação de JWT_SECRET_KEY em produção agora executa no boot (era código morto).
  - token_in_blocklist_loader registrado → token revogado é rejeitado.
  - POST /api/auth/logout revoga o jti atual.
  - Security headers de hardening (Permissions-Policy, CSP report-only).

Testes DB-free: usam a app de teste e monkeypatch dos serviços.
"""
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

from app.config import ProductionConfig


class TestProductionSecretValidation:
    """A validação vivia em __init_subclass__ (nunca executava). Agora em __init__."""

    def test_short_jwt_secret_raises(self, monkeypatch):
        monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "x" * 40, raising=False)
        monkeypatch.setattr(ProductionConfig, "JWT_SECRET_KEY", "short", raising=False)
        with pytest.raises(ValueError, match="32 caracteres"):
            ProductionConfig()

    def test_missing_jwt_secret_raises(self, monkeypatch):
        monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "x" * 40, raising=False)
        monkeypatch.setattr(ProductionConfig, "JWT_SECRET_KEY", "", raising=False)
        with pytest.raises(ValueError):
            ProductionConfig()

    def test_valid_secrets_ok(self, monkeypatch):
        monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "x" * 40, raising=False)
        monkeypatch.setattr(
            ProductionConfig, "JWT_SECRET_KEY", "y" * 40, raising=False
        )
        # Não deve levantar
        assert ProductionConfig() is not None


class TestTokenRevocation:
    """Sem token_in_blocklist_loader, logout/revoke não tinham efeito (CWE-613)."""

    def test_revoked_token_is_rejected(self, app, client, monkeypatch):
        from app.domain.services import session_service

        with app.app_context():
            token = create_access_token(
                identity=str(uuid4()),
                additional_claims={"tenant_id": str(uuid4()), "role": "operator"},
            )

        # Simula jti presente na blocklist Redis
        monkeypatch.setattr(
            session_service, "is_jti_revoked", lambda jti, **kw: True
        )
        resp = client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        # A camada JWT rejeita ANTES da view (401), sem tocar no banco.
        assert resp.status_code == 401

    def test_logout_revokes_current_jti(self, app, client, monkeypatch):
        from app.domain.services import session_service

        captured = {}

        def fake_revoke(jti, expires_at=None, **kw):
            captured["jti"] = jti
            return True

        monkeypatch.setattr(session_service, "is_jti_revoked", lambda jti, **kw: False)
        monkeypatch.setattr(session_service, "revoke_jti", fake_revoke)

        with app.app_context():
            token = create_access_token(
                identity=str(uuid4()),
                additional_claims={"tenant_id": str(uuid4()), "role": "operator"},
            )
        resp = client.post(
            "/api/auth/logout", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        assert captured.get("jti"), "logout deve revogar o jti do token atual"


class TestSecurityHeaders:
    def test_hardening_headers_present(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
        # Adicionados na auditoria:
        assert "geolocation=()" in (resp.headers.get("Permissions-Policy") or "")
        assert resp.headers.get("Content-Security-Policy-Report-Only")
