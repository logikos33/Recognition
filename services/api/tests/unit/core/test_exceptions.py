"""Tests: Custom exception hierarchy."""
import pytest

from app.core.exceptions import (
    EpiMonitorError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    StorageError,
    DatabaseError,
    TrainingError,
    InferenceError,
    StreamError,
)


class TestExceptionHierarchy:
    """All exceptions inherit from EpiMonitorError."""

    def test_validation_error(self) -> None:
        exc = ValidationError("bad input")
        assert isinstance(exc, EpiMonitorError)
        assert exc.status_code == 400
        assert exc.message == "bad input"

    def test_authentication_error(self) -> None:
        exc = AuthenticationError()
        assert exc.status_code == 401

    def test_authorization_error(self) -> None:
        exc = AuthorizationError()
        assert exc.status_code == 403

    def test_not_found_error(self) -> None:
        exc = NotFoundError("Camera", "abc123")
        assert exc.status_code == 404
        assert "Camera" in exc.message
        assert "abc123" in exc.message

    def test_not_found_without_id(self) -> None:
        exc = NotFoundError("Video")
        assert exc.status_code == 404
        assert "Video" in exc.message

    def test_conflict_error(self) -> None:
        exc = ConflictError("already exists")
        assert exc.status_code == 409

    def test_storage_error(self) -> None:
        exc = StorageError("R2 down")
        assert exc.status_code == 502

    def test_database_error(self) -> None:
        exc = DatabaseError("pool exhausted")
        assert exc.status_code == 503

    def test_training_error(self) -> None:
        exc = TrainingError("GPU OOM")
        assert exc.status_code == 500

    def test_inference_error(self) -> None:
        exc = InferenceError("model not loaded")
        assert exc.status_code == 500

    def test_stream_error(self) -> None:
        exc = StreamError("ffmpeg crashed")
        assert exc.status_code == 500

    def test_base_exception(self) -> None:
        exc = EpiMonitorError("generic", 418)
        assert exc.status_code == 418
        assert str(exc) == "generic"


class TestExceptionCatching:
    """Catching EpiMonitorError catches all subtypes."""

    def test_catch_all_subtypes(self) -> None:
        exceptions = [
            ValidationError("x"),
            AuthenticationError(),
            AuthorizationError(),
            NotFoundError("x"),
            ConflictError("x"),
            StorageError("x"),
            DatabaseError("x"),
            TrainingError("x"),
            InferenceError("x"),
            StreamError("x"),
        ]
        for exc in exceptions:
            try:
                raise exc
            except EpiMonitorError as caught:
                assert caught.status_code > 0
