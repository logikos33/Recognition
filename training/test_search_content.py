"""
Tests: search_content.py — funções PURAS de busca por conteúdo (sem GPU/torch).

search_content.py roda NA GPU remota (zero import do pacote app/) —
importado aqui via importlib a partir do path do arquivo, mesmo padrão de
training/test_propagate_seeded.py. Cobre só a seção "pure matching" do
módulo (xyxy_to_normalized_cxcywh, top_k_by_score, build_finding) — o
caminho GPU real (load_owlv2, run_owlv2_on_frame, download_image) faz
import lazy de torch/PIL/transformers DENTRO das próprias funções, então
importar o módulo aqui não exige nenhuma dessas dependências instaladas.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).parent / "search_content.py"


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("search_content_under_test", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["search_content_under_test"] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("search_content_under_test", None)


class TestXyxyToNormalizedCxcywh:
    def test_full_image_box_is_centered_and_full_size(self, mod) -> None:
        cx, cy, w, h = mod.xyxy_to_normalized_cxcywh((0.0, 0.0, 640.0, 480.0), 640, 480)
        assert cx == pytest.approx(0.5)
        assert cy == pytest.approx(0.5)
        assert w == pytest.approx(1.0)
        assert h == pytest.approx(1.0)

    def test_small_box_in_corner(self, mod) -> None:
        cx, cy, w, h = mod.xyxy_to_normalized_cxcywh((0.0, 0.0, 64.0, 48.0), 640, 480)
        assert cx == pytest.approx(0.05)
        assert cy == pytest.approx(0.05)
        assert w == pytest.approx(0.1)
        assert h == pytest.approx(0.1)

    def test_result_always_clamped_to_0_1(self, mod) -> None:
        # Caixa que "vaza" pra fora da imagem (OWLv2 pode devolver isso) —
        # nunca produz cx/cy/w/h fora de [0,1].
        cx, cy, w, h = mod.xyxy_to_normalized_cxcywh((-50.0, -50.0, 700.0, 550.0), 640, 480)
        assert 0.0 <= cx <= 1.0
        assert 0.0 <= cy <= 1.0
        assert 0.0 <= w <= 1.0
        assert 0.0 <= h <= 1.0

    def test_invalid_image_dimensions_raise(self, mod) -> None:
        with pytest.raises(ValueError):
            mod.xyxy_to_normalized_cxcywh((0.0, 0.0, 10.0, 10.0), 0, 480)


class TestTopKByScore:
    def test_keeps_highest_scores_first(self, mod) -> None:
        dets = [{"score": 0.2}, {"score": 0.9}, {"score": 0.5}]
        top = mod.top_k_by_score(dets, 2)
        assert [d["score"] for d in top] == [0.9, 0.5]

    def test_k_larger_than_list_returns_all_sorted(self, mod) -> None:
        dets = [{"score": 0.1}, {"score": 0.7}]
        top = mod.top_k_by_score(dets, 10)
        assert [d["score"] for d in top] == [0.7, 0.1]

    def test_k_zero_or_negative_returns_all_sorted_no_cut(self, mod) -> None:
        dets = [{"score": 0.1}, {"score": 0.7}, {"score": 0.4}]
        top = mod.top_k_by_score(dets, 0)
        assert [d["score"] for d in top] == [0.7, 0.4, 0.1]

    def test_empty_list_returns_empty(self, mod) -> None:
        assert mod.top_k_by_score([], 5) == []


class TestBuildFinding:
    def test_shape_matches_callback_contract(self, mod) -> None:
        term = {"label": "Capacete de Segurança", "query": "safety helmet"}
        finding = mod.build_finding("frame-1", term, 0.4321, (0.5, 0.5, 0.1, 0.2))
        assert finding == {
            "frame_id": "frame-1",
            "term": "safety helmet",
            "label": "Capacete de Segurança",
            "bbox": [0.5, 0.5, 0.1, 0.2],
            "confidence": 0.4321,
        }

    def test_confidence_rounded_to_4_decimals(self, mod) -> None:
        term = {"label": "x", "query": "y"}
        finding = mod.build_finding("f", term, 0.123456789, (0.1, 0.1, 0.1, 0.1))
        assert finding["confidence"] == 0.1235


class TestModuleConstants:
    def test_owlv2_model_id_and_revision_are_pinned(self, mod) -> None:
        assert mod.OWLV2_MODEL_ID == "google/owlv2-base-patch16-ensemble"
        assert len(mod.OWLV2_REVISION) == 40  # commit sha (git), nunca "main"

    def test_default_confidence_threshold_matches_env_default(self, mod) -> None:
        assert mod.CONFIDENCE_THRESHOLD == pytest.approx(0.15)
