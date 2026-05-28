"""Tests: Auth utilities (password hashing)."""
import pytest

from app.core.auth import check_password, hash_password


class TestPasswordHashing:
    """Testes para hash e verificação de senha."""

    def test_hash_and_verify(self) -> None:
        password = "securePassword123!"
        hashed = hash_password(password)
        assert check_password(password, hashed)

    def test_wrong_password_fails(self) -> None:
        hashed = hash_password("correct-password")
        assert not check_password("wrong-password", hashed)

    def test_hash_is_different_each_time(self) -> None:
        password = "samePassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2  # salt diferente

    def test_hash_is_string(self) -> None:
        hashed = hash_password("test")
        assert isinstance(hashed, str)

    def test_empty_password_hashes(self) -> None:
        hashed = hash_password("")
        assert isinstance(hashed, str)
        assert check_password("", hashed)
