"""
Recognition — NVR Client (Abstract).

Interface plugável por protocolo (ONVIF Profile G / Hikvision ISAPI / RTSP
com timestamp), cascata decidida pela ADR-0034. Mesma forma de
`infrastructure/storage/base.py::StorageStrategy`.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RecordingSegment:
    """Um trecho de gravação contínua encontrado na timeline do gravador."""

    channel: int
    start: datetime
    end: datetime
    playback_ref: str  # URL de playback ou token do gravador, por protocolo


class NvrClient(ABC):
    """Abstração de acesso a gravador (busca de timeline + URL de playback)."""

    @abstractmethod
    def test_connection(self) -> bool:
        """Ping leve (ex.: GetSystemDateAndTime/ISAPI status) — não faz
        busca de gravação. Retorna False (não levanta) em falha de rede."""
        ...

    @abstractmethod
    def search_recordings(
        self, channel: int, start: datetime, end: datetime
    ) -> list[RecordingSegment]:
        """Busca segmentos de gravação existentes no intervalo (timeline)."""
        ...

    @abstractmethod
    def build_playback_url(self, segment: RecordingSegment) -> str:
        """URL de playback pro segmento — SEMPRE validada por
        RTSPUrlValidator antes de qualquer uso (proteção SSRF)."""
        ...
