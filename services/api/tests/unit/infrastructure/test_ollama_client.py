"""
Tests: OllamaClient — is_available, embed, generate_stream, generate,
get_ollama_client factory.

requests is already installed; we patch at the module level
("app.infrastructure.ollama_client.requests") to avoid real network calls.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.infrastructure.ollama_client import OllamaClient, get_ollama_client

_REQ = "app.infrastructure.ollama_client.requests"
_BASE = "http://ollama.test:11434"


def _client(**kwargs) -> OllamaClient:
    return OllamaClient(
        base_url=kwargs.get("base_url", _BASE),
        model=kwargs.get("model", "epi-assistant"),
        embed_model=kwargs.get("embed_model", "nomic-embed-text"),
    )


def _mock_response(status_code=200, json_data=None, raise_for=None):
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

    def test_trailing_slash_stripped(self):
        c = OllamaClient("http://host:11434/", "m", "e")
        assert not c.base_url.endswith("/")

    def test_attributes_stored(self):
        c = OllamaClient(_BASE, "my-model", "my-embed")
        assert c.model == "my-model"
        assert c.embed_model == "my-embed"


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------

class TestIsAvailable:

    def test_returns_true_on_200(self):
        with patch(f"{_REQ}.get", return_value=_mock_response(200)):
            assert _client().is_available() is True

    def test_returns_false_on_non_200(self):
        with patch(f"{_REQ}.get", return_value=_mock_response(503)):
            assert _client().is_available() is False

    def test_returns_false_on_exception(self):
        with patch(f"{_REQ}.get", side_effect=Exception("conn refused")):
            assert _client().is_available() is False

    def test_calls_api_tags_endpoint(self):
        with patch(f"{_REQ}.get", return_value=_mock_response()) as mock_get:
            _client().is_available()
        url = mock_get.call_args[0][0]
        assert "/api/tags" in url


# ---------------------------------------------------------------------------
# embed
# ---------------------------------------------------------------------------

class TestEmbed:

    def test_returns_embedding_list(self):
        embedding = [0.1, 0.2, 0.3]
        resp = _mock_response(json_data={"embedding": embedding})
        with patch(f"{_REQ}.post", return_value=resp):
            result = _client().embed("hello world")
        assert result == embedding

    def test_calls_api_embeddings_endpoint(self):
        resp = _mock_response(json_data={"embedding": []})
        with patch(f"{_REQ}.post", return_value=resp) as mock_post:
            _client().embed("text")
        url = mock_post.call_args[0][0]
        assert "/api/embeddings" in url

    def test_uses_embed_model(self):
        resp = _mock_response(json_data={"embedding": []})
        with patch(f"{_REQ}.post", return_value=resp) as mock_post:
            _client(embed_model="my-embed").embed("text")
        body = mock_post.call_args[1]["json"]
        assert body["model"] == "my-embed"

    def test_raises_on_http_error(self):
        import requests as _r
        resp = _mock_response(raise_for=_r.HTTPError("503"))
        with patch(f"{_REQ}.post", return_value=resp), \
             patch(f"{_REQ}.HTTPError", _r.HTTPError):
            with pytest.raises(_r.HTTPError):
                _client().embed("text")


# ---------------------------------------------------------------------------
# generate (synchronous)
# ---------------------------------------------------------------------------

class TestGenerate:

    def test_returns_response_text(self):
        resp = _mock_response(json_data={"response": "hello from llm"})
        with patch(f"{_REQ}.post", return_value=resp):
            result = _client().generate("Say hello")
        assert result == "hello from llm"

    def test_empty_response_key_returns_empty_string(self):
        resp = _mock_response(json_data={})
        with patch(f"{_REQ}.post", return_value=resp):
            result = _client().generate("prompt")
        assert result == ""

    def test_uses_main_model(self):
        resp = _mock_response(json_data={"response": "ok"})
        with patch(f"{_REQ}.post", return_value=resp) as mock_post:
            _client(model="my-model").generate("q")
        body = mock_post.call_args[1]["json"]
        assert body["model"] == "my-model"
        assert body["stream"] is False

    def test_calls_api_generate_endpoint(self):
        resp = _mock_response(json_data={"response": ""})
        with patch(f"{_REQ}.post", return_value=resp) as mock_post:
            _client().generate("q")
        url = mock_post.call_args[0][0]
        assert "/api/generate" in url


# ---------------------------------------------------------------------------
# generate_stream
# ---------------------------------------------------------------------------

class TestGenerateStream:

    def _streaming_resp(self, lines):
        """Build a mock streaming response that acts as context manager."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.iter_lines.return_value = [
            json.dumps(line).encode() for line in lines
        ]
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_yields_tokens(self):
        lines = [
            {"response": "hello", "done": False},
            {"response": " world", "done": True},
        ]
        resp = self._streaming_resp(lines)
        with patch(f"{_REQ}.post", return_value=resp):
            tokens = list(_client().generate_stream("prompt"))
        assert tokens == ["hello", " world"]

    def test_done_true_stops_iteration(self):
        lines = [
            {"response": "first", "done": False},
            {"response": "last", "done": True},
            {"response": "ignored", "done": False},  # should not be yielded
        ]
        resp = self._streaming_resp(lines)
        with patch(f"{_REQ}.post", return_value=resp):
            tokens = list(_client().generate_stream("p"))
        assert "ignored" not in tokens

    def test_empty_response_token_not_yielded(self):
        lines = [
            {"response": "", "done": False},
            {"response": "real", "done": True},
        ]
        resp = self._streaming_resp(lines)
        with patch(f"{_REQ}.post", return_value=resp):
            tokens = list(_client().generate_stream("p"))
        assert tokens == ["real"]

    def test_invalid_json_line_skipped(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.iter_lines.return_value = [
            b"not-valid-json",
            json.dumps({"response": "ok", "done": True}).encode(),
        ]
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch(f"{_REQ}.post", return_value=mock_resp):
            tokens = list(_client().generate_stream("p"))
        assert tokens == ["ok"]

    def test_empty_line_skipped(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.iter_lines.return_value = [
            b"",
            json.dumps({"response": "data", "done": True}).encode(),
        ]
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch(f"{_REQ}.post", return_value=mock_resp):
            tokens = list(_client().generate_stream("p"))
        assert tokens == ["data"]

    def test_uses_stream_true(self):
        resp = self._streaming_resp([{"response": "x", "done": True}])
        with patch(f"{_REQ}.post", return_value=resp) as mock_post:
            list(_client().generate_stream("q"))
        body = mock_post.call_args[1]["json"]
        assert body["stream"] is True


# ---------------------------------------------------------------------------
# get_ollama_client factory
# ---------------------------------------------------------------------------

class TestGetOllamaClient:

    def test_returns_client_instance(self):
        result = get_ollama_client()
        assert isinstance(result, OllamaClient)

    def test_uses_env_vars(self):
        with patch("os.environ.get", side_effect=lambda k, d="": {
            "OLLAMA_BASE_URL": "http://custom:11434",
            "OLLAMA_MODEL": "custom-model",
            "OLLAMA_EMBED_MODEL": "custom-embed",
        }.get(k, d)):
            c = get_ollama_client()
        assert "custom" in c.base_url
        assert c.model == "custom-model"
        assert c.embed_model == "custom-embed"

    def test_defaults_when_env_absent(self):
        with patch.dict("os.environ", {}, clear=True):
            c = get_ollama_client()
        assert "11434" in c.base_url
