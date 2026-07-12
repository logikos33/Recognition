"""
Recognition — NVR Client Factory (WS-B1, ADR-0034).

Mapeia `recorders.protocol` pro client concreto. Cascata da ADR: ONVIF
Profile G é o caminho "ideal" (protocolo aberto), Hikvision ISAPI é o SDK
de fabricante mais tratável de implementar sem hardware de teste; Dahua/
Intelbras/RTSP genérico caem no fallback RTSP-com-timestamp (sem API de
busca dedicada — TODO conhecido: Dahua e Intelbras têm APIs HTTP próprias
(CGI-based) que não foram implementadas nesta PR por falta de hardware
pra validar contra).
"""
from typing import Any

from app.infrastructure.nvr.base import NvrClient
from app.infrastructure.nvr.generic_rtsp_client import GenericRtspPlaybackClient
from app.infrastructure.nvr.hikvision_isapi_client import HikvisionIsapiClient
from app.infrastructure.nvr.onvif_client import OnvifClient

_CLIENTS_BY_PROTOCOL: dict[str, type[NvrClient]] = {
    "onvif": OnvifClient,
    "hikvision": HikvisionIsapiClient,
    "dahua": GenericRtspPlaybackClient,
    "intelbras": GenericRtspPlaybackClient,
    "rtsp": GenericRtspPlaybackClient,
}


def get_nvr_client(recorder: dict[str, Any], password: str) -> NvrClient:
    """Resolve o client pelo protocolo do recorder (dict de repository/model)."""
    protocol = str(recorder.get("protocol") or "onvif")
    client_cls = _CLIENTS_BY_PROTOCOL.get(protocol, GenericRtspPlaybackClient)
    return client_cls(
        host=recorder["host"],
        port=recorder.get("port", 80),
        username=recorder.get("username") or "",
        password=password,
    )
