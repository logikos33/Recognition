"""
Tests: infrastructure/gpu/runpod_client.py — cliente REST/GraphQL RunPod
(substitui vast_client.py).

Cobre:
- create_pod: POST /pods com imagem/env/dockerStartCmd, erro sem `id`
- get_pod: GET /pods/{id}
- list_pods: unwrap de lista crua e de {"pods": [...]}/{"data": [...]}
- terminate_pod: DELETE; best-effort (retorna False, nunca levanta)
- get_gpu_price: GraphQL gpuTypes.lowestPrice.uninterruptablePrice; erro
  sem gpu_type/sem preço
- get_billing: GET /billing/pods; filtro client-side por pod_id
- _request/_graphql: timeout sempre presente, chave via header, RunPodError
  em HTTP >= 400 e em RequestException
- resolve_runpod_api_key: integration store do tenant → fallback env
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests as requests_lib

from app.infrastructure.gpu import runpod_client
from app.infrastructure.gpu.runpod_client import (
    RunPodClient,
    RunPodError,
    resolve_runpod_api_key,
)

_TENANT = "99999999-8888-7777-6666-555555555555"


def _response(status_code: int = 200, payload: dict | list | None = None,
              text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = b"x"
    resp.json.return_value = payload if payload is not None else {}
    resp.text = text or str(payload or {})
    return resp


@pytest.fixture
def client() -> RunPodClient:
    return RunPodClient("test-api-key")


class TestClientBasics:
    def test_missing_api_key_raises(self) -> None:
        with pytest.raises(RunPodError, match="ausente"):
            RunPodClient("")

    def test_request_sends_bearer_header_and_timeout(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(200, {"ok": True})
            client._request("GET", "/pods")

        _, kwargs = mock_requests.request.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer test-api-key"
        assert kwargs["timeout"] == 30

    def test_http_error_raises_runpod_error(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(401, {"error": "unauthorized"})
            with pytest.raises(RunPodError, match="HTTP 401"):
                client._request("GET", "/pods/1")

    def test_network_error_raises_runpod_error(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.side_effect = requests_lib.RequestException("boom")
            with pytest.raises(RunPodError, match="falhou"):
                client._request("GET", "/pods")

    def test_empty_body_returns_empty_dict(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            resp = MagicMock(status_code=204, content=b"")
            mock_requests.request.return_value = resp
            assert client._request("DELETE", "/pods/1") == {}


class TestCreatePod:
    def test_posts_to_pods_with_image_env_and_start_cmd(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(200, {"id": "pod-42"})
            data = client.create_pod(
                name="recognition-train-abcd1234",
                image="runpod/pytorch:2.4.0",
                gpu_type_id="NVIDIA GeForce RTX 4090",
                env={"FOO": "bar"},
                docker_start_cmd=["/bin/bash", "-c", "echo oi"],
            )

        assert data["id"] == "pod-42"
        args, kwargs = mock_requests.request.call_args
        assert args[0] == "POST"
        assert args[1].endswith("/pods")
        body = kwargs["json"]
        assert body["imageName"] == "runpod/pytorch:2.4.0"
        assert body["gpuTypeIds"] == ["NVIDIA GeForce RTX 4090"]
        assert body["env"] == {"FOO": "bar"}
        assert body["dockerStartCmd"] == ["/bin/bash", "-c", "echo oi"]

    def test_missing_id_raises(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(200, {"success": False})
            with pytest.raises(RunPodError, match="sem id"):
                client.create_pod(
                    name="x", image="img", gpu_type_id="gpu",
                    env={}, docker_start_cmd=["true"],
                )


class TestGetAndListPods:
    def test_get_pod_returns_dict(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(
                200, {"id": "pod-1", "desiredStatus": "RUNNING"}
            )
            pod = client.get_pod("pod-1")
        assert pod["desiredStatus"] == "RUNNING"

    def test_list_pods_unwraps_raw_list(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(200, [{"id": "pod-1"}])
            pods = client.list_pods()
        assert pods == [{"id": "pod-1"}]

    def test_list_pods_unwraps_pods_key(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(200, {"pods": [{"id": "pod-2"}]})
            pods = client.list_pods()
        assert pods == [{"id": "pod-2"}]


class TestTerminatePod:
    def test_sends_delete(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            resp = MagicMock(status_code=200, content=b"")
            mock_requests.request.return_value = resp
            assert client.terminate_pod("pod-1") is True

        args, _ = mock_requests.request.call_args
        assert args[0] == "DELETE"
        assert args[1].endswith("/pods/pod-1")

    def test_never_raises_on_error(self, client, caplog) -> None:
        """terminate é chamado em finally/reconciler — falha loga e retorna False."""
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(500, {}, text="boom")
            assert client.terminate_pod("pod-1") is False
        assert "runpod_terminate_failed" in caplog.text


class TestGetGpuPrice:
    def test_returns_lowest_uninterruptable_price(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.post.return_value = _response(200, {
                "data": {
                    "gpuTypes": [
                        {"id": "NVIDIA GeForce RTX 4090",
                         "lowestPrice": {"uninterruptablePrice": 0.44}},
                    ]
                }
            })
            price = client.get_gpu_price("NVIDIA GeForce RTX 4090")
        assert price == 0.44

    def test_unknown_gpu_type_raises(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.post.return_value = _response(200, {"data": {"gpuTypes": []}})
            with pytest.raises(RunPodError, match="desconhecido"):
                client.get_gpu_price("GPU inexistente")

    def test_missing_price_raises(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.post.return_value = _response(200, {
                "data": {"gpuTypes": [{"id": "x", "lowestPrice": {}}]}
            })
            with pytest.raises(RunPodError, match="não retornou preço"):
                client.get_gpu_price("x")

    def test_graphql_errors_field_raises(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.post.return_value = _response(200, {
                "errors": [{"message": "bad query"}]
            })
            with pytest.raises(RunPodError, match="erros"):
                client.get_gpu_price("x")


class TestGetBilling:
    def test_filters_by_pod_id(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(200, {
                "data": [
                    {"podId": "pod-1", "amount": 0.1},
                    {"podId": "pod-2", "amount": 0.2},
                    {"podId": "pod-1", "amount": 0.05},
                ]
            })
            records = client.get_billing(pod_id="pod-1")
        assert records == [{"podId": "pod-1", "amount": 0.1}, {"podId": "pod-1", "amount": 0.05}]

    def test_no_pod_id_returns_all(self, client) -> None:
        with patch.object(runpod_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(
                200, {"data": [{"podId": "pod-1", "amount": 0.1}]}
            )
            records = client.get_billing()
        assert len(records) == 1


class TestResolveRunpodApiKey:
    def test_tenant_integration_wins_over_env(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_API_KEY", "env-key")
        with patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            return_value=MagicMock(),
        ), patch(
            "app.domain.services.integration_service.IntegrationService"
        ) as mock_svc_cls:
            mock_svc_cls.return_value.get_integration_secret.return_value = "tenant-key"
            assert resolve_runpod_api_key(_TENANT) == "tenant-key"

    def test_falls_back_to_env_when_tenant_has_no_secret(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_API_KEY", "env-key")
        with patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            return_value=MagicMock(),
        ), patch(
            "app.domain.services.integration_service.IntegrationService"
        ) as mock_svc_cls:
            mock_svc_cls.return_value.get_integration_secret.return_value = ""
            assert resolve_runpod_api_key(_TENANT) == "env-key"

    def test_falls_back_to_env_on_lookup_error(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_API_KEY", "env-key")
        with patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            side_effect=RuntimeError("db down"),
        ):
            assert resolve_runpod_api_key(_TENANT) == "env-key"

    def test_no_tenant_uses_env(self, monkeypatch) -> None:
        monkeypatch.setenv("RUNPOD_API_KEY", "env-key")
        assert resolve_runpod_api_key(None) == "env-key"

    def test_empty_everywhere_returns_empty(self, monkeypatch) -> None:
        monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
        with patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            return_value=None,
        ):
            assert resolve_runpod_api_key(_TENANT) == ""
