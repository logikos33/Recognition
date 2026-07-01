"""
Unit tests: LPR service — parse_plate, ocr_plate, process_plate_crop (task-050).

Estratégia:
  - parse_plate: tabela de casos Mercosul + antiga + inválidos
  - ocr_plate: mocked via patch do backend
  - process_plate_crop: decisão de review threshold
"""
from unittest.mock import patch

import pytest

from app.domain.services.lpr_service import (
    CONFIDENCE_REVIEW_THRESHOLD,
    PlateResult,
    ocr_plate,
    parse_plate,
    process_plate_crop,
)


# ---------------------------------------------------------------------------
# parse_plate — Mercosul e antiga
# ---------------------------------------------------------------------------
class TestParsePlate:

    @pytest.mark.parametrize("text,expected_format,normalized", [
        # Mercosul (2018+): 3 letras · dígito · LETRA · 2 dígitos
        ("ABC1D23",  "mercosul", "ABC1D23"),
        ("abc1d23",  "mercosul", "ABC1D23"),   # lowercase → normaliza
        ("RST2B89",  "mercosul", "RST2B89"),   # 5ª posição: letra
        ("ABC-1D23", "mercosul", "ABC1D23"),   # hífen ignorado
        # Antiga: 3 letras · 4 dígitos
        ("ABC1234",  "antiga",   "ABC1234"),
        ("ZZZ9999",  "antiga",   "ZZZ9999"),
        ("ABC 1234", "antiga",   "ABC1234"),   # espaço ignorado
    ])
    def test_valid_plates(self, text: str, expected_format: str, normalized: str) -> None:
        result = parse_plate(text)
        assert result is not None, f"Placa '{text}' deveria ser válida"
        assert result["format"] == expected_format
        assert result["normalized"] == normalized

    @pytest.mark.parametrize("text", [
        "",           # vazio
        "AB1234",     # só 2 letras no início
        "ABCD1234",   # 4 letras no início
        "ABC123",     # 3 dígitos — não é nem Mercosul nem antiga
        "ABC12345",   # 5 dígitos — muito longo
        "123ABC1",    # começa com dígito
        "!!@#$%",     # caracteres especiais
        None,         # type: ignore[arg-type]
    ])
    def test_invalid_plates(self, text) -> None:
        result = parse_plate(text)
        assert result is None, f"Placa '{text}' deveria ser inválida"

    def test_fifth_position_letter_is_mercosul_digit_is_antiga(self) -> None:
        """Mercosul exige LETRA na 5ª posição; dígito → cai no formato antiga."""
        r_letter = parse_plate("ABC1A23")
        assert r_letter is not None
        assert r_letter["format"] == "mercosul"

        r_digit = parse_plate("ABC1123")   # 4 dígitos finais (1123) → antiga
        assert r_digit is not None
        assert r_digit["format"] == "antiga"

    def test_old_format_all_uppercase(self) -> None:
        result = parse_plate("BRA1234")
        assert result is not None
        assert result["format"] == "antiga"
        assert result["normalized"] == "BRA1234"


# ---------------------------------------------------------------------------
# ocr_plate — mockado
# ---------------------------------------------------------------------------
class TestOcrPlate:

    def test_returns_none_by_default(self) -> None:
        """O stub padrão retorna (None, 0.0) — modelo não configurado."""
        text, conf = ocr_plate(b"fake-image-bytes")
        assert text is None
        assert conf == pytest.approx(0.0)

    def test_mocked_ocr_returns_custom_value(self) -> None:
        """Patch do backend simula OCR real nos testes."""
        with patch("app.domain.services.lpr_service._ocr_backend", return_value=("ABC1D23", 0.95)):
            text, conf = ocr_plate(b"fake")
        assert text == "ABC1D23"
        assert conf == pytest.approx(0.95)

    def test_ocr_exception_returns_none(self) -> None:
        """Exceção no backend → (None, 0.0) silencioso."""
        def bad_backend(b: bytes):
            raise RuntimeError("GPU error")

        with patch("app.domain.services.lpr_service._ocr_backend", side_effect=bad_backend):
            text, conf = ocr_plate(b"bad")
        assert text is None
        assert conf == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# process_plate_crop — pipeline completo
# ---------------------------------------------------------------------------
class TestProcessPlateCrop:

    def test_no_ocr_result_returns_empty(self) -> None:
        """Backend retorna None → PlateResult com plate_text=None."""
        with patch("app.domain.services.lpr_service._ocr_backend", return_value=(None, 0.0)):
            result = process_plate_crop(b"img")
        assert isinstance(result, PlateResult)
        assert result.plate_text is None
        assert not result.needs_review

    def test_high_confidence_no_review(self) -> None:
        """Confiança acima do threshold → needs_review=False."""
        with patch("app.domain.services.lpr_service._ocr_backend", return_value=("ABC1234", 0.95)):
            result = process_plate_crop(b"img")
        assert result.plate_text == "ABC1234"
        assert result.normalized == "ABC1234"
        assert result.format == "antiga"
        assert not result.needs_review
        assert result.confidence == pytest.approx(0.95)

    def test_low_confidence_triggers_review(self) -> None:
        """Confiança abaixo do threshold → needs_review=True."""
        low_conf = CONFIDENCE_REVIEW_THRESHOLD - 0.01
        with patch("app.domain.services.lpr_service._ocr_backend", return_value=("ABC1D23", low_conf)):
            result = process_plate_crop(b"img")
        assert result.plate_text == "ABC1D23"
        assert result.needs_review is True

    def test_exact_threshold_no_review(self) -> None:
        """Exatamente no threshold (0.80) → NÃO precisa revisão."""
        with patch("app.domain.services.lpr_service._ocr_backend", return_value=("ABC1234", CONFIDENCE_REVIEW_THRESHOLD)):
            result = process_plate_crop(b"img")
        assert not result.needs_review

    def test_invalid_plate_text_flags_review(self) -> None:
        """OCR retorna texto mas não é placa válida → needs_review=True."""
        with patch("app.domain.services.lpr_service._ocr_backend", return_value=("XYZNOTPLATE", 0.90)):
            result = process_plate_crop(b"img")
        assert result.needs_review is True
        assert result.plate_text == "XYZNOTPLATE"  # preserva texto original p/ revisão
        assert result.normalized is None

    def test_to_dict_structure(self) -> None:
        """to_dict retorna chaves esperadas pelo frontend."""
        r = PlateResult("ABC1234", 0.92, normalized="ABC1234", format_="antiga", needs_review=False)
        d = r.to_dict()
        assert "plate_text" in d
        assert "plate_confidence" in d
        assert "plate_review" in d
        assert "plate_format" in d
        assert d["plate_text"] == "ABC1234"
        assert d["plate_confidence"] == pytest.approx(0.92)
        assert d["plate_review"] is False
        assert d["plate_format"] == "antiga"

    def test_mercosul_plate_recognized(self) -> None:
        """Placa Mercosul é reconhecida e normalizada corretamente."""
        with patch("app.domain.services.lpr_service._ocr_backend", return_value=("rst2b89", 0.91)):
            result = process_plate_crop(b"img")
        assert result.normalized == "RST2B89"
        assert result.format == "mercosul"
        assert not result.needs_review
