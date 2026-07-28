"""Tests for ota.client.fetch_target_ref: request shape, envelope parsing, errors."""

from unittest.mock import MagicMock

import pytest

from app.ota.client import TargetFetchError, fetch_target_ref


def _response(status_code, data=None):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = {"data": data} if data is not None else {}
    return r


def _token_source(bearer="tok-1"):
    ts = MagicMock()
    ts.get_bearer.return_value = bearer
    return ts


def test_fetch_target_ref_returns_ref_from_envelope():
    http = MagicMock()
    http.get.return_value = _response(200, {"target_ref": "abc123", "channel": "dev"})

    ref = fetch_target_ref(http, "http://cloud.test", _token_source())

    assert ref == "abc123"


def test_fetch_target_ref_sends_bearer_and_channel_param():
    http = MagicMock()
    http.get.return_value = _response(200, {"target_ref": "abc123"})
    ts = _token_source(bearer="fresh-tok")

    fetch_target_ref(http, "http://cloud.test", ts, channel="dev")

    args, kwargs = http.get.call_args
    assert args[0] == "http://cloud.test/api/v1/edge/software/target"
    assert kwargs["params"] == {"channel": "dev"}
    assert kwargs["headers"]["Authorization"] == "Bearer fresh-tok"


def test_fetch_target_ref_omits_channel_param_when_not_given():
    http = MagicMock()
    http.get.return_value = _response(200, {"target_ref": "abc123"})

    fetch_target_ref(http, "http://cloud.test", _token_source())

    _, kwargs = http.get.call_args
    assert kwargs["params"] is None


def test_fetch_target_ref_raises_on_non_200():
    http = MagicMock()
    http.get.return_value = _response(401)

    with pytest.raises(TargetFetchError, match="401"):
        fetch_target_ref(http, "http://cloud.test", _token_source())


def test_fetch_target_ref_raises_when_target_ref_missing():
    http = MagicMock()
    http.get.return_value = _response(200, {"channel": "dev"})

    with pytest.raises(TargetFetchError, match="target_ref"):
        fetch_target_ref(http, "http://cloud.test", _token_source())


def test_fetch_target_ref_raises_on_network_error():
    http = MagicMock()
    http.get.side_effect = ConnectionError("boom")

    with pytest.raises(TargetFetchError, match="rede"):
        fetch_target_ref(http, "http://cloud.test", _token_source())
