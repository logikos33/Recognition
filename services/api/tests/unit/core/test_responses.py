"""Tests: Response helpers."""
from flask import Flask


class TestResponses:
    """Tests for success() and error() response helpers."""

    def setup_method(self) -> None:
        self.app = Flask(__name__)

    def test_success_default(self) -> None:
        with self.app.app_context():
            from app.core.responses import success
            response, status = success()
            data = response.get_json()
            assert data["success"] is True
            assert data["message"] == "OK"
            assert status == 200

    def test_success_with_data(self) -> None:
        with self.app.app_context():
            from app.core.responses import success
            response, status = success({"key": "value"}, status=201)
            data = response.get_json()
            assert data["data"]["key"] == "value"
            assert status == 201

    def test_error_default(self) -> None:
        with self.app.app_context():
            from app.core.responses import error
            response, status = error()
            data = response.get_json()
            assert data["success"] is False
            assert status == 400

    def test_error_with_code(self) -> None:
        with self.app.app_context():
            from app.core.responses import error
            response, status = error("Not found", 404, error_code="NOT_FOUND")
            data = response.get_json()
            assert data["error"] == "Not found"
            assert data["error_code"] == "NOT_FOUND"
            assert status == 404

    def test_success_none_data(self) -> None:
        with self.app.app_context():
            from app.core.responses import success
            response, _ = success(None)
            data = response.get_json()
            assert "data" not in data
