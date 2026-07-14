"""Tests: PasswordResetService (ADR-0042 Fase 2)."""
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ValidationError
from app.domain.services.password_reset_service import PasswordResetService

MODULE = "app.domain.services.password_reset_service"


class TestRequestReset:

    def setup_method(self) -> None:
        self.user_repo = MagicMock()
        self.session_repo = MagicMock()
        self.service = PasswordResetService(self.user_repo, self.session_repo)

    def test_unknown_email_does_not_raise_and_sends_nothing(self) -> None:
        self.user_repo.get_by_email.return_value = None
        with patch(f"{MODULE}.send_email") as mock_send:
            self.service.request_reset("nobody@test.com")
        mock_send.assert_not_called()

    def test_inactive_user_does_not_send_email(self) -> None:
        self.user_repo.get_by_email.return_value = {
            "id": "u1", "email": "x@test.com", "is_active": False,
        }
        with patch(f"{MODULE}.send_email") as mock_send:
            self.service.request_reset("x@test.com")
        mock_send.assert_not_called()

    def test_active_user_stores_token_and_sends_email(self) -> None:
        self.user_repo.get_by_email.return_value = {
            "id": "u1", "email": "x@test.com", "is_active": True, "name": "X",
        }
        mock_redis = MagicMock()
        with patch(f"{MODULE}._get_redis", return_value=mock_redis), \
             patch(f"{MODULE}.send_email", return_value=True) as mock_send:
            self.service.request_reset("x@test.com")
        assert mock_redis.setex.call_count == 1
        key, ttl, value = mock_redis.setex.call_args[0]
        assert key.startswith("pwreset:")
        assert ttl == 1800
        assert value == "u1"
        mock_send.assert_called_once()

    def test_redis_failure_does_not_raise(self) -> None:
        self.user_repo.get_by_email.return_value = {
            "id": "u1", "email": "x@test.com", "is_active": True,
        }
        with patch(f"{MODULE}._get_redis", side_effect=Exception("redis down")), \
             patch(f"{MODULE}.send_email") as mock_send:
            self.service.request_reset("x@test.com")
        mock_send.assert_not_called()

    def test_blank_email_is_noop(self) -> None:
        with patch(f"{MODULE}.send_email") as mock_send:
            self.service.request_reset("")
        self.user_repo.get_by_email.assert_not_called()
        mock_send.assert_not_called()


class TestResetPassword:

    def setup_method(self) -> None:
        self.user_repo = MagicMock()
        self.session_repo = MagicMock()
        self.service = PasswordResetService(self.user_repo, self.session_repo)

    def test_missing_token_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError, match="obrigatórios"):
            self.service.reset_password("", "newpass123")

    def test_short_password_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError, match="mínimo 6"):
            self.service.reset_password("sometoken", "123")

    def test_invalid_or_expired_token_raises(self) -> None:
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        with patch(f"{MODULE}._get_redis", return_value=mock_redis):
            with pytest.raises(ValidationError, match="inválido ou expirado"):
                self.service.reset_password("badtoken", "newpass123")

    def test_valid_token_updates_password_and_invalidates_sessions(self) -> None:
        mock_redis = MagicMock()
        mock_redis.get.return_value = "u1"
        self.user_repo.reset_password.return_value = {"id": "u1", "email": "x@test.com"}
        with patch(f"{MODULE}._get_redis", return_value=mock_redis), \
             patch("app.domain.services.session_service.invalidate_all_sessions") as mock_invalidate:
            self.service.reset_password("goodtoken", "newpass123")
        self.user_repo.reset_password.assert_called_once()
        mock_redis.delete.assert_called_once_with("pwreset:goodtoken")
        mock_invalidate.assert_called_once_with(self.session_repo, "u1")

    def test_user_repo_returns_none_raises_validation_error(self) -> None:
        mock_redis = MagicMock()
        mock_redis.get.return_value = "u1"
        self.user_repo.reset_password.return_value = None
        with patch(f"{MODULE}._get_redis", return_value=mock_redis):
            with pytest.raises(ValidationError, match="inválido ou expirado"):
                self.service.reset_password("goodtoken", "newpass123")

    def test_redis_lookup_failure_raises_validation_error(self) -> None:
        with patch(f"{MODULE}._get_redis", side_effect=Exception("redis down")):
            with pytest.raises(ValidationError, match="inválido ou expirado"):
                self.service.reset_password("goodtoken", "newpass123")
