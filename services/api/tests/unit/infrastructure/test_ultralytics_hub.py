"""
Tests: UltralyticsHubClient — all HTTP methods + high-level operations.

All network calls are patched via requests.*; no real HTTP made.
"""
import sys
from unittest.mock import MagicMock, mock_open, patch

import pytest

# requests is imported at module level in ultralytics_hub
_requests_mock = MagicMock()
sys.modules.setdefault("requests", _requests_mock)

from app.infrastructure.hub.ultralytics_hub import (  # noqa: E402
    TrainingError,
    UltralyticsHubClient,
)

_REQ = "app.infrastructure.hub.ultralytics_hub.requests"


def _client(key: str = "test-api-key") -> UltralyticsHubClient:
    return UltralyticsHubClient(key)


def _mock_response(json_data=None, status_code=200, raise_for=None):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_data or {}
    if raise_for:
        r.raise_for_status.side_effect = raise_for
    else:
        r.raise_for_status.return_value = None
    return r


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_empty_key_raises_value_error(self):
        with pytest.raises(ValueError, match="ULTRALYTICS_HUB_API_KEY"):
            UltralyticsHubClient("")

    def test_valid_key_sets_auth_header(self):
        c = _client("my-secret")
        assert "Authorization" in c._auth
        assert "my-secret" in c._auth["Authorization"]


# ---------------------------------------------------------------------------
# _get
# ---------------------------------------------------------------------------

class TestGetPrimitive:
    def test_returns_parsed_json(self):
        resp = _mock_response({"data": {"id": "m1"}})
        with patch(f"{_REQ}.get", return_value=resp):
            result = _client()._get("/models/m1")
        assert result["data"]["id"] == "m1"

    def test_http_error_raises_training_error(self):
        import requests as _r
        http_err = _r.HTTPError("404")
        http_err.response = MagicMock(status_code=404)
        resp = _mock_response(raise_for=http_err)
        with patch(f"{_REQ}.get", return_value=resp), \
             patch(f"{_REQ}.HTTPError", _r.HTTPError):
            with pytest.raises(TrainingError) as exc_info:
                _client()._get("/models/missing")
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# _post_json
# ---------------------------------------------------------------------------

class TestPostJson:
    def test_returns_parsed_json(self):
        resp = _mock_response({"data": {"id": "ds1"}})
        with patch(f"{_REQ}.post", return_value=resp):
            result = _client()._post_json("/datasets", {"meta": {"name": "test"}})
        assert result["data"]["id"] == "ds1"

    def test_http_error_raises_training_error(self):
        import requests as _r
        http_err = _r.HTTPError("500")
        http_err.response = MagicMock(status_code=500)
        resp = _mock_response(raise_for=http_err)
        with patch(f"{_REQ}.post", return_value=resp), \
             patch(f"{_REQ}.HTTPError", _r.HTTPError):
            with pytest.raises(TrainingError):
                _client()._post_json("/datasets", {})


# ---------------------------------------------------------------------------
# _post_file
# ---------------------------------------------------------------------------

class TestPostFile:
    def test_posts_file_and_returns_json(self):
        resp = _mock_response({"ok": True})
        with patch(f"{_REQ}.post", return_value=resp), \
             patch("builtins.open", mock_open(read_data=b"zip_data")):
            result = _client()._post_file("/datasets/ds1/upload", "/tmp/data.zip")
        assert result["ok"] is True

    def test_http_error_raises_training_error(self):
        import requests as _r
        http_err = _r.HTTPError("413")
        http_err.response = MagicMock(status_code=413)
        resp = _mock_response(raise_for=http_err)
        with patch(f"{_REQ}.post", return_value=resp), \
             patch("builtins.open", mock_open(read_data=b"zip")), \
             patch(f"{_REQ}.HTTPError", _r.HTTPError):
            with pytest.raises(TrainingError):
                _client()._post_file("/datasets/ds1/upload", "/tmp/data.zip")


# ---------------------------------------------------------------------------
# _delete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_returns_true_on_200(self):
        with patch(f"{_REQ}.delete", return_value=MagicMock(status_code=200)):
            assert _client()._delete("/models/m1/deploy") is True

    def test_returns_true_on_204(self):
        with patch(f"{_REQ}.delete", return_value=MagicMock(status_code=204)):
            assert _client()._delete("/models/m1/deploy") is True

    def test_returns_false_on_other_status(self):
        with patch(f"{_REQ}.delete", return_value=MagicMock(status_code=404)):
            assert _client()._delete("/models/m1/deploy") is False

    def test_exception_swallowed_returns_false(self):
        with patch(f"{_REQ}.delete", side_effect=Exception("conn refused")):
            assert _client()._delete("/models/m1/deploy") is False


# ---------------------------------------------------------------------------
# upload_dataset
# ---------------------------------------------------------------------------

