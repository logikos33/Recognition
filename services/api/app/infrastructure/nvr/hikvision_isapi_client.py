"""
Recognition — Hikvision ISAPI Client (WS-B1, ADR-0034, 2º da cascata).

ISAPI (REST/XML, Digest Auth) é o caminho recomendado quando o gravador é
Hikvision (ou compatível ISAPI, ex. Intelbras NVR linha profissional) — mais
simples e estável que ONVIF Profile G na prática (ADR-0034).

Endpoints usados:
  GET  /ISAPI/System/deviceInfo                  — ping (test_connection)
  POST /ISAPI/ContentMgmt/search                 — busca de gravação (timeline)

Playback: URL RTSP com starttime/endtime (formato Hikvision:
YYYYMMDDTHHMMSSZ), servida pelo próprio gravador via
Streaming/tracks/{channel}01.

PENDÊNCIA: request/response não validados contra hardware real (sem NVR
disponível neste ambiente) — cobertura via XML mockado, formato conforme
documentação pública ISAPI (Hikvision Open Platform).
"""
import logging
from datetime import datetime
from xml.etree import ElementTree as ET

import requests
from requests.auth import HTTPDigestAuth

from app.core.validators import RTSPUrlValidator
from app.infrastructure.nvr.base import NvrClient, RecordingSegment

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 15
_ISAPI_NS = "http://www.hikvision.com/ver20/XMLSchema"


def _fmt(dt: datetime) -> str:
    """Formato de timestamp ISAPI: YYYY-MM-DDTHH:MM:SSZ."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")


class HikvisionIsapiClient(NvrClient):
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        timeout: int = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = f"http://{host}:{port}"
        self._auth = HTTPDigestAuth(username, password)
        self._timeout = timeout
        self._host = host
        self._port = port

    def test_connection(self) -> bool:
        url = f"{self._base_url}/ISAPI/System/deviceInfo"
        RTSPUrlValidator.validate(url)
        try:
            resp = requests.get(url, auth=self._auth, timeout=self._timeout)
            return resp.status_code == 200
        except requests.RequestException as exc:
            logger.warning("hikvision_test_connection_failed: host=%s err=%s", self._host, exc)
            return False

    def search_recordings(
        self, channel: int, start: datetime, end: datetime
    ) -> list[RecordingSegment]:
        url = f"{self._base_url}/ISAPI/ContentMgmt/search"
        RTSPUrlValidator.validate(url)

        body = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<CMSearchDescription>'
            "<searchID>recognition-nvr-search</searchID>"
            "<trackList>"
            f"<trackID>{channel}01</trackID>"
            "</trackList>"
            "<timeSpanList><timeSpan>"
            f"<startTime>{_fmt(start)}</startTime>"
            f"<endTime>{_fmt(end)}</endTime>"
            "</timeSpan></timeSpanList>"
            "<maxResults>64</maxResults>"
            "<searchResultPostion>0</searchResultPostion>"
            "</CMSearchDescription>"
        )
        resp = requests.post(
            url, data=body, auth=self._auth, timeout=self._timeout,
            headers={"Content-Type": "application/xml"},
        )
        resp.raise_for_status()
        return self._parse_search_response(channel, resp.text)

    @staticmethod
    def _find(elem: ET.Element, tag: str, ns: dict[str, str]) -> "ET.Element | None":
        """find() com fallback pra XML sem namespace — NUNCA usar `or` entre
        chamadas de .find(): um Element "folha" (sem filhos, ex. <startTime>)
        avalia como falsy em bool(), o que faria o fallback disparar mesmo
        quando o find() namespaced já tinha achado o elemento certo."""
        found = elem.find(f"h:{tag}", ns)
        if found is None:
            found = elem.find(tag)
        return found

    def _parse_search_response(self, channel: int, xml_text: str) -> list[RecordingSegment]:
        segments: list[RecordingSegment] = []
        try:
            root = ET.fromstring(xml_text)  # noqa: S314 — resposta do próprio gravador (não input de usuário)
        except ET.ParseError as exc:
            logger.warning("hikvision_search_parse_failed: err=%s", exc)
            return segments

        ns = {"h": _ISAPI_NS}
        items = root.findall(".//h:searchMatchItem", ns)
        if not items:
            items = root.findall(".//searchMatchItem")

        for item in items:
            span = self._find(item, "timeSpan", ns)
            if span is None:
                continue
            start_el = self._find(span, "startTime", ns)
            end_el = self._find(span, "endTime", ns)
            if start_el is None or end_el is None or not start_el.text or not end_el.text:
                continue
            try:
                seg_start = _parse(start_el.text)
                seg_end = _parse(end_el.text)
            except ValueError:
                logger.warning("hikvision_search_invalid_timespan: item=%s", ET.tostring(item))
                continue
            segments.append(
                RecordingSegment(
                    channel=channel, start=seg_start, end=seg_end,
                    playback_ref=f"{seg_start.isoformat()}/{seg_end.isoformat()}",
                )
            )
        return segments

    def build_playback_url(self, segment: RecordingSegment) -> str:
        url = (
            f"rtsp://{self._host}:554/Streaming/tracks/{segment.channel}01"
            f"?starttime={_fmt(segment.start)}&endtime={_fmt(segment.end)}"
        )
        return RTSPUrlValidator.validate(url)
