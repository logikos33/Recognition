"""Tests: API route integration tests (using Flask test client)."""
import pytest


class TestAuthRoutes:
    """Integration tests for auth endpoints."""

    def test_login_missing_body(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.post("/api/auth/login", json={})
        data = res.get_json()
        assert res.status_code == 400 or not data.get("success")

    def test_login_invalid_json(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.post(
            "/api/auth/login",
            data="not json",
            content_type="text/plain",
        )
        assert res.status_code in (400, 415, 500)

    def test_register_missing_fields(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.post("/api/auth/register", json={"email": "test@test.com"})
        data = res.get_json()
        assert not data.get("success")

    def test_me_no_token(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.get("/api/auth/me")
        assert res.status_code in (401, 422)


class TestCameraRoutes:
    """Integration tests for camera endpoints."""

    def test_list_cameras_no_token(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.get("/api/cameras")
        assert res.status_code in (401, 422)

    def test_create_camera_no_token(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.post("/api/cameras", json={"name": "test", "host": "1.2.3.4"})
        assert res.status_code in (401, 422)


class TestTrainingRoutes:
    """Integration tests for training endpoints."""

    def test_list_videos_no_token(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.get("/api/training/videos")
        assert res.status_code in (401, 422)

    def test_list_jobs_no_token(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.get("/api/training/jobs")
        assert res.status_code in (401, 422)

    def test_list_models_no_token(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.get("/api/training/models")
        assert res.status_code in (401, 422)

    def test_get_classes_no_token(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.get("/api/classes")
        assert res.status_code in (401, 422)


class TestDashboardRoutes:
    """Integration tests for dashboard endpoints."""

    def test_stats_no_token(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.get("/api/v1/dashboard/stats")
        assert res.status_code in (401, 422)

    def test_detections_no_token(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.get("/api/v1/dashboard/detections")
        assert res.status_code in (401, 422)

    def test_export_no_token(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.get("/api/v1/reports/export")
        assert res.status_code in (401, 422)


class TestVideoRoutes:
    """Integration tests for video upload endpoints."""

    def test_upload_no_token(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.post("/api/v1/videos/upload")
        assert res.status_code in (401, 422)

    def test_upload_url_no_token(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.post("/api/v1/videos/upload-url", json={"filename": "test.mp4"})
        assert res.status_code in (401, 422)


class TestStorageRoutes:
    """Integration tests for storage endpoints."""

    def test_storage_health_public(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.get("/api/v1/storage/health")
        assert res.status_code == 200
        data = res.get_json()
        assert "data" in data
        assert "storage_type" in data["data"]

    def test_test_upload_no_token(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.post("/api/v1/storage/test-upload")
        assert res.status_code in (401, 422)


class TestStreamsRoutes:
    """Integration tests for streams endpoint."""

    def test_streams_status_public(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.get("/api/streams/status")
        assert res.status_code == 200
        data = res.get_json()
        assert "workers" in data


class TestFrontendServing:
    """Integration tests for frontend serving."""

    def test_root_returns_200(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.get("/")
        assert res.status_code == 200

    def test_unknown_path_returns_200(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.get("/some/unknown/path")
        assert res.status_code == 200


class TestErrorHandling:
    """Tests for error handler middleware."""

    def test_404_api_endpoint(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.get("/api/v1/nonexistent")
        # Should be caught by frontend catch-all or 404 handler
        assert res.status_code in (200, 404)

    def test_method_not_allowed(self, client) -> None:  # type: ignore[no-untyped-def]
        res = client.delete("/health")
        assert res.status_code == 405
        data = res.get_json()
        assert not data.get("success")
