"""Tests: Middleware (error handlers, security headers, request logging)."""
import pytest
from flask import Flask

from app.core.exceptions import ValidationError, NotFoundError
from app.core.middleware import (
    register_error_handlers,
    register_security_headers,
    register_request_logging,
)


class TestErrorHandlers:
    """Tests for error handler registration."""

    def setup_method(self) -> None:
        self.app = Flask(__name__)
        register_error_handlers(self.app)
        self.client = self.app.test_client()

    def test_app_error_handled(self) -> None:
        @self.app.route("/test-validation")
        def raise_validation():  # type: ignore[no-untyped-def]
            raise ValidationError("bad input")

        res = self.client.get("/test-validation")
        assert res.status_code == 400
        data = res.get_json()
        assert data["error"] == "bad input"
        assert data["success"] is False

    def test_not_found_error(self) -> None:
        @self.app.route("/test-notfound")
        def raise_notfound():  # type: ignore[no-untyped-def]
            raise NotFoundError("Item", "xyz")

        res = self.client.get("/test-notfound")
        assert res.status_code == 404

    def test_404_handler(self) -> None:
        res = self.client.get("/nonexistent-route")
        assert res.status_code == 404
        data = res.get_json()
        assert not data["success"]

    def test_405_handler(self) -> None:
        @self.app.route("/only-get", methods=["GET"])
        def only_get():  # type: ignore[no-untyped-def]
            return "ok"

        res = self.client.post("/only-get")
        assert res.status_code == 405

    def test_generic_exception_handled(self) -> None:
        @self.app.route("/test-crash")
        def crash():  # type: ignore[no-untyped-def]
            raise RuntimeError("unexpected")

        res = self.client.get("/test-crash")
        assert res.status_code == 500
        data = res.get_json()
        assert data["error"] == "Erro interno"
        # Stack trace should NOT be in response
        assert "RuntimeError" not in str(data)


class TestSecurityHeaders:
    """Tests for security headers middleware."""

    def setup_method(self) -> None:
        self.app = Flask(__name__)
        register_security_headers(self.app)

        @self.app.route("/test")
        def test_route():  # type: ignore[no-untyped-def]
            return "ok"

        self.client = self.app.test_client()

    def test_x_content_type_options(self) -> None:
        res = self.client.get("/test")
        assert res.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self) -> None:
        res = self.client.get("/test")
        assert res.headers.get("X-Frame-Options") == "SAMEORIGIN"

    def test_x_xss_protection(self) -> None:
        res = self.client.get("/test")
        assert res.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_referrer_policy(self) -> None:
        res = self.client.get("/test")
        assert "strict-origin" in res.headers.get("Referrer-Policy", "")


class TestRequestLogging:
    """Tests for request logging middleware."""

    def setup_method(self) -> None:
        self.app = Flask(__name__)
        register_request_logging(self.app)

        @self.app.route("/test")
        def test_route():  # type: ignore[no-untyped-def]
            return "ok"

        self.client = self.app.test_client()

    def test_request_completes(self) -> None:
        res = self.client.get("/test")
        assert res.status_code == 200
