"""
LPR (License Plate Recognition) — task-050.

Responsabilidades:
  1. parse_plate(text)     — valida e normaliza texto de placa BR (Mercosul + antiga)
  2. ocr_plate(crop_bytes) — extrai texto de uma imagem de crop usando backend plugável
  3. process_plate_result  — decide confiança + flag de revisão

Formatos suportados:
  Mercosul  : AAA1A11   (3 letras · 1 dígito · 1 letra ou dígito · 2 dígitos)
  Antiga BR : AAA1234   (3 letras · 4 dígitos)

OCR backend:
  Em produção, substituir _DEFAULT_OCR_BACKEND por chamada a modelo ONNX/CV2 leve.
  Em testes, mockar `ocr_plate` diretamente via patch.

Thresholds:
  CONFIDENCE_REVIEW_THRESHOLD  — abaixo deste valor → plate_review=True (não descarta)
"""
import logging
import re

logger = logging.getLogger(__name__)

# Limiar: abaixo deste → marcada para revisão humana (não descarta)
CONFIDENCE_REVIEW_THRESHOLD = 0.80

# Regex de placas BR
# Mercosul (2018+): ABC1A23 — posição 5 é LETRA obrigatoriamente
# Antiga:           ABC1234 — 4 dígitos finais
_RE_MERCOSUL = re.compile(r"^([A-Z]{3})([0-9])([A-Z])([0-9]{2})$")
_RE_ANTIGA   = re.compile(r"^([A-Z]{3})([0-9]{4})$")


# ---------------------------------------------------------------------------
# Parsing e validação
# ---------------------------------------------------------------------------

def parse_plate(text: str) -> dict | None:
    """
    Valida e normaliza texto de placa brasileira.

    Retorna:
        {"normalized": "ABC1D23", "format": "mercosul"} ou {"format": "antiga"} / None
    Aceita espaços e hífens; normaliza para maiúsculas sem separadores.
    """
    if not text:
        return None

    clean = re.sub(r"[\s\-]", "", text.upper().strip())

    m = _RE_MERCOSUL.match(clean)
    if m:
        return {"normalized": clean, "format": "mercosul"}

    m = _RE_ANTIGA.match(clean)
    if m:
        return {"normalized": clean, "format": "antiga"}

    return None


# ---------------------------------------------------------------------------
# OCR — backend plugável (mockável em testes)
# ---------------------------------------------------------------------------

def _default_ocr_backend(crop_bytes: bytes) -> tuple[str | None, float]:
    """
    Stub OCR — substituir por modelo ONNX/CV2 leve em produção.

    Em desenvolvimento retorna None para indicar "sem OCR disponível".
    Em testes, este símbolo é patchado para retornar valores controlados.

    Retorna:
        (texto_lido, confiança)  ou  (None, 0.0) se não conseguir ler
    """
    logger.debug("lpr_ocr_stub: modelo OCR não configurado — usando fallback None")
    return None, 0.0


# Referência global ao backend — substituível em runtime (ex.: injeção de dependência)
_ocr_backend = _default_ocr_backend


def ocr_plate(crop_bytes: bytes) -> tuple[str | None, float]:
    """
    Extrai texto de placa de um crop de imagem.

    Retorna (plate_text, confidence) onde plate_text pode ser None.
    Esta função é o ponto de patch em testes.
    """
    try:
        return _ocr_backend(crop_bytes)
    except Exception as exc:
        logger.warning("lpr_ocr_error: %s", exc)
        return None, 0.0


# ---------------------------------------------------------------------------
# Processamento de resultado
# ---------------------------------------------------------------------------

class PlateResult:
    """Resultado do processamento de uma detecção de placa."""

    def __init__(
        self,
        plate_text: str | None,
        confidence: float,
        normalized: str | None = None,
        format_: str | None = None,
        needs_review: bool = False,
    ) -> None:
        self.plate_text    = plate_text
        self.confidence    = confidence
        self.normalized    = normalized
        self.format        = format_
        self.needs_review  = needs_review

    def to_dict(self) -> dict:
        return {
            "plate_text":       self.normalized or self.plate_text,
            "plate_confidence": self.confidence,
            "plate_review":     self.needs_review,
            "plate_format":     self.format,
        }


def process_plate_crop(crop_bytes: bytes) -> PlateResult:
    """
    Pipeline completo: OCR → parse → decisão de revisão.

    - Se OCR retornar None → PlateResult com plate_text=None, review=False
    - Se OCR retornar texto mas inválido → review=True (confiança<threshold)
    - Confiança abaixo de CONFIDENCE_REVIEW_THRESHOLD → review=True
    """
    raw_text, confidence = ocr_plate(crop_bytes)

    if not raw_text:
        return PlateResult(None, 0.0)

    parsed = parse_plate(raw_text)

    if not parsed:
        # OCR leu algo mas não é uma placa válida — marca p/ revisão
        return PlateResult(
            plate_text=raw_text,
            confidence=confidence,
            needs_review=True,
        )

    needs_review = confidence < CONFIDENCE_REVIEW_THRESHOLD
    return PlateResult(
        plate_text=parsed["normalized"],
        confidence=confidence,
        normalized=parsed["normalized"],
        format_=parsed["format"],
        needs_review=needs_review,
    )
