"""Tests for task-012: enrollment token list + revoke.

GET  /api/v1/edge/sites/<site_id>/enrollment-tokens
POST /api/v1/edge/enrollment-tokens/<token_id>/revoke

Eval cases (spec):
  1. list: retorna status correto (active/used/expired) para 3 tokens semeados
  2. list: token_hash/plaintext AUSENTES da resposta
  3. revoke de token active → 200; token torna-se inutilizável para enroll
  4. revoke de token já usado → 409
  5. isolamento: list/revoke de site/token de OUTRO tenant → 404; nada alterado no outro tenant
  6. role insuficiente → 403; sem JWT → 401
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

from tests.security._helpers_tenant import make_two_tenant_contexts


def _make_jwt(app, tenant_id, role="admin", user_id=None):
    uid = str(user_id or uuid4())
    with app.app_context():
        return create_access_token(
            identity=uid,
            additional_claims={"tenant_id": str(tenant_id), "role": role},
        )


def _mock_site(tenant_id, site_id):
    return {
        "id": str(site_id),
        "tenant_id": str(tenant_id),
        "name": "Site X",
        "deployment_mode": "edge",
        "status": "active",
    }


def _active_token(tenant_id, site_id, token_id=None):
    return {
        "id": str(token_id or uuid4()),
        "tenant_id": str(tenant_id),
        "site_id": str(site_id),
        "created_at": datetime.now(timezone.utc) - timedelta(hours=1),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=23),
        "used_at": None,
        "used_by_device_id": None,
        "token_hash": "SENSITIVE_HASH_NEVER_EXPOSE",
    }


def _used_token(tenant_id, site_id, token_id=None):
    t = _active_token(tenant_id, site_id, token_id)
    t["used_at"] = datetime.now(timezone.utc) - timedelta(minutes=30)
    t["used_by_device_id"] = "device-abc"
    return t


def _expired_token(tenant_id, site_id, token_id=None):
    t = _active_token(tenant_id, site_id, token_id)
    t["expires_at"] = datetime.now(timezone.utc) - timedelta(hours=1)
    return t


# ---------------------------------------------------------------------------
# GET /api/v1/edge/sites/<site_id>/enrollment-tokens
# ---------------------------------------------------------------------------

class TestListEnrollmentTokens:

    def test_returns_active_used_expired_status(self, client, app):
        """Spec: status correto para 3 tipos de token."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)

        tid_active = uuid4()
        tid_used = uuid4()
        tid_expired = uuid4()

        tokens = [
            _active_token(tenant_id, site_id, tid_active),
            _used_token(tenant_id, site_id, tid_used),
            _expired_token(tenant_id, site_id, tid_expired),
        ]

        mock_repo = MagicMock()
        mock_repo.get_site_by_id.return_value = _mock_site(tenant_id, site_id)
        mock_repo.list_enrollment_tokens.return_value = tokens

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                f"/api/v1/edge/sites/{site_id}/enrollment-tokens",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 200
        result_tokens = res.get_json()["data"]["tokens"]
        assert len(result_tokens) == 3

        statuses = {str(t["id"]): t["status"] for t in result_tokens}
        assert statuses[str(tid_active)] == "active"
        assert statuses[str(tid_used)] == "used"
        assert statuses[str(tid_expired)] == "expired"

    def test_token_hash_absent_from_response(self, client, app):
        """C-05: token_hash/plaintext NUNCA na resposta."""
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id)

        mock_repo = MagicMock()
        mock_repo.get_site_by_id.return_value = _mock_site(tenant_id, site_id)
        mock_repo.list_enrollment_tokens.return_value = [_active_token(tenant_id, site_id)]

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                f"/api/v1/edge/sites/{site_id}/enrollment-tokens",
                headers={"Authorization": f"Bearer {token}"},
            )

        raw = res.get_data(as_text=True)
        assert "token_hash" not in raw, "token_hash NÃO deve aparecer na resposta"
        assert "SENSITIVE_HASH_NEVER_EXPOSE" not in raw

    def test_cross_tenant_site_returns_404(self, client, app):
        ctx_a, ctx_b = make_two_tenant_contexts(app)

        mock_repo = MagicMock()
        mock_repo.get_site_by_id.return_value = None  # site não pertence a ctx_b

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                f"/api/v1/edge/sites/{ctx_a.site_id}/enrollment-tokens",
                headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
            )

        assert res.status_code == 404
        mock_repo.list_enrollment_tokens.assert_not_called()

    def test_no_jwt_returns_401(self, client):
        res = client.get(f"/api/v1/edge/sites/{uuid4()}/enrollment-tokens")
        assert res.status_code == 401

    def test_operator_role_returns_403(self, client, app):
        tenant_id = uuid4()
        site_id = uuid4()
        token = _make_jwt(app, tenant_id, role="operator")

        mock_repo = MagicMock()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.get(
                f"/api/v1/edge/sites/{site_id}/enrollment-tokens",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert res.status_code == 403
        mock_repo.list_enrollment_tokens.assert_not_called()


# ---------------------------------------------------------------------------
# POST /api/v1/edge/enrollment-tokens/<token_id>/revoke
# ---------------------------------------------------------------------------

class TestRevokeEnrollmentToken:

    def test_revoke_active_token_returns_200(self, client, app):
        tenant_id = uuid4()
        site_id = uuid4()
        token_id = uuid4()
        jwt_tok = _make_jwt(app, tenant_id)

        active = _active_token(tenant_id, site_id, token_id)

        mock_repo = MagicMock()
        mock_repo.get_enrollment_token_by_id.return_value = active
        mock_repo.revoke_enrollment_token_if_unused.return_value = {
            **active,
            "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1),
        }

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                f"/api/v1/edge/enrollment-tokens/{token_id}/revoke",
                headers={"Authorization": f"Bearer {jwt_tok}"},
            )

        assert res.status_code == 200
        assert res.get_json()["data"]["revoked"] is True
        mock_repo.revoke_enrollment_token_if_unused.assert_called_once_with(
            str(token_id), str(tenant_id)
        )

    def test_revoke_used_token_returns_409(self, client, app):
        """Spec: token já usado → 409 (não dá pra revogar enrollment consumado)."""
        tenant_id = uuid4()
        site_id = uuid4()
        token_id = uuid4()
        jwt_tok = _make_jwt(app, tenant_id)

        used = _used_token(tenant_id, site_id, token_id)

        mock_repo = MagicMock()
        mock_repo.get_enrollment_token_by_id.return_value = used

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                f"/api/v1/edge/enrollment-tokens/{token_id}/revoke",
                headers={"Authorization": f"Bearer {jwt_tok}"},
            )

        assert res.status_code == 409
        mock_repo.revoke_enrollment_token_if_unused.assert_not_called()

    def test_revoke_nonexistent_token_returns_404(self, client, app):
        tenant_id = uuid4()
        token_id = uuid4()
        jwt_tok = _make_jwt(app, tenant_id)

        mock_repo = MagicMock()
        mock_repo.get_enrollment_token_by_id.return_value = None

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                f"/api/v1/edge/enrollment-tokens/{token_id}/revoke",
                headers={"Authorization": f"Bearer {jwt_tok}"},
            )

        assert res.status_code == 404

    def test_revoke_expired_token_is_idempotent_200(self, client, app):
        """Spec: token já expirado/revogado → 200 no-op (idempotente)."""
        tenant_id = uuid4()
        site_id = uuid4()
        token_id = uuid4()
        jwt_tok = _make_jwt(app, tenant_id)

        expired = _expired_token(tenant_id, site_id, token_id)

        mock_repo = MagicMock()
        mock_repo.get_enrollment_token_by_id.return_value = expired
        # UPDATE WHERE used_at IS NULL → still runs (already expired → SET expires_at = now() → no-op semantically)
        mock_repo.revoke_enrollment_token_if_unused.return_value = {
            **expired, "expires_at": datetime.now(timezone.utc),
        }

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                f"/api/v1/edge/enrollment-tokens/{token_id}/revoke",
                headers={"Authorization": f"Bearer {jwt_tok}"},
            )

        assert res.status_code == 200

    def test_cross_tenant_token_returns_404(self, client, app):
        """C-01: token de outro tenant → 404; nada alterado."""
        ctx_a, ctx_b = make_two_tenant_contexts(app)
        token_id = uuid4()

        mock_repo = MagicMock()
        mock_repo.get_enrollment_token_by_id.return_value = None  # não pertence a ctx_b

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                f"/api/v1/edge/enrollment-tokens/{token_id}/revoke",
                headers={"Authorization": f"Bearer {ctx_b.jwt_token}"},
            )

        assert res.status_code == 404
        mock_repo.revoke_enrollment_token_if_unused.assert_not_called()
        # Lookup feito com tenant_b, nunca tenant_a
        mock_repo.get_enrollment_token_by_id.assert_called_once_with(
            str(token_id), str(ctx_b.tenant_id)
        )

    def test_revoke_makes_token_unusable_for_enroll(self, client, app):
        """Spec: revoke → enroll usando esse token retorna 401."""
        import secrets

        tenant_id = uuid4()
        site_id = uuid4()
        token_id = uuid4()
        jwt_tok = _make_jwt(app, tenant_id)
        plaintext = secrets.token_urlsafe(32)

        active = _active_token(tenant_id, site_id, token_id)

        mock_repo = MagicMock()
        mock_repo.get_enrollment_token_by_id.return_value = active
        mock_repo.revoke_enrollment_token_if_unused.return_value = {**active}

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            revoke_res = client.post(
                f"/api/v1/edge/enrollment-tokens/{token_id}/revoke",
                headers={"Authorization": f"Bearer {jwt_tok}"},
            )
        assert revoke_res.status_code == 200

        # Simular enroll com token já revogado (expires_at = now() — passado)
        # enroll_device chama repo.enroll_device que levanta ValueError
        mock_repo.enroll_device.side_effect = ValueError("enrollment_token_invalid")

        from cryptography.hazmat.primitives.asymmetric import rsa as _rsa
        key = _rsa.generate_private_key(public_exponent=65537, key_size=2048)
        from cryptography.hazmat.primitives import serialization as _ser
        pub_pem = key.public_key().public_bytes(
            _ser.Encoding.PEM, _ser.PublicFormat.SubjectPublicKeyInfo
        ).decode()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            enroll_res = client.post(
                "/api/v1/edge/enroll",
                json={
                    "enrollment_token": plaintext,
                    "device_id": "test-device-001",
                    "device_name": "Test PC",
                    "public_key_pem": pub_pem,
                },
            )

        assert enroll_res.status_code == 401

    def test_no_jwt_returns_401(self, client):
        res = client.post(f"/api/v1/edge/enrollment-tokens/{uuid4()}/revoke")
        assert res.status_code == 401

    def test_operator_role_returns_403(self, client, app):
        tenant_id = uuid4()
        token_id = uuid4()
        jwt_tok = _make_jwt(app, tenant_id, role="operator")

        mock_repo = MagicMock()

        with patch("app.api.v1.edge.routes._get_site_repo", return_value=mock_repo):
            res = client.post(
                f"/api/v1/edge/enrollment-tokens/{token_id}/revoke",
                headers={"Authorization": f"Bearer {jwt_tok}"},
            )

        assert res.status_code == 403
        mock_repo.revoke_enrollment_token_if_unused.assert_not_called()
