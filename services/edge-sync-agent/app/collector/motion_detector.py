"""Frame-diffing motion detection — no ONVIF motion events confirmed available
across RVB's Intelbras hardware (task-092 investigation), so the collector
polls RecorderClient.capture_frame() and decides "did anything change" itself.

Downscaled-grayscale mean absolute difference: a classic, dependency-light
motion heuristic. Deliberately Pillow-only (no numpy/opencv) — opencv-python
wheels on ARM/Jetson are a known landmine (the box already has JetPack's own
OpenCV build; a second pip install risks shadowing or conflicting with it,
see docs/edge/REGRAS_PLATAFORMA_JETSON.md's landmine notes), and numpy alone
would still need something to decode JPEG bytes in the first place.

Pure functions/class, no I/O — testable without a real camera or ffmpeg.

CALIBRADO EM CAMPO (RVB, 2026-07-31): a primeira versão usava a diferença
MÉDIA do quadro com limiar 8.0 e enchia o bucket de quadro inútil — ruído de
compressão e tremulação de luz marcavam 8.19/8.70, colados no limiar, e
disparavam rajada atrás de rajada. Movimento real marcava 30-43. Trocado por
fração de ÁREA alterada (`motion_area_fraction`), que separa os dois casos
por construção em vez de depender de um limiar bem no meio do ruído.
Ajustável por COLLECTOR_MOTION_THRESHOLD (agora é fração, 0.0-1.0).
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageStat

_THUMBNAIL_SIZE = (64, 48)
# Quanto um pixel precisa mudar (0-255) pra contar como "mudou de verdade".
# Abaixo disso é ruído de compressão JPEG e variação sutil de iluminação.
_PIXEL_DELTA = 25


@dataclass(frozen=True)
class MotionResult:
    changed: bool
    score: float  # fração do quadro que mudou de fato, 0.0-1.0


def frame_diff_score(frame_a: bytes, frame_b: bytes) -> float:
    """Diferença média por pixel (0-255) entre dois JPEGs, cinza reduzido.

    Usada só pelo DEDUP intra-burst do coletor ("esse frame é praticamente
    igual ao último que subi?"). NÃO serve como sinal de movimento — ver
    `motion_area_fraction`.
    """
    a = _to_thumbnail(frame_a)
    b = _to_thumbnail(frame_b)
    diff = ImageChops.difference(a, b)
    return ImageStat.Stat(diff).mean[0]


def motion_area_fraction(
    frame_a: bytes, frame_b: bytes, pixel_delta: int = _PIXEL_DELTA
) -> float:
    """Fração do quadro (0.0-1.0) cujos pixels mudaram ACIMA de `pixel_delta`.

    Substitui a diferença média como sinal de movimento. Medido em campo na
    RVB, a média não separava as duas situações:
        ruído/iluminação -> 8.19, 8.70   |   pessoa passando -> 30.4, 43.5
    com o limiar em 8.0, tremulação de luz e ruído de compressão disparavam
    rajada atrás de rajada e enchiam o bucket de quadro inútil.

    Contar ÁREA em vez de média separa por construção: mudança global de
    brilho mexe um pouco em todo pixel (fica abaixo de `pixel_delta`, não
    conta), enquanto algo se movendo muda muito uma região (conta). É a
    abordagem clássica de detecção por frame-differencing.
    """
    a = _to_thumbnail(frame_a)
    b = _to_thumbnail(frame_b)
    diff = ImageChops.difference(a, b)
    # point() -> 255 onde passou do delta, 0 caso contrário; a média disso
    # dividida por 255 é exatamente a fração de pixels que mudaram.
    mask = diff.point(lambda px: 255 if px > pixel_delta else 0)
    return ImageStat.Stat(mask).mean[0] / 255.0


class MotionDetector:
    """Detector com estado, por câmera — chame detect() com cada frame novo,
    na ordem de captura. A PRIMEIRA chamada nunca acusa movimento (não há
    contra o que comparar ainda, só semeia `_previous`); é o comportamento
    correto de frame-differencing, não um bug.
    """

    # 2% do quadro. Pessoa/empilhadeira entrando em cena muda MUITO mais que
    # isso; ruído de compressão e tremulação de luz, muito menos.
    DEFAULT_MIN_AREA = 0.02

    def __init__(
        self,
        threshold: float = DEFAULT_MIN_AREA,
        pixel_delta: int = _PIXEL_DELTA,
    ) -> None:
        self._threshold = threshold
        self._pixel_delta = pixel_delta
        self._previous: bytes | None = None

    def detect(self, frame_bytes: bytes) -> MotionResult:
        if self._previous is None:
            self._previous = frame_bytes
            return MotionResult(changed=False, score=0.0)
        score = motion_area_fraction(frame_bytes, self._previous, self._pixel_delta)
        self._previous = frame_bytes
        return MotionResult(changed=score >= self._threshold, score=score)


def _to_thumbnail(frame_bytes: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(frame_bytes)).convert("L")
    image.thumbnail(_THUMBNAIL_SIZE)
    return image