class TestUploadDataset:
    def test_returns_dataset_id(self):
        c = _client()
        create_resp = _mock_response({"data": {"id": "ds-abc"}})
        upload_resp = _mock_response({})
        with patch.object(c, "_post_json", return_value=create_resp.json()), \
             patch.object(c, "_post_file", return_value=upload_resp.json()), \
             patch("os.path.getsize", return_value=1024):
            result = c.upload_dataset("/tmp/dataset.zip", "MyDataset")
        assert result == "ds-abc"

    def test_calls_create_then_upload(self):
        c = _client()
        with patch.object(c, "_post_json", return_value={"data": {"id": "ds-xyz"}}) as mock_json, \
             patch.object(c, "_post_file", return_value={}) as mock_file, \
             patch("os.path.getsize", return_value=0):
            c.upload_dataset("/tmp/d.zip", "D")
        mock_json.assert_called_once()
        mock_file.assert_called_once()
        file_path_arg = mock_file.call_args[0][1]
        assert file_path_arg == "/tmp/d.zip"


# ---------------------------------------------------------------------------
# create_model
# ---------------------------------------------------------------------------

class TestCreateModel:
    def test_returns_model_id(self):
        c = _client()
        with patch.object(c, "_post_json", return_value={"data": {"id": "model-99"}}):
            result = c.create_model("My Model", "ds-1", "yolov8n", 100, 640, 16)
        assert result == "model-99"


# ---------------------------------------------------------------------------
# start_training
# ---------------------------------------------------------------------------

class TestStartTraining:
    def test_calls_deploy_endpoint(self):
        c = _client()
        with patch.object(c, "_post_json", return_value={}) as mock_post:
            c.start_training("model-1")
        path = mock_post.call_args[0][0]
        assert "model-1" in path
        assert "deploy" in path


# ---------------------------------------------------------------------------
# get_model_status
# ---------------------------------------------------------------------------

class TestGetModelStatus:

    def _call(self, m_data):
        c = _client()
        with patch.object(c, "_get", return_value={"data": m_data}):
            return c.get_model_status("model-1")

    def test_training_status_maps_to_running(self):
        result = self._call({"status": "training", "epoch": 25, "trainArgs": {"epochs": 100}})
        assert result["status"] == "running"
        assert result["progress"] == 25

    def test_trained_status_maps_to_completed_100(self):
        result = self._call({"status": "trained"})
        assert result["status"] == "completed"
        assert result["progress"] == 100

    def test_failed_status_maps_to_failed_0(self):
        result = self._call({"status": "failed"})
        assert result["status"] == "failed"
        assert result["progress"] == 0

    def test_stopped_maps_to_failed(self):
        result = self._call({"status": "stopped"})
        assert result["status"] == "failed"

    def test_queued_maps_to_pending(self):
        result = self._call({"status": "queued"})
        assert result["status"] == "pending"

    def test_unknown_status_defaults_to_running(self):
        result = self._call({"status": "some_new_status"})
        assert result["status"] == "running"

    def test_metrics_extracted_correctly(self):
        result = self._call({
            "status": "trained",
            "metrics": {"mAP50": 0.9, "precision": 0.88, "recall": 0.85, "loss": 0.05},
        })
        assert result["metrics"]["mAP50"] == 0.9
        assert result["metrics"]["precision"] == 0.88

    def test_metrics_alt_keys_fallback(self):
        result = self._call({
            "status": "trained",
            "metrics": {"map50": 0.75, "p": 0.80, "r": 0.70, "box_loss": 0.12},
        })
        assert result["metrics"]["mAP50"] == 0.75
        assert result["metrics"]["precision"] == 0.80

    def test_weights_url_extracted(self):
        result = self._call({"status": "trained", "weightsUrl": "https://hub.example/best.pt"})
        assert result["weights_url"] == "https://hub.example/best.pt"

    def test_progress_capped_at_99_while_running(self):
        result = self._call({"status": "training", "epoch": 101, "trainArgs": {"epochs": 100}})
        assert result["progress"] == 99


# ---------------------------------------------------------------------------
# cancel_training
# ---------------------------------------------------------------------------

class TestCancelTraining:
    def test_cancel_returns_true_on_success(self):
        c = _client()
        with patch.object(c, "_delete", return_value=True):
            assert c.cancel_training("model-1") is True

    def test_cancel_returns_false_on_failure(self):
        c = _client()
        with patch.object(c, "_delete", return_value=False):
            assert c.cancel_training("model-1") is False


# ---------------------------------------------------------------------------
# download_weights
# ---------------------------------------------------------------------------

class TestDownloadWeights:
    def test_no_weights_url_raises_training_error(self):
        c = _client()
        with patch.object(c, "get_model_status", return_value={"weights_url": None}):
            with pytest.raises(TrainingError, match="Sem URL"):
                c.download_weights("model-1", "/tmp/best.pt")

    def test_downloads_and_writes_file(self):
        c = _client()
        chunk = b"model_data"
        mock_resp = MagicMock()
        mock_resp.iter_content.return_value = [chunk]
        mock_resp.raise_for_status.return_value = None

        with patch.object(c, "get_model_status",
                          return_value={"weights_url": "https://hub.example/best.pt"}), \
             patch(f"{_REQ}.get", return_value=mock_resp), \
             patch("builtins.open", mock_open()) as m_open:
            result = c.download_weights("model-1", "/tmp/best.pt")

        assert result == "/tmp/best.pt"
        m_open().write.assert_called_once_with(chunk)
