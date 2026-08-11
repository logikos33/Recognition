"""
Tests: infrastructure/gpu/license_gate.py — trava RF-DETR Apache 2.0 vs PML
(ADR-0044, decisão do dono).

Cobre:
- framework != 'rfdetr' é sempre no-op (yolox nunca tem variante PML).
- variante ausente (None/"") é permitida (RFDETRBase default).
- variantes Apache (nano/small/base/medium) passam, em qualquer formatação
  (maiúscula, prefixo "rfdetr-"/"RFDETR", etc.).
- variantes XL/2XL (PML) são rejeitadas com mensagem legível mencionando a
  licença — venham de base_model ou de hyperparams (base_model/model_size/
  variant).
- variante desconhecida (nem Apache nem claramente PML) também é rejeitada
  (allowlist estrito, não blocklist).
"""
from __future__ import annotations

import pytest

from app.infrastructure.gpu.license_gate import (
    ALLOWED_RFDETR_VARIANTS,
    RfdetrLicenseError,
    assert_rfdetr_variant_allowed,
)


class TestNonRfdetrFrameworksAreNoOp:
    def test_yolox_never_checked(self) -> None:
        assert_rfdetr_variant_allowed("yolox", base_model="RFDETRXLarge")  # não levanta

    def test_none_framework_never_checked(self) -> None:
        assert_rfdetr_variant_allowed(None, base_model="RFDETR2XLarge")  # não levanta


class TestNoVariantSpecifiedIsAllowed:
    def test_none_base_model_and_hyperparams(self) -> None:
        assert_rfdetr_variant_allowed("rfdetr", base_model=None, hyperparams=None)

    def test_empty_hyperparams_dict(self) -> None:
        assert_rfdetr_variant_allowed("rfdetr", base_model=None, hyperparams={})


class TestApacheVariantsAllowed:
    @pytest.mark.parametrize("variant", sorted(ALLOWED_RFDETR_VARIANTS))
    def test_allowed_variant_passes(self, variant: str) -> None:
        assert_rfdetr_variant_allowed("rfdetr", base_model=variant)

    def test_case_insensitive(self) -> None:
        assert_rfdetr_variant_allowed("rfdetr", base_model="NANO")

    def test_prefixed_class_name(self) -> None:
        assert_rfdetr_variant_allowed("rfdetr", base_model="RFDETRBase")
        assert_rfdetr_variant_allowed("rfdetr", base_model="RFDETRSmall")

    def test_from_hyperparams_variant_key(self) -> None:
        assert_rfdetr_variant_allowed("rfdetr", hyperparams={"variant": "medium"})

    def test_from_hyperparams_model_size_key(self) -> None:
        assert_rfdetr_variant_allowed("rfdetr", hyperparams={"model_size": "small"})

    def test_rf_detr_hyphen_framework_spelling(self) -> None:
        assert_rfdetr_variant_allowed("rf-detr", base_model="nano")


class TestPmlVariantsRejected:
    @pytest.mark.parametrize("variant", [
        "xlarge", "2xlarge", "xl", "2xl",
        "RFDETRXLarge", "RFDETR2XLarge", "rfdetr-xl", "rfdetr_2xl",
    ])
    def test_blocked_variant_raises_license_error(self, variant: str) -> None:
        with pytest.raises(RfdetrLicenseError, match="PML"):
            assert_rfdetr_variant_allowed("rfdetr", base_model=variant)

    def test_blocked_via_hyperparams_base_model(self) -> None:
        with pytest.raises(RfdetrLicenseError, match="PML"):
            assert_rfdetr_variant_allowed("rfdetr", hyperparams={"base_model": "xlarge"})

    def test_blocked_via_hyperparams_variant(self) -> None:
        with pytest.raises(RfdetrLicenseError, match="PML"):
            assert_rfdetr_variant_allowed("rfdetr", hyperparams={"variant": "2xl"})

    def test_error_message_lists_allowed_variants(self) -> None:
        with pytest.raises(RfdetrLicenseError, match=r"nano.*small") as excinfo:
            assert_rfdetr_variant_allowed("rfdetr", base_model="xlarge")
        assert "ADR-0044" in str(excinfo.value)


class TestUnknownVariantsRejectedByStrictAllowlist:
    def test_unrecognized_variant_raises(self) -> None:
        """Allowlist estrito (não blocklist): uma variante nova/desconhecida
        que não seja explicitamente xl/2xl ainda é rejeitada — defesa em
        profundidade contra qualquer variante futura não auditada."""
        with pytest.raises(RfdetrLicenseError, match="não reconhecida"):
            assert_rfdetr_variant_allowed("rfdetr", base_model="turbo")
