"""Cloud Connector — WebSocket persistent connection to EPI Monitor API."""
import asyncio
import json
import logging
import time
from typing import Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


class CloudConnector:
    """Maintains persistent WebSocket connection to cloud API.

    Features:
    - Heartbeat every 30s
    - Exponential backoff reconnect (2s -> 60s)
    - Outbound queue for offline buffering
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        agent_id: str,
        on_command: Optional[Callable] = None,
    ) -> None:
        self._url = api_url.replace("http", "ws") + "/ws/agent"
        self._api_key = api_key
        self._agent_id = agent_id
        self._on_command = on_command
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._connected = False

    async def send(self, message: dict) -> None:
        """Queue message for sending. Non-blocking."""
        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("cloud_connector: queue full, dropping message")

    async def run(self) -> None:
        """Main loop with reconnect."""
        backoff = 2
        while True:
            try:
                headers = {
                    "X-Agent-ID": self._agent_id,
                    "X-API-Key": self._api_key,
                }
                async with websockets.connect(
                    self._url, extra_headers=headers, ping_interval=30
                ) as ws:
                    self._connected = True
                    backoff = 2
                    logger.info("cloud_connector: connected to %s", self._url)
                    await asyncio.gather(
                        self._send_loop(ws),
                        self._recv_loop(ws),
                        self._heartbeat_loop(ws),
                    )
            except (ConnectionClosed, OSError) as exc:
                self._connected = False
                logger.warning(
                    "cloud_connector: disconnected (%s), retry in %ds", exc, backoff
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
            except Exception as exc:
                self._connected = False
                logger.error(
                    "cloud_connector: error %s, retry in %ds", exc, backoff
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def _send_loop(self, ws) -> None:
        while True:
            msg = await self._queue.get()
            await ws.send(json.dumps(msg))

    async def _recv_loop(self, ws) -> None:
        async for message in ws:
            try:
                data = json.loads(message)
                if self._on_command:
                    await self._on_command(data)
            except Exception as exc:
                logger.warning("cloud_connector: recv error %s", exc)

    async def _heartbeat_loop(self, ws) -> None:
        while True:
            await asyncio.sleep(30)
            await ws.send(json.dumps({
                "type": "heartbeat",
                "agent_id": self._agent_id,
                "timestamp": time.time(),
            }))
