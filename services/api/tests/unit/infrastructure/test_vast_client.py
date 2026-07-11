"""
Tests: infrastructure/gpu/vast_client.py — cliente REST Vast.ai (WS-A4).

Cobre:
- search_offers: query com GPUs alvo, price-cap (env VAST_PRICE_CAP default
  0.60), filtro client-side e ordenação por dph_total asc
- create_instance: PUT /asks/{id}/ com image/onstart, erro sem new_contract
- get_instance_status: unwrap de {"instances": {...}} e lista
- destroy_instance: DELETE; best-effort (retorna False, nunca levanta)
- _request: timeout sempre presente, chave via header, VastAIError em
  HTTP >= 400 e em RequestException
- resolve_vast_api_key: integration store do tenant → fallback env
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests as requests_lib

from app.infrastructure.gpu import vast_client
from app.infrastructure.gpu.vast_client import (
    VastAIClient,
    VastAIError,
    resolve_vast_api_key,
)

_TENANT = "99999999-8888-7777-6666-555555555555"


def _response(status_code: int = 200, payload: dict | None = None,
              text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload if payload is not None else {}
    resp.text = text or json.dumps(payload or {})
    return resp


@pytest.fixture
def client() -> VastAIClient:
    return VastAIClient("test-api-key")


class TestClientBasics:
    def test_missing_api_key_raises(self) -> None:
        with pytest.raises(VastAIError, match="ausente"):
            VastAIClient("")

    def test_request_sends_bearer_header_and_timeout(self, client) -> None:
        with patch.object(vast_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(200, {"ok": True})
            client._request("GET", "/bundles/")

        _, kwargs = mock_requests.request.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer test-api-key"
        assert kwargs["timeout"] == 30

    def test_http_error_raises_vast_error(self, client) -> None:
        with patch.object(vast_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(
                401, {"error": "unauthorized"}
            )
            with pytest.raises(VastAIError, match="HTTP 401"):
                client._request("GET", "/instances/1/")

    def test_network_error_raises_vast_error(self, client) -> None:
        with patch.object(vast_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.side_effect = requests_lib.RequestException("boom")
            with pytest.raises(VastAIError, match="falhou"):
                client._request("GET", "/bundles/")


class TestSearchOffers:
    def _offers_payload(self) -> dict:
        return {"offers": [
            {"id": 3, "dph_total": 0.55, "gpu_name": "RTX 4090"},
            {"id": 1, "dph_total": 0.25, "gpu_name": "RTX 3090"},
            {"id": 2, "dph_total": 0.90, "gpu_name": "RTX 4090"},  # acima do cap
        ]}

    def test_filters_by_price_cap_and_sorts_ascending(
        self, client, monkeypatch,
    ) -> None:
        monkeypatch.delenv("VAST_PRICE_CAP", raising=False)
        with patch.object(vast_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(
                200, self._offers_payload()
            )
            offers = client.search_offers()

        assert [o["id"] for o in offers] == [1, 3]  # 0.90 filtrada (cap 0.60)

    def test_price_cap_from_env(self, client, monkeypatch) -> None:
        monkeypatch.setenv("VAST_PRICE_CAP", "0.30")
        with patch.object(vast_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(
                200, self._offers_payload()
            )
            offers = client.search_offers()

        assert [o["id"] for o in offers] == [1]

    def test_query_targets_default_gpus(self, client, monkeypatch) -> None:
        monkeypatch.delenv("VAST_PRICE_CAP", raising=False)
        with patch.object(vast_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(200, {"offers": []})
            client.search_offers()

        _, kwargs = mock_requests.request.call_args
        query = json.loads(kwargs["params"]["q"])
        assert query["gpu_name"] == {"in": ["RTX 4090", "RTX 3090"]}
        assert query["rentable"] == {"eq": True}
        assert query["dph_total"] == {"lte": 0.60}

    def test_invalid_env_cap_falls_back_to_default(self, monkeypatch) -> None:
        monkeypatch.setenv("VAST_PRICE_CAP", "not-a-float")
        assert vast_client.get_price_cap() == 0.60


class TestCreateInstance:
    def test_puts_to_asks_with_image_and_onstart(self, client) -> None:
        with patch.object(vast_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(
                200, {"success": True, "new_contract": 4242}
            )
            data = client.create_instance(
                77, onstart="#!/bin/bash\necho oi", label="recognition-x"
            )

        assert data["new_contract"] == 4242
        args, kwargs = mock_requests.request.call_args
        assert args[0] == "PUT"
        assert args[1].endswith("/asks/77/")
        body = kwargs["json"]
        assert body["onstart"].startswith("#!/bin/bash")
        assert "pytorch" in body["image"]
        assert body["label"] == "recognition-x"

    def test_missing_new_contract_raises(self, client) -> None:
        with patch.object(vast_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(200, {"success": False})
            with pytest.raises(VastAIError, match="new_contract"):
                client.create_instance(77, onstart="x")


class TestInstanceStatus:
    def test_unwraps_instances_dict(self, client) -> None:
        with patch.object(vast_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(
                200, {"instances": {"id": 4242, "actual_status": "running"}}
            )
            status = client.get_instance_status(4242)
        assert status["actual_status"] == "running"

    def test_unwraps_instances_list(self, client) -> None:
        with patch.object(vast_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(
                200, {"instances": [{"id": 4242, "actual_status": "exited"}]}
            )
            status = client.get_instance_status(4242)
        assert status["actual_status"] == "exited"


class TestDestroyInstance:
    def test_sends_delete(self, client) -> None:
        with patch.object(vast_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(200, {"success": True})
            assert client.destroy_instance(4242) is True

        args, _ = mock_requests.request.call_args
        assert args[0] == "DELETE"
        assert args[1].endswith("/instances/4242/")

    def test_never_raises_on_error(self, client, caplog) -> None:
        """destroy é chamado em finally — falha loga e retorna False."""
        with patch.object(vast_client, "requests") as mock_requests:
            mock_requests.RequestException = requests_lib.RequestException
            mock_requests.request.return_value = _response(500, {}, text="boom")
            assert client.destroy_instance(4242) is False
        assert "vast_destroy_failed" in caplog.text


class TestResolveVastApiKey:
    def test_tenant_integration_wins_over_env(self, monkeypatch) -> None:
        monkeypatch.setenv("VAST_API_KEY", "env-key")
        with patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            return_value=MagicMock(),
        ), patch(
            "app.domain.services.integration_service.IntegrationService"
        ) as mock_svc_cls:
            mock_svc_cls.return_value.get_integration_secret.return_value = (
                "tenant-key"
            )
            assert resolve_vast_api_key(_TENANT) == "tenant-key"

    def test_falls_back_to_env_when_tenant_has_no_secret(self, monkeypatch) -> None:
        monkeypatch.setenv("VAST_API_KEY", "env-key")
        with patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            return_value=MagicMock(),
        ), patch(
            "app.domain.services.integration_service.IntegrationService"
        ) as mock_svc_cls:
            mock_svc_cls.return_value.get_integration_secret.return_value = ""
            assert resolve_vast_api_key(_TENANT) == "env-key"

    def test_falls_back_to_env_on_lookup_error(self, monkeypatch) -> None:
        monkeypatch.setenv("VAST_API_KEY", "env-key")
        with patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            side_effect=RuntimeError("db down"),
        ):
            assert resolve_vast_api_key(_TENANT) == "env-key"

    def test_no_tenant_uses_env(self, monkeypatch) -> None:
        monkeypatch.setenv("VAST_API_KEY", "env-key")
        assert resolve_vast_api_key(None) == "env-key"

    def test_empty_everywhere_returns_empty(self, monkeypatch) -> None:
        monkeypatch.delenv("VAST_API_KEY", raising=False)
        with patch(
            "app.infrastructure.database.connection.DatabasePool.get_instance",
            return_value=None,
        ):
            assert resolve_vast_api_key(_TENANT) == ""
