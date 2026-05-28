"""
Tower Controller — adapter para torre luminosa industrial (sinaleiro).

Implementações disponíveis:
  - SimulatedTowerController : apenas loga (desenvolvimento/teste) — padrão
  - GPIOTowerController      : Raspberry Pi GPIO
  - HTTPRelayTowerController : relé HTTP (Sonoff / ESP8266 Tasmota)

Seleção via variável de ambiente:
  TOWER_CONTROLLER_TYPE = simulated | gpio | http_relay  (default: simulated)

Pinos GPIO (apenas GPIOTowerController):
  TOWER_GPIO_GREEN_PIN = 17  (default)
  TOWER_GPIO_RED_PIN   = 27  (default)

URLs do relé HTTP (apenas HTTPRelayTowerController):
  TOWER_HTTP_GREEN_URL     = URL para acionar verde
  TOWER_HTTP_RED_URL       = URL para acionar vermelho
  TOWER_HTTP_OFF_GREEN_URL = URL para desligar verde
  TOWER_HTTP_OFF_RED_URL   = URL para desligar vermelho
"""
import logging
import os
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class TowerController(ABC):
    """Interface para controle de torre luminosa (sinaleiro industrial).

    Implementações disponíveis:
    - SimulatedTowerController: log apenas (desenvolvimento/teste)
    - GPIOTowerController: Raspberry Pi GPIO
    - USBRelayTowerController: módulo relé USB HID
    - HTTPRelayTowerController: relé HTTP (ex: Sonoff)
    """

    @abstractmethod
    def set_green(self, station: str) -> None:
        """Acende verde (OK). Apaga vermelho.

        Args:
            station: Código da bancada (para logging/contexto).
        """

    @abstractmethod
    def set_red(self, station: str) -> None:
        """Acende vermelho (NOK). Apaga verde.

        Args:
            station: Código da bancada (para logging/contexto).
        """

    @abstractmethod
    def set_idle(self, station: str) -> None:
        """Apaga todos os sinalizadores (aguardando peça).

        Args:
            station: Código da bancada (para logging/contexto).
        """

    @abstractmethod
    def blink_red(self, station: str, times: int = 3) -> None:
        """Pisca vermelho N vezes (alerta de atenção).

        Args:
            station: Código da bancada.
            times: Número de piscadas (default: 3).
        """


class SimulatedTowerController(TowerController):
    """Torre simulada — apenas loga. Usar em desenvolvimento e testes."""

    def set_green(self, station: str) -> None:
        """Simula acionamento do verde — loga o evento."""
        logger.info("tower_green: station=%s", station)

    def set_red(self, station: str) -> None:
        """Simula acionamento do vermelho — loga o evento."""
        logger.info("tower_red: station=%s", station)

    def set_idle(self, station: str) -> None:
        """Simula desligamento de todos — loga o evento."""
        logger.info("tower_idle: station=%s", station)

    def blink_red(self, station: str, times: int = 3) -> None:
        """Simula piscada de vermelho — loga o evento."""
        logger.info("tower_blink_red: station=%s times=%d", station, times)


class GPIOTowerController(TowerController):
    """Torre via GPIO do Raspberry Pi.

    Pinos configurados por variável de ambiente:
      TOWER_GPIO_GREEN_PIN = 17  (default)
      TOWER_GPIO_RED_PIN   = 27  (default)

    Se RPi.GPIO não estiver disponível, opera em modo simulado com log de aviso.
    """

    def __init__(self):
        """Inicializa os pinos GPIO. Fallback para modo simulado se RPi.GPIO indisponível."""
        self.green_pin = int(os.environ.get("TOWER_GPIO_GREEN_PIN", "17"))
        self.red_pin = int(os.environ.get("TOWER_GPIO_RED_PIN", "27"))
        try:
            import RPi.GPIO as GPIO  # lazy — só disponível no Raspberry Pi
            self._gpio = GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.green_pin, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(self.red_pin, GPIO.OUT, initial=GPIO.LOW)
        except ImportError:
            logger.warning("RPi.GPIO não disponível — usando modo simulado")
            self._gpio = None

    def set_green(self, station: str) -> None:
        """Aciona pino verde via GPIO. Apaga vermelho antes."""
        if self._gpio:
            self._gpio.output(self.red_pin, self._gpio.LOW)
            self._gpio.output(self.green_pin, self._gpio.HIGH)
        logger.info("tower_gpio_green: station=%s", station)

    def set_red(self, station: str) -> None:
        """Aciona pino vermelho via GPIO. Apaga verde antes."""
        if self._gpio:
            self._gpio.output(self.green_pin, self._gpio.LOW)
            self._gpio.output(self.red_pin, self._gpio.HIGH)
        logger.info("tower_gpio_red: station=%s", station)

    def set_idle(self, station: str) -> None:
        """Apaga todos os pinos via GPIO."""
        if self._gpio:
            self._gpio.output(self.green_pin, self._gpio.LOW)
            self._gpio.output(self.red_pin, self._gpio.LOW)
        logger.info("tower_gpio_idle: station=%s", station)

    def blink_red(self, station: str, times: int = 3) -> None:
        """Pisca vermelho via GPIO N vezes com intervalo de 0.3s/0.2s."""
        import time
        for _ in range(times):
            self.set_red(station)
            time.sleep(0.3)
            self.set_idle(station)
            time.sleep(0.2)


