"""Tests: Health check endpoint."""
import pytest


class TestHealthEndpoint:
    """Testes para /api/v1/health."""

    def test_health_returns_json(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get("/api/v1/health")
        data = response.get_json()
        assert "status" in data
        assert "checks" in data

    def test_health_has_db_check(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get("/api/v1/health")
        data = response.get_json()
        assert "database" in data["checks"]

    def test_health_has_redis_check(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get("/api/v1/health")
        data = response.get_json()
        assert "redis" in data["checks"]

    def test_health_legacy_path(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get("/health")
        assert response.status_code in (200, 503)
        data = response.get_json()
        assert "status" in data
