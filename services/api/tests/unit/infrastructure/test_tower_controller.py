"""Tests: tower_controller.py — SimulatedTowerController, GPIOTowerController,
HTTPRelayTowerController, get_tower_controller factory."""
import sys
from unittest.mock import MagicMock, call, patch


from app.api.v1.quality.tower_controller import (
    HTTPRelayTowerController,
    SimulatedTowerController,
    get_tower_controller,
)


# ---------------------------------------------------------------------------
# SimulatedTowerController
# ---------------------------------------------------------------------------

class TestSimulatedTowerController:

    def test_set_green_does_not_raise(self):
        ctrl = SimulatedTowerController()
        ctrl.set_green("bancada-1")

    def test_set_red_does_not_raise(self):
        ctrl = SimulatedTowerController()
        ctrl.set_red("bancada-1")

    def test_set_idle_does_not_raise(self):
        ctrl = SimulatedTowerController()
        ctrl.set_idle("bancada-1")

    def test_blink_red_does_not_raise(self):
        ctrl = SimulatedTowerController()
        ctrl.blink_red("bancada-1", times=2)

    def test_set_green_logs_station(self, caplog):
        import logging
        ctrl = SimulatedTowerController()
        with caplog.at_level(logging.INFO):
            ctrl.set_green("ST-42")
        assert "ST-42" in caplog.text

    def test_set_red_logs_station(self, caplog):
        import logging
        ctrl = SimulatedTowerController()
        with caplog.at_level(logging.INFO):
            ctrl.set_red("ST-42")
        assert "ST-42" in caplog.text

    def test_set_idle_logs_station(self, caplog):
        import logging
        ctrl = SimulatedTowerController()
        with caplog.at_level(logging.INFO):
            ctrl.set_idle("ST-42")
        assert "ST-42" in caplog.text

    def test_blink_red_logs_station(self, caplog):
        import logging
        ctrl = SimulatedTowerController()
        with caplog.at_level(logging.INFO):
            ctrl.blink_red("ST-42", times=1)
        assert "ST-42" in caplog.text


# ---------------------------------------------------------------------------
# GPIOTowerController — RPi.GPIO unavailable (default on non-Pi hardware)
# ---------------------------------------------------------------------------

class TestGPIOTowerControllerNoGPIO:

    def _make(self):
        from app.api.v1.quality.tower_controller import GPIOTowerController
        return GPIOTowerController()

    def test_init_sets_gpio_none_when_rpi_unavailable(self):
        ctrl = self._make()
        assert ctrl._gpio is None

    def test_set_green_does_not_raise_without_gpio(self):
        ctrl = self._make()
        ctrl.set_green("S1")

    def test_set_red_does_not_raise_without_gpio(self):
        ctrl = self._make()
        ctrl.set_red("S1")

    def test_set_idle_does_not_raise_without_gpio(self):
        ctrl = self._make()
        ctrl.set_idle("S1")

    def test_blink_red_does_not_raise_without_gpio(self):
        ctrl = self._make()
        with patch("time.sleep"):
            ctrl.blink_red("S1", times=1)

    def test_default_pins_are_17_and_27(self):
        ctrl = self._make()
        assert ctrl.green_pin == 17
        assert ctrl.red_pin == 27

    def test_env_override_changes_pins(self, monkeypatch):
        monkeypatch.setenv("TOWER_GPIO_GREEN_PIN", "22")
        monkeypatch.setenv("TOWER_GPIO_RED_PIN", "23")
        ctrl = self._make()
        assert ctrl.green_pin == 22
        assert ctrl.red_pin == 23


# ---------------------------------------------------------------------------
# GPIOTowerController — RPi.GPIO mocked (simulates Raspberry Pi)
# ---------------------------------------------------------------------------

