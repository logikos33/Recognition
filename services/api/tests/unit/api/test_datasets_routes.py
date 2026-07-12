"""Tests: datasets/routes.py — datasets pai + build de versão COCO (WS-A3).

O blueprint é registrado localmente no fixture (guardado) para não depender
do wiring em app/__init__.py (colado pelo orquestrador).
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app import create_app

TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
DATASET_ID = str(uuid4())
VERSION_ID = str(uuid4())

_SAMPLE_DATASET = {
    "id": DATASET_ID,
    "tenant_id": TENANT_ID,
    "module_code": "epi",
    "name": "EPI base",
    "description": None,
}

_SAMPLE_VERSION_DETAIL = {
    "id": VERSION_ID,
    "tenant_id": TENANT_ID,
    "dataset_id": DATASET_ID,
    "version": "v1",
    "status": "ready",
    "coco_r2_key": f"dataset-exports/{TENANT_ID}/{DATASET_ID}/v1",
    "coco_files": {
        "train": {
            "key": f"dataset-exports/{TENANT_ID}/{DATASET_ID}/v1/train/_annotations.coco.json",
            "url": "https://mock-r2.test/train.json",
        },
    },
}


@pytest.fixture
def app():
    """App com datasets_bp registrado (guardado p/ quando o wiring chegar)."""
    application = create_app("testing")
    if "datasets" not in application.blueprints:
        from app.api.v1.datasets.routes import datasets_bp
        application.register_blueprint(datasets_bp)
    yield application


def _make_headers(app, role="admin"):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=USER_ID,
            additional_claims={
                "tenant_id": TENANT_ID,
                "tenant_schema": "public",
                "role": role,
                "modules": ["epi"],
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers(app):
    return _make_headers(app, role="admin")


@pytest.fixture
def operator_headers(app):
    return _make_headers(app, role="operator")


def _patch_service(service):
    return patch(
        "app.api.v1.datasets.routes._get_service", return_value=service
    )


def _make_service(**overrides):
    service = MagicMock()
    service.list_datasets.return_value = [_SAMPLE_DATASET]
    service.create_dataset.return_value = _SAMPLE_DATASET
    service.get_dataset.return_value = _SAMPLE_DATASET
    service.list_dataset_versions.return_value = []
    service.next_version_label.return_value = "v1"
    service.validate_split.return_value = {"train": 0.7, "val": 0.2, "test": 0.1}
    service.get_version_detail.return_value = _SAMPLE_VERSION_DETAIL
    for key, value in overrides.items():
        setattr(getattr(service, key), "return_value", value)
    return service


# ---------------------------------------------------------------------------
# GET /api/v1/datasets
# ---------------------------------------------------------------------------

class TestListDatasets:

    def test_no_token_returns_401(self, client):
        assert client.get("/api/v1/datasets").status_code == 401

    def test_lists_tenant_datasets(self, client, auth_headers):
        service = _make_service()
        with _patch_service(service):
            resp = client.get("/api/v1/datasets", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["total"] == 1
        assert body["data"]["datasets"][0]["id"] == DATASET_ID
        service.list_datasets.assert_called_once_with(TENANT_ID, None)

    def test_module_filter_forwarded(self, client, auth_headers):
        service = _make_service()
        with _patch_service(service):
            client.get("/api/v1/datasets?module=fueling", headers=auth_headers)
        service.list_datasets.assert_called_once_with(TENANT_ID, "fueling")


# ---------------------------------------------------------------------------
# POST /api/v1/datasets
# ---------------------------------------------------------------------------

class TestCreateDataset:

    def test_no_token_returns_401(self, client):
        assert client.post("/api/v1/datasets", json={"name": "x"}).status_code == 401

    def test_operator_without_override_returns_403(self, client, operator_headers):
        service = _make_service()
        with _patch_service(service):
            resp = client.post(
                "/api/v1/datasets", json={"name": "x"}, headers=operator_headers
            )
        assert resp.status_code == 403
        service.create_dataset.assert_not_called()

    def test_missing_name_returns_400(self, client, auth_headers):
        service = _make_service()
        service.create_dataset.side_effect = ValueError(
            "Campo 'name' é obrigatório"
        )
        with _patch_service(service):
            resp = client.post("/api/v1/datasets", json={}, headers=auth_headers)
        assert resp.status_code == 400
        assert resp.get_json()["success"] is False

    def test_creates_dataset_201(self, client, auth_headers):
        service = _make_service()
        with _patch_service(service):
            resp = client.post(
                "/api/v1/datasets",
                json={"name": "EPI base", "module_code": "epi"},
                headers=auth_headers,
            )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["dataset"]["id"] == DATASET_ID
        kwargs = service.create_dataset.call_args.kwargs
        assert kwargs["tenant_id"] == TENANT_ID
        assert kwargs["created_by"] == USER_ID
        assert kwargs["name"] == "EPI base"


# ---------------------------------------------------------------------------
# GET /api/v1/datasets/<id>
# ---------------------------------------------------------------------------

class TestGetDataset:

    def test_invalid_uuid_returns_400(self, client, auth_headers):
        with _patch_service(_make_service()):
            resp = client.get("/api/v1/datasets/not-a-uuid", headers=auth_headers)
        assert resp.status_code == 400

    def test_not_found_returns_404(self, client, auth_headers):
        service = _make_service(get_dataset=None)
        with _patch_service(service):
            resp = client.get(
                f"/api/v1/datasets/{DATASET_ID}", headers=auth_headers
            )
        assert resp.status_code == 404

    def test_returns_dataset_with_versions(self, client, auth_headers):
        service = _make_service()
        service.list_dataset_versions.return_value = [{"id": VERSION_ID}]
        with _patch_service(service):
            resp = client.get(
                f"/api/v1/datasets/{DATASET_ID}", headers=auth_headers
            )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["dataset"]["id"] == DATASET_ID
        assert data["versions"][0]["id"] == VERSION_ID


# ---------------------------------------------------------------------------
# POST /api/v1/datasets/<id>/versions
# ---------------------------------------------------------------------------

class TestCreateDatasetVersion:

    def _post(self, client, headers, body=None, dataset_id=DATASET_ID):
        return client.post(
            f"/api/v1/datasets/{dataset_id}/versions",
            json=body or {},
            headers=headers,
        )

    def test_no_token_returns_401(self, client):
        resp = client.post(f"/api/v1/datasets/{DATASET_ID}/versions", json={})
        assert resp.status_code == 401

    def test_operator_without_override_returns_403(self, client, operator_headers):
        with _patch_service(_make_service()):
            resp = self._post(client, operator_headers)
        assert resp.status_code == 403

    def test_invalid_uuid_returns_400(self, client, auth_headers):
        with _patch_service(_make_service()):
            resp = self._post(client, auth_headers, dataset_id="nope")
        assert resp.status_code == 400

    def test_unsupported_format_returns_400(self, client, auth_headers):
        with _patch_service(_make_service()):
            resp = self._post(client, auth_headers, body={"format": "yolo"})
        assert resp.status_code == 400

    def test_invalid_split_returns_400(self, client, auth_headers):
        service = _make_service()
        service.validate_split.side_effect = ValueError("split deve somar 1.0")
        with _patch_service(service):
            resp = self._post(
                client, auth_headers, body={"split": {"train": 0.9, "val": 0.9}}
            )
        assert resp.status_code == 400

    def test_invalid_augmentations_returns_400(self, client, auth_headers):
        with _patch_service(_make_service()):
            resp = self._post(
                client, auth_headers, body={"augmentations": "flip"}
            )
        assert resp.status_code == 400

    def test_dataset_not_found_returns_404(self, client, auth_headers):
        service = _make_service(get_dataset=None)
        with _patch_service(service), patch(
            "app.infrastructure.queue.tasks.versioning_v2.build_dataset_version_v2"
        ) as task:
            resp = self._post(client, auth_headers)
        assert resp.status_code == 404
        task.delay.assert_not_called()

    def test_dispatches_build_task_202(self, client, auth_headers):
        service = _make_service()
        with _patch_service(service), patch(
            "app.infrastructure.queue.tasks.versioning_v2.build_dataset_version_v2"
        ) as task:
            task.delay.return_value = MagicMock(id="task-123")
            resp = self._post(client, auth_headers, body={"name": "v-golden"})

        assert resp.status_code == 202
        data = resp.get_json()["data"]
        assert data["task_id"] == "task-123"
        assert data["version"] == "v-golden"
        assert data["status"] == "building"

        kwargs = task.delay.call_args.kwargs
        assert kwargs["tenant_id"] == TENANT_ID
        assert kwargs["dataset_id"] == DATASET_ID
        assert kwargs["user_id"] == USER_ID
        assert kwargs["version"] == "v-golden"
        assert kwargs["export_format"] == "coco"
        assert kwargs["module_code"] == "epi"

    def test_autogenerates_version_label(self, client, auth_headers):
        service = _make_service()
        service.next_version_label.return_value = "v3"
        with _patch_service(service), patch(
            "app.infrastructure.queue.tasks.versioning_v2.build_dataset_version_v2"
        ) as task:
            task.delay.return_value = MagicMock(id="task-9")
            resp = self._post(client, auth_headers)
        assert resp.get_json()["data"]["version"] == "v3"


# ---------------------------------------------------------------------------
# GET /api/v1/dataset-versions/<id>
# ---------------------------------------------------------------------------

class TestGetDatasetVersion:

    def test_no_token_returns_401(self, client):
        assert client.get(f"/api/v1/dataset-versions/{VERSION_ID}").status_code == 401

    def test_invalid_uuid_returns_400(self, client, auth_headers):
        with _patch_service(_make_service()):
            resp = client.get(
                "/api/v1/dataset-versions/xyz", headers=auth_headers
            )
        assert resp.status_code == 400

    def test_not_found_or_wrong_tenant_returns_404(self, client, auth_headers):
        service = _make_service(get_version_detail=None)
        with _patch_service(service):
            resp = client.get(
                f"/api/v1/dataset-versions/{VERSION_ID}", headers=auth_headers
            )
        assert resp.status_code == 404

    def test_returns_detail_with_presigned_coco(self, client, auth_headers):
        service = _make_service()
        with _patch_service(service):
            resp = client.get(
                f"/api/v1/dataset-versions/{VERSION_ID}", headers=auth_headers
            )
        assert resp.status_code == 200
        version = resp.get_json()["data"]["version"]
        assert version["id"] == VERSION_ID
        assert version["coco_files"]["train"]["url"].startswith("https://")
