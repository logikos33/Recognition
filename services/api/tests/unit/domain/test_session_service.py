"""Testes unitários — session_service (sessões concorrentes / última sessão ganha)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.domain.services.session_service import (
    is_jti_revoked,
    register_login_session,
)

USER = "22222222-2222-2222-2222-222222222222"
TENANT = "11111111-1111-1111-1111-111111111111"
EXPIRES = datetime.now(timezone.utc) + timedelta(hours=24)


def _repos(single_session: bool, revoked_rows=None):
    session_repo = MagicMock()
    session_repo.revoke_other_sessions.return_value = revoked_rows or []
    policy_repo = MagicMock()
    policy_repo.get_seat_policy.return_value = {
        "max_seats": None,
        "single_session": single_session,
    }
    return session_repo, policy_repo


class TestRegisterLoginSession:
    def test_registers_session_without_single_session(self):
        session_repo, policy_repo = _repos(single_session=False)
        result = register_login_session(
            session_repo, policy_repo,
            user_id=USER, tenant_id=TENANT, jti="jti-new",
            expires_at=EXPIRES, redis_client=MagicMock(),
        )
        assert result["registered"] is True
        assert result["revoked_count"] == 0
        session_repo.create_session.assert_called_once()
        session_repo.revoke_other_sessions.assert_not_called()

    def test_single_session_revokes_previous_and_blocklists(self):
        revoked = [
            {"jti": "jti-old-1", "expires_at": EXPIRES},
            {"jti": "jti-old-2", "expires_at": EXPIRES},
        ]
        session_repo, policy_repo = _repos(single_session=True, revoked_rows=revoked)
        redis_client = MagicMock()

        result = register_login_session(
            session_repo, policy_repo,
            user_id=USER, tenant_id=TENANT, jti="jti-new",
            expires_at=EXPIRES, redis_client=redis_client,
        )

        assert result["revoked_count"] == 2
        session_repo.revoke_other_sessions.assert_called_once_with(USER, keep_jti="jti-new")
        # Ambos os jtis antigos foram para o blocklist com TTL > 0
        keys = [call.args[0] for call in redis_client.setex.call_args_list]
        assert "revoked_jti:jti-old-1" in keys
        assert "revoked_jti:jti-old-2" in keys
        for call in redis_client.setex.call_args_list:
            assert call.args[1] >= 60  # TTL mínimo

    def test_single_session_with_no_previous_sessions(self):
        session_repo, policy_repo = _repos(single_session=True, revoked_rows=[])
        redis_client = MagicMock()
        result = register_login_session(
            session_repo, policy_repo,
            user_id=USER, tenant_id=TENANT, jti="jti-new",
            expires_at=EXPIRES, redis_client=redis_client,
        )
        assert result["revoked_count"] == 0
        redis_client.setex.assert_not_called()

    def test_best_effort_never_raises(self):
        session_repo = MagicMock()
        session_repo.create_session.side_effect = RuntimeError("db down")
        policy_repo = MagicMock()
        result = register_login_session(
            session_repo, policy_repo,
            user_id=USER, tenant_id=TENANT, jti="jti-new",
            expires_at=EXPIRES, redis_client=MagicMock(),
        )
        assert result["registered"] is False


class TestIsJtiRevoked:
    def test_revoked_jti_returns_true(self):
        redis_client = MagicMock()
        redis_client.exists.return_value = 1
        assert is_jti_revoked("jti-x", redis_client=redis_client) is True
        redis_client.exists.assert_called_once_with("revoked_jti:jti-x")

    def test_unknown_jti_returns_false(self):
        redis_client = MagicMock()
        redis_client.exists.return_value = 0
        assert is_jti_revoked("jti-y", redis_client=redis_client) is False

    def test_empty_jti_returns_false(self):
        assert is_jti_revoked("", redis_client=MagicMock()) is False

    def test_redis_error_fails_open(self):
        redis_client = MagicMock()
        redis_client.exists.side_effect = ConnectionError("redis down")
        assert is_jti_revoked("jti-z", redis_client=redis_client) is False