class HTTPRelayTowerController(TowerController):
    """Torre via relé HTTP (ex: Sonoff Basic, ESP8266 com firmware Tasmota).

    Variáveis de ambiente:
      TOWER_HTTP_GREEN_URL     = http://192.168.1.50/cm?cmnd=Power1%20On
      TOWER_HTTP_RED_URL       = http://192.168.1.51/cm?cmnd=Power1%20On
      TOWER_HTTP_OFF_GREEN_URL = http://192.168.1.50/cm?cmnd=Power1%20Off
      TOWER_HTTP_OFF_RED_URL   = http://192.168.1.51/cm?cmnd=Power1%20Off

    Timeout padrão: 1 segundo por request. Falhas apenas logam warning, não levantam exceção.
    """

    def __init__(self):
        """Lê URLs de controle das variáveis de ambiente."""
        self.green_on = os.environ.get("TOWER_HTTP_GREEN_URL", "")
        self.red_on = os.environ.get("TOWER_HTTP_RED_URL", "")
        self.green_off = os.environ.get("TOWER_HTTP_OFF_GREEN_URL", "")
        self.red_off = os.environ.get("TOWER_HTTP_OFF_RED_URL", "")

    def _get(self, url: str, timeout: float = 1.0) -> None:
        """Faz GET na URL do relé. Silencia erros com log de warning.

        Args:
            url: URL do endpoint do relé HTTP.
            timeout: Timeout em segundos (default: 1.0).
        """
        if not url:
            return
        try:
            import requests  # lazy
            requests.get(url, timeout=timeout)
        except Exception as exc:
            logger.warning("tower_http_error: url=%s err=%s", url, exc)

    def set_green(self, station: str) -> None:
        """Desliga vermelho e aciona verde via HTTP."""
        self._get(self.red_off)
        self._get(self.green_on)

    def set_red(self, station: str) -> None:
        """Desliga verde e aciona vermelho via HTTP."""
        self._get(self.green_off)
        self._get(self.red_on)

    def set_idle(self, station: str) -> None:
        """Desliga verde e vermelho via HTTP."""
        self._get(self.green_off)
        self._get(self.red_off)

    def blink_red(self, station: str, times: int = 3) -> None:
        """Pisca vermelho via HTTP N vezes com intervalo de 0.3s/0.2s."""
        import time
        for _ in range(times):
            self.set_red(station)
            time.sleep(0.3)
            self.set_idle(station)
            time.sleep(0.2)


def get_tower_controller() -> TowerController:
    """Factory: seleciona implementação via TOWER_CONTROLLER_TYPE env var.

    Valores aceitos (case-insensitive):
      - "simulated"   → SimulatedTowerController (padrão)
      - "gpio"        → GPIOTowerController
      - "http_relay"  → HTTPRelayTowerController

    Returns:
        Instância concreta de TowerController.
    """
    controller_type = os.environ.get("TOWER_CONTROLLER_TYPE", "simulated").lower()
    if controller_type == "gpio":
        return GPIOTowerController()
    elif controller_type == "http_relay":
        return HTTPRelayTowerController()
    else:
        return SimulatedTowerController()
