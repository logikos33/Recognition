"""Clientes de NVR/DVR (WS-B1, ADR-0034) — cascata ONVIF Profile G → SDK do
fabricante (Hikvision ISAPI) → RTSP com timestamp.

PENDÊNCIA CONHECIDA (não bloqueante, ver PR): nenhum destes clients foi
validado contra hardware real — não há NVR/DVR disponível neste ambiente de
desenvolvimento. A lógica de protocolo (construção de request, parsing de
resposta) tem cobertura de teste unitário com respostas mockadas
(fixtures realistas por fabricante), mas a validação E2E contra um
gravador de verdade é uma pendência explícita.
"""
from app.infrastructure.nvr.base import NvrClient, RecordingSegment
from app.infrastructure.nvr.factory import get_nvr_client

__all__ = ["NvrClient", "RecordingSegment", "get_nvr_client"]