class TestGPIOTowerControllerWithGPIO:

    def _make_with_mock_gpio(self):
        mock_gpio = MagicMock()
        mock_gpio.BCM = "BCM"
        mock_gpio.OUT = "OUT"
        mock_gpio.HIGH = 1
        mock_gpio.LOW = 0

        from app.api.v1.quality.tower_controller import GPIOTowerController
        ctrl = GPIOTowerController()
        # RPi.GPIO is unavailable on this machine; inject mock directly
        ctrl._gpio = mock_gpio
        return ctrl, mock_gpio

    def test_set_green_calls_output_twice(self):
        ctrl, gpio = self._make_with_mock_gpio()
        ctrl.set_green("S1")
        assert gpio.output.call_count == 2

    def test_set_green_turns_off_red_then_on_green(self):
        ctrl, gpio = self._make_with_mock_gpio()
        ctrl.set_green("S1")
        calls = gpio.output.call_args_list
        assert calls[0] == call(ctrl.red_pin, gpio.LOW)
        assert calls[1] == call(ctrl.green_pin, gpio.HIGH)

    def test_set_red_turns_off_green_then_on_red(self):
        ctrl, gpio = self._make_with_mock_gpio()
        ctrl.set_red("S1")
        calls = gpio.output.call_args_list
        assert calls[0] == call(ctrl.green_pin, gpio.LOW)
        assert calls[1] == call(ctrl.red_pin, gpio.HIGH)

    def test_set_idle_turns_off_both(self):
        ctrl, gpio = self._make_with_mock_gpio()
        ctrl.set_idle("S1")
        calls = gpio.output.call_args_list
        assert calls[0] == call(ctrl.green_pin, gpio.LOW)
        assert calls[1] == call(ctrl.red_pin, gpio.LOW)

    def test_blink_red_calls_set_red_and_idle_n_times(self):
        ctrl, gpio = self._make_with_mock_gpio()
        with patch("time.sleep"):
            ctrl.blink_red("S1", times=2)
        # 2 blinks × (set_red=2 outputs + set_idle=2 outputs) = 8 output calls
        assert gpio.output.call_count == 8


# ---------------------------------------------------------------------------
# HTTPRelayTowerController
# ---------------------------------------------------------------------------

class TestHTTPRelayTowerControllerGet:

    def test_get_skips_empty_url(self):
        ctrl = HTTPRelayTowerController()
        mock_requests = MagicMock()
        with patch.dict(sys.modules, {"requests": mock_requests}):
            ctrl._get("")
        mock_requests.get.assert_not_called()

    def test_get_calls_requests_with_url_and_timeout(self):
        ctrl = HTTPRelayTowerController()
        mock_requests = MagicMock()
        with patch.dict(sys.modules, {"requests": mock_requests}):
            ctrl._get("http://relay.local/on", timeout=2.0)
        mock_requests.get.assert_called_once_with("http://relay.local/on", timeout=2.0)

    def test_get_swallows_request_exception(self):
        ctrl = HTTPRelayTowerController()
        mock_requests = MagicMock()
        mock_requests.get.side_effect = Exception("connection refused")
        with patch.dict(sys.modules, {"requests": mock_requests}):
            ctrl._get("http://relay.local/on")  # must not raise

    def test_get_default_timeout_is_one_second(self):
        ctrl = HTTPRelayTowerController()
        mock_requests = MagicMock()
        with patch.dict(sys.modules, {"requests": mock_requests}):
            ctrl._get("http://relay.local/on")
        _, kwargs = mock_requests.get.call_args
        assert kwargs.get("timeout") == 1.0


