"""Tests: AuthService."""
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.domain.services.auth_service import AuthService


class TestAuthService:
    """Testes para AuthService."""

    def setup_method(self) -> None:
        self.user_repo = MagicMock()
        self.service = AuthService(self.user_repo)

    def test_register_success(self) -> None:
        uid = uuid4()
        self.user_repo.exists_by_email.return_value = False
        self.user_repo.create.return_value = {
            "id": uid, "email": "test@test.com",
            "name": "Test", "role": "operator",
            "is_active": True, "created_at": "2024-01-01",
        }
        result = self.service.register("test@test.com", "password123", "Test")
        assert result["email"] == "test@test.com"
        assert result["id"] == str(uid)

    def test_register_email_exists(self) -> None:
        self.user_repo.exists_by_email.return_value = True
        with pytest.raises(ConflictError, match="já cadastrado"):
            self.service.register("existing@test.com", "password123", "Test")

    def test_register_short_password(self) -> None:
        with pytest.raises(ValidationError, match="mínimo 6"):
            self.service.register("test@test.com", "123", "Test")

    def test_register_missing_fields(self) -> None:
        with pytest.raises(ValidationError, match="obrigatórios"):
            self.service.register("", "password123", "Test")

    def test_login_success(self) -> None:
        import bcrypt
        hashed = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode()
        uid = uuid4()
        self.user_repo.get_by_email.return_value = {
            "id": uid, "email": "test@test.com",
            "name": "Test", "role": "operator",
            "password_hash": hashed, "is_active": True,
            "created_at": "2024-01-01",
        }
        result = self.service.login("test@test.com", "password123")
        assert result["email"] == "test@test.com"
        assert "password_hash" not in result

    def test_login_wrong_password(self) -> None:
        import bcrypt
        hashed = bcrypt.hashpw(b"correct", bcrypt.gensalt()).decode()
        self.user_repo.get_by_email.return_value = {
            "id": uuid4(), "email": "test@test.com",
            "password_hash": hashed, "is_active": True,
        }
        with pytest.raises(AuthenticationError, match="inválidas"):
            self.service.login("test@test.com", "wrong")

    def test_login_user_not_found(self) -> None:
        self.user_repo.get_by_email.return_value = None
        with pytest.raises(AuthenticationError, match="inválidas"):
            self.service.login("nobody@test.com", "password")

    def test_login_inactive_user(self) -> None:
        self.user_repo.get_by_email.return_value = {
            "id": uuid4(), "email": "test@test.com",
            "password_hash": "x", "is_active": False,
        }
        with pytest.raises(AuthenticationError, match="inválidas"):
            self.service.login("test@test.com", "password")

    def test_get_user_success(self) -> None:
        uid = uuid4()
        self.user_repo.get_by_id.return_value = {
            "id": uid, "email": "test@test.com",
            "name": "Test", "role": "operator",
        }
        result = self.service.get_user(uid)
        assert result["id"] == str(uid)

    def test_get_user_not_found(self) -> None:
        self.user_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            self.service.get_user(uuid4())
