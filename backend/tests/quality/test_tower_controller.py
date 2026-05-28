"""
Testes unitarios para TowerController e implementacoes.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from app.api.v1.quality.tower_controller import (
    HTTPRelayTowerController,
    SimulatedTowerController,
    get_tower_controller,
)


STATION = "BANCADA_A"


@pytest.fixture
def simulated():
    return SimulatedTowerController()


def test_simulated_set_green_does_not_raise(simulated):
    """SimulatedTowerController.set_green nao deve levantar excecao."""
    simulated.set_green(STATION)  # deve completar sem erro


def test_simulated_set_red_does_not_raise(simulated):
    """SimulatedTowerController.set_red nao deve levantar excecao."""
    simulated.set_red(STATION)


def test_simulated_set_idle_does_not_raise(simulated):
    """SimulatedTowerController.set_idle nao deve levantar excecao."""
    simulated.set_idle(STATION)


def test_http_relay_calls_requests_on_set_green():
    """HTTPRelayTowerController.set_green deve chamar requests.get com URL verde."""
    mock_requests = MagicMock()
    mock_requests.get.return_value = MagicMock(status_code=200)

    with patch.dict(os.environ, {
        "TOWER_HTTP_GREEN_URL": "http://relay.local/green/on",
        "TOWER_HTTP_RED_URL": "http://relay.local/red/on",
        "TOWER_HTTP_OFF_GREEN_URL": "http://relay.local/green/off",
        "TOWER_HTTP_OFF_RED_URL": "http://relay.local/red/off",
    }):
        controller = HTTPRelayTowerController()
        with patch.dict("sys.modules", {"requests": mock_requests}):
            controller.set_green(STATION)

    # set_green aciona red_off + green_on (2 chamadas)
    assert mock_requests.get.call_count >= 1
    called_urls = [str(c) for c in mock_requests.get.call_args_list]
    assert any("green" in url.lower() for url in called_urls)


def test_get_tower_controller_returns_simulated_by_default():
    """get_tower_controller sem env var deve retornar SimulatedTowerController."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("TOWER_CONTROLLER_TYPE", None)
        controller = get_tower_controller()
    assert isinstance(controller, SimulatedTowerController)


def test_get_tower_controller_simulated_when_env_is_simulated():
    """TOWER_CONTROLLER_TYPE=simulated deve retornar SimulatedTowerController."""
    with patch.dict(os.environ, {"TOWER_CONTROLLER_TYPE": "simulated"}):
        controller = get_tower_controller()
    assert isinstance(controller, SimulatedTowerController)


def test_get_tower_controller_http_relay_when_env_is_http_relay():
    """TOWER_CONTROLLER_TYPE=http_relay deve retornar HTTPRelayTowerController."""
    with patch.dict(os.environ, {"TOWER_CONTROLLER_TYPE": "http_relay"}):
        controller = get_tower_controller()
    assert isinstance(controller, HTTPRelayTowerController)