class TestHTTPRelayTowerControllerCommands:

    def _make_with_urls(self, monkeypatch):
        monkeypatch.setenv("TOWER_HTTP_GREEN_URL", "http://r.local/green_on")
        monkeypatch.setenv("TOWER_HTTP_RED_URL", "http://r.local/red_on")
        monkeypatch.setenv("TOWER_HTTP_OFF_GREEN_URL", "http://r.local/green_off")
        monkeypatch.setenv("TOWER_HTTP_OFF_RED_URL", "http://r.local/red_off")
        return HTTPRelayTowerController()

    def test_set_green_calls_red_off_then_green_on(self, monkeypatch):
        ctrl = self._make_with_urls(monkeypatch)
        with patch.object(ctrl, "_get") as mock_get:
            ctrl.set_green("S1")
        assert mock_get.call_count == 2
        assert mock_get.call_args_list[0] == call("http://r.local/red_off")
        assert mock_get.call_args_list[1] == call("http://r.local/green_on")

    def test_set_red_calls_green_off_then_red_on(self, monkeypatch):
        ctrl = self._make_with_urls(monkeypatch)
        with patch.object(ctrl, "_get") as mock_get:
            ctrl.set_red("S1")
        assert mock_get.call_count == 2
        assert mock_get.call_args_list[0] == call("http://r.local/green_off")
        assert mock_get.call_args_list[1] == call("http://r.local/red_on")

    def test_set_idle_calls_green_off_and_red_off(self, monkeypatch):
        ctrl = self._make_with_urls(monkeypatch)
        with patch.object(ctrl, "_get") as mock_get:
            ctrl.set_idle("S1")
        assert mock_get.call_count == 2
        assert mock_get.call_args_list[0] == call("http://r.local/green_off")
        assert mock_get.call_args_list[1] == call("http://r.local/red_off")

    def test_blink_red_alternates_red_and_idle(self, monkeypatch):
        ctrl = self._make_with_urls(monkeypatch)
        call_sequence = []
        def _fake_get(url):
            call_sequence.append(url)
        with patch.object(ctrl, "_get", side_effect=_fake_get), patch("time.sleep"):
            ctrl.blink_red("S1", times=2)
        # 2 blinks: red_on+green_off, red_off+green_off interleaved with sleeps
        assert len(call_sequence) == 8  # 2 × (set_red=2 + set_idle=2)

    def test_blink_red_sleeps_between_pulses(self, monkeypatch):
        ctrl = self._make_with_urls(monkeypatch)
        with patch.object(ctrl, "_get"), patch("time.sleep") as mock_sleep:
            ctrl.blink_red("S1", times=3)
        assert mock_sleep.call_count == 6  # 3 × (sleep after red + sleep after idle)

    def test_no_env_vars_all_urls_empty(self, monkeypatch):
        for key in ("TOWER_HTTP_GREEN_URL", "TOWER_HTTP_RED_URL",
                    "TOWER_HTTP_OFF_GREEN_URL", "TOWER_HTTP_OFF_RED_URL"):
            monkeypatch.delenv(key, raising=False)
        ctrl = HTTPRelayTowerController()
        assert ctrl.green_on == ""
        assert ctrl.red_on == ""
        assert ctrl.green_off == ""
        assert ctrl.red_off == ""


# ---------------------------------------------------------------------------
# get_tower_controller factory
# ---------------------------------------------------------------------------

class TestGetTowerControllerFactory:

    def test_default_returns_simulated(self, monkeypatch):
        monkeypatch.delenv("TOWER_CONTROLLER_TYPE", raising=False)
        ctrl = get_tower_controller()
        assert isinstance(ctrl, SimulatedTowerController)

    def test_simulated_explicit_returns_simulated(self, monkeypatch):
        monkeypatch.setenv("TOWER_CONTROLLER_TYPE", "simulated")
        ctrl = get_tower_controller()
        assert isinstance(ctrl, SimulatedTowerController)

    def test_simulated_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("TOWER_CONTROLLER_TYPE", "SIMULATED")
        ctrl = get_tower_controller()
        assert isinstance(ctrl, SimulatedTowerController)

    def test_http_relay_returns_http_controller(self, monkeypatch):
        monkeypatch.setenv("TOWER_CONTROLLER_TYPE", "http_relay")
        ctrl = get_tower_controller()
        assert isinstance(ctrl, HTTPRelayTowerController)

    def test_http_relay_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("TOWER_CONTROLLER_TYPE", "HTTP_RELAY")
        ctrl = get_tower_controller()
        assert isinstance(ctrl, HTTPRelayTowerController)

    def test_gpio_returns_gpio_controller(self, monkeypatch):
        monkeypatch.setenv("TOWER_CONTROLLER_TYPE", "gpio")
        from app.api.v1.quality.tower_controller import GPIOTowerController
        ctrl = get_tower_controller()
        assert isinstance(ctrl, GPIOTowerController)

    def test_unknown_value_returns_simulated(self, monkeypatch):
        monkeypatch.setenv("TOWER_CONTROLLER_TYPE", "unknown_type")
        ctrl = get_tower_controller()
        assert isinstance(ctrl, SimulatedTowerController)
