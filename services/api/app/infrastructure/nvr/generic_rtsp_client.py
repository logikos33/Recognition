"""
Recognition — Generic RTSP-with-timestamp Client (WS-B1, ADR-0034, 3º/
fallback da cascata).

Sem API de busca dedicada — usado quando o gravador só expõe RTSP com
parâmetro de tempo (DVR genérico, ou fabricante sem ISAPI/ONVIF). Não há
"timeline" real: search_recordings sempre devolve um único segmento
cobrindo o intervalo pedido (o próprio RTSP seeka pro timestamp; se não
houver gravação naquele intervalo, o playback falha na extração, não na
busca — comportamento aceito pelo ADR-0034 pra esse fallback).

Template de URL por fabricante (Dahua/Intelbras compartilham o mesmo dialeto
de query string de playback RTSP; ajuste fino de mapeamento de canal fica
como TODO — ver PENDÊNCIA no PR).
"""
import logging
import socket
from datetime import datetime

from app.core.validators import RTSPUrlValidator
from app.infrastructure.nvr.base import NvrClient, RecordingSegment

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 5


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


class GenericRtspPlaybackClient(NvrClient):
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        timeout: int = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._timeout = timeout

    def test_connection(self) -> bool:
        """Sem API HTTP — testa só se a porta RTSP aceita conexão TCP."""
        try:
            with socket.create_connection((self._host, self._port), timeout=self._timeout):
                return True
        except OSError as exc:
            logger.warning(
                "generic_rtsp_test_connection_failed: host=%s port=%s err=%s",
                self._host, self._port, exc,
            )
            return False

    def search_recordings(
        self, channel: int, start: datetime, end: datetime
    ) -> list[RecordingSegment]:
        """Sem busca real — devolve 1 segmento cobrindo o intervalo pedido
        (playback via URL com starttime/endtime resolve ou falha na hora
        de extrair, não aqui)."""
        return [
            RecordingSegment(
                channel=channel, start=start, end=end,
                playback_ref=f"{start.isoformat()}/{end.isoformat()}",
            )
        ]

    def build_playback_url(self, segment: RecordingSegment) -> str:
        from urllib.parse import quote  # noqa: PLC0415

        user = quote(self._username or "", safe="")
        pwd = quote(self._password or "", safe="")
        creds = f"{user}:{pwd}@" if user else ""
        url = (
            f"rtsp://{creds}{self._host}:{self._port}/cam/playback"
            f"?channel={segment.channel}"
            f"&starttime={_fmt(segment.start)}&endtime={_fmt(segment.end)}"
        )
        return RTSPUrlValidator.validate(url)
