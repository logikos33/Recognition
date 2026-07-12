"""
Tests: /api/v1/recorders (WS-B1, ADR-0034) — CRUD, test-connection,
timeline, extract-frames. Gate @require_training_role('write') em mutações.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from flask_jwt_extended import create_access_token

TENANT_ID = "00000000-0000-0000-0000-000000000001"
_ROUTES = "app.api.v1.recorders.routes"


def _auth_header(app, role="admin", tenant_id=TENANT_ID):
    with app.app_context():
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={"tenant_id": tenant_id, "tenant_schema": None, "role": role},
        )
    return {"Authorization": f"Bearer {token}"}


class TestListCreateRecorders:
    def test_no_auth_returns_401(self, client):
        assert client.get("/api/v1/recorders").status_code == 401

    def test_list_returns_recorders(self, app, client):
        mock_service = MagicMock()
        mock_service.list_recorders.return_value = [{"id": str(uuid4()), "name": "NVR 1"}]
        with patch(f"{_ROUTES}._get_service", return_value=mock_service):
            resp = client.get("/api/v1/recorders", headers=_auth_header(app))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["total"] == 1

    def test_create_requires_write_role(self, app, client):
        resp = client.post(
            "/api/v1/recorders",
            json={"name": "NVR 1", "host": "10.0.0.5"},
            headers=_auth_header(app, role="operator"),
        )
        assert resp.status_code == 403

    def test_create_returns_201(self, app, client):
        mock_service = MagicMock()
        mock_service.create_recorder.return_value = {"id": str(uuid4()), "name": "NVR 1"}
        with patch(f"{_ROUTES}._get_service", return_value=mock_service):
            resp = client.post(
                "/api/v1/recorders",
                json={"name": "NVR 1", "host": "10.0.0.5"},
                headers=_auth_header(app),
            )
        assert resp.status_code == 201

    def test_create_validation_error_propagates_as_400(self, app, client):
        from app.core.exceptions import ValidationError
        mock_service = MagicMock()
        mock_service.create_recorder.side_effect = ValidationError("name e host são obrigatórios")
        with patch(f"{_ROUTES}._get_service", return_value=mock_service):
            resp = client.post(
                "/api/v1/recorders", json={}, headers=_auth_header(app),
            )
        assert resp.status_code == 400


class TestGetUpdateDeleteRecorder:
    def test_invalid_uuid_returns_400(self, app, client):
        resp = client.get("/api/v1/recorders/not-a-uuid", headers=_auth_header(app))
        assert resp.status_code == 400

    def test_get_not_found_returns_404(self, app, client):
        mock_service = MagicMock()
        mock_service.get_recorder.return_value = None
        with patch(f"{_ROUTES}._get_service", return_value=mock_service):
            resp = client.get(f"/api/v1/recorders/{uuid4()}", headers=_auth_header(app))
        assert resp.status_code == 404

    def test_delete_requires_write_role(self, app, client):
        resp = client.delete(
            f"/api/v1/recorders/{uuid4()}", headers=_auth_header(app, role="operator")
        )
        assert resp.status_code == 403

    def test_delete_success(self, app, client):
        mock_service = MagicMock()
        mock_service.delete_recorder.return_value = True
        with patch(f"{_ROUTES}._get_service", return_value=mock_service):
            resp = client.delete(f"/api/v1/recorders/{uuid4()}", headers=_auth_header(app))
        assert resp.status_code == 200


class TestConnectionTest:
    def test_requires_write_role(self, app, client):
        resp = client.post(
            f"/api/v1/recorders/{uuid4()}/test", headers=_auth_header(app, role="operator")
        )
        assert resp.status_code == 403

    def test_returns_test_result(self, app, client):
        mock_service = MagicMock()
        mock_service.test_connection.return_value = {"status": "online"}
        with patch(f"{_ROUTES}._get_service", return_value=mock_service):
            resp = client.post(f"/api/v1/recorders/{uuid4()}/test", headers=_auth_header(app))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["recorder"]["status"] == "online"


class TestRecordingsTimeline:
    def test_missing_from_to_returns_400(self, app, client):
        recorder_id = uuid4()
        mock_service = MagicMock()
        with patch(f"{_ROUTES}._get_service", return_value=mock_service):
            resp = client.get(
                f"/api/v1/recorders/{recorder_id}/recordings", headers=_auth_header(app)
            )
        assert resp.status_code == 400

    def test_returns_segments(self, app, client):
        recorder_id = uuid4()
        mock_service = MagicMock()
        mock_service.get_recorder_or_raise.return_value = {
            "host": "10.0.0.5", "port": 80, "protocol": "onvif", "password_encrypted": None,
        }
        mock_client = MagicMock()
        from datetime import datetime
        from app.infrastructure.nvr.base import RecordingSegment
        mock_client.search_recordings.return_value = [
            RecordingSegment(
                channel=1, start=datetime(2026, 7, 10, 10), end=datetime(2026, 7, 10, 10, 5),
                playback_ref="x",
            )
        ]
        with patch(f"{_ROUTES}._get_service", return_value=mock_service), patch(
            "app.infrastructure.nvr.factory.get_nvr_client", return_value=mock_client
        ):
            resp = client.get(
                f"/api/v1/recorders/{recorder_id}/recordings"
                "?channel=1&from=2026-07-10T09:00:00Z&to=2026-07-10T11:00:00Z",
                headers=_auth_header(app),
            )
        assert resp.status_code == 200
        assert len(resp.get_json()["data"]["segments"]) == 1

    def test_search_failure_returns_502(self, app, client):
        recorder_id = uuid4()
        mock_service = MagicMock()
        mock_service.get_recorder_or_raise.return_value = {
            "host": "10.0.0.5", "port": 80, "protocol": "onvif", "password_encrypted": None,
        }
        with patch(f"{_ROUTES}._get_service", return_value=mock_service), patch(
            "app.infrastructure.nvr.factory.get_nvr_client",
            side_effect=RuntimeError("device unreachable"),
        ):
            resp = client.get(
                f"/api/v1/recorders/{recorder_id}/recordings"
                "?from=2026-07-10T09:00:00Z&to=2026-07-10T11:00:00Z",
                headers=_auth_header(app),
            )
        assert resp.status_code == 502


class TestExtractFrames:
    def test_requires_write_role(self, app, client):
        resp = client.post(
            f"/api/v1/recorders/{uuid4()}/extract-frames",
            headers=_auth_header(app, role="operator"),
        )
        assert resp.status_code == 403

    def test_missing_from_to_returns_400(self, app, client):
        recorder_id = uuid4()
        mock_service = MagicMock()
        with patch(f"{_ROUTES}._get_service", return_value=mock_service):
            resp = client.post(
                f"/api/v1/recorders/{recorder_id}/extract-frames",
                json={"channel": 1},
                headers=_auth_header(app),
            )
        assert resp.status_code == 400

    def test_dispatches_celery_task_returns_202(self, app, client):
        recorder_id = uuid4()
        mock_service = MagicMock()
        mock_service.get_recorder_or_raise.return_value = {"id": recorder_id}
        mock_task = MagicMock()
        mock_task.id = "task-abc-123"
        with patch(f"{_ROUTES}._get_service", return_value=mock_service), patch(
            "app.infrastructure.queue.tasks.nvr_extraction.extract_nvr_frames.delay",
            return_value=mock_task,
        ) as mock_delay:
            resp = client.post(
                f"/api/v1/recorders/{recorder_id}/extract-frames",
                json={
                    "channel": 1, "from": "2026-07-10T09:00:00Z", "to": "2026-07-10T11:00:00Z",
                    "interval_seconds": 10,
                },
                headers=_auth_header(app),
            )
        assert resp.status_code == 202
        assert resp.get_json()["data"]["task_id"] == "task-abc-123"
        mock_delay.assert_called_once()
