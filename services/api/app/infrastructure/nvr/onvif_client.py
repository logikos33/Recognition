"""
Recognition — ONVIF Profile G Client (WS-B1, ADR-0034, 1º da cascata).

SOAP cru via `requests` (sem onvif-zeep/WSDL) — envelopes mínimos das 3
operações necessárias: GetSystemDateAndTime (ping), FindRecordings +
GetRecordingSearchResults (busca de timeline), GetReplayUri (URL de
playback). Endpoints via os caminhos padrão ONVIF (device_service /
search_service / replay_service) — descoberta via GetCapabilities não
implementada nesta versão (ver pendência abaixo).

PENDÊNCIA: nenhuma chamada foi validada contra um dispositivo ONVIF real
(sem hardware disponível neste ambiente). Cobertura via SOAP mockado,
envelopes conforme especificação ONVIF Core/Profile G pública. Antes de
usar em produção: validar contra um NVR real e, se necessário, trocar os
caminhos fixos por descoberta via GetCapabilities.
"""
import logging
import re
from datetime import datetime
from uuid import uuid4

import requests

from app.core.validators import RTSPUrlValidator
from app.infrastructure.nvr.base import NvrClient, RecordingSegment

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 15
_SOAP_ENV_NS = "http://www.w3.org/2003/05/soap-envelope"


def _fmt(dt: datetime) -> str:
    """Formato ISO 8601 UTC exigido pelo ONVIF (xs:dateTime)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _soap_envelope(body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<s:Envelope xmlns:s="{_SOAP_ENV_NS}">'
        f"<s:Body>{body}</s:Body>"
        "</s:Envelope>"
    )


class OnvifClient(NvrClient):
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
        self._device_url = f"http://{host}:{port}/onvif/device_service"
        self._search_url = f"http://{host}:{port}/onvif/search_service"
        self._replay_url = f"http://{host}:{port}/onvif/replay_service"

    def _post_soap(self, url: str, body: str) -> str:
        RTSPUrlValidator.validate(url)
        resp = requests.post(
            url,
            data=_soap_envelope(body),
            timeout=self._timeout,
            headers={"Content-Type": "application/soap+xml; charset=utf-8"},
        )
        resp.raise_for_status()
        return resp.text

    def test_connection(self) -> bool:
        try:
            body = '<tds:GetSystemDateAndTime xmlns:tds="http://www.onvif.org/ver10/device/wsdl"/>'
            self._post_soap(self._device_url, body)
            return True
        except requests.RequestException as exc:
            logger.warning("onvif_test_connection_failed: host=%s err=%s", self._host, exc)
            return False

    def search_recordings(
        self, channel: int, start: datetime, end: datetime
    ) -> list[RecordingSegment]:
        search_token = f"recognition-{uuid4().hex[:12]}"
        find_body = (
            '<tse:FindRecordings xmlns:tse="http://www.onvif.org/ver10/search/wsdl">'
            "<Scope>"
            "<IncludedSources/>"
            f"<IncludedRecordings><Token>{channel}</Token></IncludedRecordings>"
            "</Scope>"
            "<KeepAliveTime>PT30S</KeepAliveTime>"
            "</tse:FindRecordings>"
        )
        find_resp = self._post_soap(self._search_url, find_body)
        search_token = self._extract_search_token(find_resp) or search_token

        results_body = (
            '<tse:GetRecordingSearchResults xmlns:tse="http://www.onvif.org/ver10/search/wsdl">'
            f"<SearchToken>{search_token}</SearchToken>"
            "<MinResults>1</MinResults><MaxResults>64</MaxResults>"
            "</tse:GetRecordingSearchResults>"
        )
        results_resp = self._post_soap(self._search_url, results_body)
        return self._parse_recording_results(channel, results_resp, start, end)

    @staticmethod
    def _extract_search_token(xml_text: str) -> "str | None":
        match = re.search(r"<(?:\w+:)?SearchToken>([^<]+)</(?:\w+:)?SearchToken>", xml_text)
        return match.group(1) if match else None

    def _parse_recording_results(
        self, channel: int, xml_text: str, requested_start: datetime, requested_end: datetime
    ) -> list[RecordingSegment]:
        """Extrai (Track/RecordingToken, Time) de cada RecordingInformation.

        Parsing por regex (não ElementTree): a resposta ONVIF tem prefixos de
        namespace variáveis por fabricante (tse:/tt:/sem prefixo) — regex nos
        elementos-folha é mais robusto que casar namespace exato aqui.
        """
        segments: list[RecordingSegment] = []
        for m in re.finditer(
            r"<(?:\w+:)?RecordingInformation>.*?<(?:\w+:)?Time>([^<]+)</(?:\w+:)?Time>",
            xml_text, re.DOTALL,
        ):
            try:
                ts = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue
            if requested_start <= ts <= requested_end:
                segments.append(
                    RecordingSegment(
                        channel=channel, start=ts, end=requested_end,
                        playback_ref=ts.isoformat(),
                    )
                )
        return segments

    def build_playback_url(self, segment: RecordingSegment) -> str:
        """GetReplayUri — protocolo RTSP, stream do canal no intervalo."""
        body = (
            '<trp:GetReplayUri xmlns:trp="http://www.onvif.org/ver10/replay/wsdl">'
            "<StreamSetup>"
            "<Stream xmlns=\"http://www.onvif.org/ver10/schema\">RTP-Unicast</Stream>"
            "<Transport xmlns=\"http://www.onvif.org/ver10/schema\">"
            "<Protocol>RTSP</Protocol></Transport>"
            "</StreamSetup>"
            f"<RecordingToken>{segment.channel}</RecordingToken>"
            "</trp:GetReplayUri>"
        )
        resp = self._post_soap(self._replay_url, body)
        match = re.search(r"<(?:\w+:)?Uri>([^<]+)</(?:\w+:)?Uri>", resp)
        if not match:
            raise RuntimeError("GetReplayUri não retornou Uri")
        return RTSPUrlValidator.validate(match.group(1))
