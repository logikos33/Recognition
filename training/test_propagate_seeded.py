"""
Tests: propagate_seeded.py — funções PURAS de matching (sem GPU/torch).

propagate_seeded.py roda NA GPU remota (zero import do pacote app/) —
importado aqui via importlib a partir do path do arquivo, mesmo padrão de
training/vast/test_remote_train.py. Cobre só a seção "pure matching" do
módulo (cosine_similarity, best_class_for_embedding, mask_bbox_to_
normalized, denormalize_bbox, build_proposal, download_and_verify_weight) —
o caminho GPU real (embed_crop, load_dinov2, load_sam_mask_generator,
build_pool_proposals) faz import lazy de torch/cv2/segment_anything DENTRO
das próprias funções, então importar o módulo aqui não exige nenhuma
dessas dependências instaladas.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).parent / "propagate_seeded.py"


@pytest.fixture
def mod(tmp_path, monkeypatch):
    """Importa propagate_seeded.py isolado, com WORK_DIR em tmp_path (o
    módulo real usa /root — não pode rodar em máquina de dev/CI)."""
    spec = importlib.util.spec_from_file_location(
        "propagate_seeded_under_test", _MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["propagate_seeded_under_test"] = module
    spec.loader.exec_module(module)

    monkeypatch.setattr(module, "WORK_DIR", tmp_path)

    yield module
    sys.modules.pop("propagate_seeded_under_test", None)


class TestCosineSimilarity:
    def test_identical_vectors_similarity_one(self, mod) -> None:
        v = [1.0, 2.0, 3.0]
        assert mod.cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_similarity_zero(self, mod) -> None:
        assert mod.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors_similarity_negative_one(self, mod) -> None:
        assert mod.cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_empty_vectors_return_zero_never_raises(self, mod) -> None:
        assert mod.cosine_similarity([], []) == 0.0

    def test_mismatched_length_returns_zero_never_raises(self, mod) -> None:
        assert mod.cosine_similarity([1.0, 2.0], [1.0]) == 0.0

    def test_zero_norm_vector_returns_zero_never_raises(self, mod) -> None:
        assert mod.cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


class TestBestClassForEmbedding:
    def test_picks_class_with_highest_average_similarity(self, mod) -> None:
        embedding = [1.0, 0.0]
        exemplars = {
            "capacete": [[1.0, 0.0], [0.9, 0.1]],
            "bota": [[0.0, 1.0]],
        }
        class_name, score = mod.best_class_for_embedding(embedding, exemplars, 0.5)
        assert class_name == "capacete"
        assert score > 0.9

    def test_below_threshold_returns_none(self, mod) -> None:
        embedding = [1.0, 0.0]
        exemplars = {"bota": [[0.0, 1.0]]}
        class_name, score = mod.best_class_for_embedding(embedding, exemplars, 0.5)
        assert class_name is None
        assert score == pytest.approx(0.0)

    def test_noisy_single_exemplar_averaged_out(self, mod) -> None:
        """Uma classe com 1 exemplar ruidoso perde pra outra com 2
        exemplares consistentemente próximos — média, não só o melhor par."""
        embedding = [1.0, 0.0]
        exemplars = {
            "ruidosa": [[1.0, 0.0]],  # 1 exemplar perfeito, mas sozinho
            "consistente": [[0.95, 0.05], [0.93, 0.07]],
        }
        class_name, _score = mod.best_class_for_embedding(embedding, exemplars, 0.5)
        assert class_name == "ruidosa"  # ainda vence (score médio maior)

    def test_empty_exemplars_dict_returns_none(self, mod) -> None:
        class_name, score = mod.best_class_for_embedding([1.0, 0.0], {}, 0.5)
        assert class_name is None
        assert score == 0.0

    def test_class_with_empty_exemplar_list_is_skipped(self, mod) -> None:
        exemplars = {"vazia": [], "capacete": [[1.0, 0.0]]}
        class_name, _score = mod.best_class_for_embedding([1.0, 0.0], exemplars, 0.5)
        assert class_name == "capacete"


class TestBboxConversions:
    def test_mask_bbox_to_normalized_roundtrip_with_denormalize(self, mod) -> None:
        img_w, img_h = 640, 480
        bbox_xywh = (100.0, 50.0, 80.0, 60.0)  # x, y, w, h absolutos
        normalized = mod.mask_bbox_to_normalized(bbox_xywh, img_w, img_h)
        cx, cy, w, h = normalized
        assert 0.0 <= cx <= 1.0
        assert 0.0 <= cy <= 1.0
        assert 0.0 < w <= 1.0
        assert 0.0 < h <= 1.0

        x0, y0, x1, y1 = mod.denormalize_bbox(normalized, img_w, img_h)
        # Tolerância de arredondamento (round-trip float -> normalizado -> pixel)
        assert abs(x0 - 100) <= 2
        assert abs(y0 - 50) <= 2
        assert abs((x1 - x0) - 80) <= 2
        assert abs((y1 - y0) - 60) <= 2

    def test_mask_bbox_to_normalized_clamps_to_unit_range(self, mod) -> None:
        # Bbox que extrapola a imagem (x+w > img_w) — resultado sempre em [0,1]
        cx, cy, w, h = mod.mask_bbox_to_normalized((600.0, 400.0, 200.0, 200.0), 640, 480)
        assert 0.0 <= cx <= 1.0
        assert 0.0 <= cy <= 1.0
        assert 0.0 < w <= 1.0
        assert 0.0 < h <= 1.0

    def test_mask_bbox_to_normalized_raises_on_invalid_image_dims(self, mod) -> None:
        with pytest.raises(ValueError, match="dimensões"):
            mod.mask_bbox_to_normalized((0.0, 0.0, 10.0, 10.0), 0, 480)

    def test_denormalize_bbox_never_yields_degenerate_box(self, mod) -> None:
        x0, y0, x1, y1 = mod.denormalize_bbox((0.5, 0.5, 0.0, 0.0), 640, 480)
        assert x1 > x0
        assert y1 > y0

    def test_denormalize_bbox_clamps_to_image_bounds(self, mod) -> None:
        x0, y0, x1, y1 = mod.denormalize_bbox((0.99, 0.99, 0.5, 0.5), 640, 480)
        assert 0 <= x0 <= 640
        assert 0 <= y0 <= 480
        assert x1 <= 640
        assert y1 <= 480


class TestBuildProposal:
    def test_shape_matches_pre_annotations_contract(self, mod) -> None:
        proposal = mod.build_proposal("capacete", 0.87654, (0.5, 0.4, 0.1, 0.2))
        assert set(proposal.keys()) == {"bbox", "class", "confidence"}
        assert proposal["class"] == "capacete"
        assert proposal["bbox"] == [0.5, 0.4, 0.1, 0.2]
        assert proposal["confidence"] == 0.8765  # arredondado 4 casas

    def test_bbox_is_list_not_tuple(self, mod) -> None:
        """AnnotationService.get_frame_annotations indexa bbox[0..3] —
        precisa ser subscritável (list serializa limpo em JSON; tupla
        também funcionaria, mas o contrato real grava JSON puro)."""
        proposal = mod.build_proposal("bota", 0.5, (0.1, 0.2, 0.3, 0.4))
        assert isinstance(proposal["bbox"], list)
        assert len(proposal["bbox"]) == 4


class TestDownloadAndVerifyWeight:
    def test_raises_without_url(self, mod, tmp_path) -> None:
        with pytest.raises(mod.WeightVerificationError, match="URL de download ausente"):
            mod.download_and_verify_weight("", "abc123", tmp_path / "w.pth", "TesteModel")

    def test_raises_without_expected_hash(self, mod, tmp_path) -> None:
        with pytest.raises(mod.WeightVerificationError, match="sha256 esperado ausente"):
            mod.download_and_verify_weight(
                "https://example.com/w.pth", "", tmp_path / "w.pth", "TesteModel",
            )

    def test_raises_on_sha256_mismatch_and_never_returns_path(
        self, mod, tmp_path, monkeypatch,
    ) -> None:
        """Falha-antes/passa-depois do guard: sem a verificação, qualquer
        arquivo baixado seria aceito como o peso certo."""
        captured_bytes = b"conteudo-adulterado-ou-corrompido"

        def _fake_download(url, dest, timeout=600):  # noqa: ARG001
            dest.write_bytes(captured_bytes)

        monkeypatch.setattr(mod, "download", _fake_download)
        wrong_hash = "0" * 64

        with pytest.raises(mod.WeightVerificationError, match="sha256 divergente"):
            mod.download_and_verify_weight(
                "https://example.com/w.pth", wrong_hash, tmp_path / "w.pth", "TesteModel",
            )

    def test_accepts_matching_sha256(self, mod, tmp_path, monkeypatch) -> None:
        content = b"peso-verificado-de-verdade"
        expected = hashlib.sha256(content).hexdigest()

        def _fake_download(url, dest, timeout=600):  # noqa: ARG001
            dest.write_bytes(content)

        monkeypatch.setattr(mod, "download", _fake_download)
        dest = tmp_path / "w.pth"

        result = mod.download_and_verify_weight(
            "https://example.com/w.pth", expected, dest, "TesteModel",
        )
        assert result == dest
        assert dest.read_bytes() == content

    def test_hash_comparison_is_case_insensitive(self, mod, tmp_path, monkeypatch) -> None:
        content = b"peso-verificado"
        expected_upper = hashlib.sha256(content).hexdigest().upper()

        def _fake_download(url, dest, timeout=600):  # noqa: ARG001
            dest.write_bytes(content)

        monkeypatch.setattr(mod, "download", _fake_download)
        mod.download_and_verify_weight(
            "https://example.com/w.pth", expected_upper, tmp_path / "w.pth", "TesteModel",
        )  # não levanta


class TestMainAbortsFailClosedWithoutManifest:
    def test_main_raises_without_manifest_url(self, mod, monkeypatch) -> None:
        monkeypatch.setattr(mod, "MANIFEST_URL", "")
        with pytest.raises(RuntimeError, match="MANIFEST_URL"):
            mod.main()

    def test_main_raises_without_seeds(self, mod, monkeypatch) -> None:
        monkeypatch.setattr(mod, "MANIFEST_URL", "https://example.com/manifest.json")
        monkeypatch.setattr(mod, "download_json", lambda url, timeout=60: {"seeds": [], "pool": [{"frame_id": "f1", "image_url": "x"}]})  # noqa: E501
        with pytest.raises(RuntimeError, match="sem sementes"):
            mod.main()

    def test_main_raises_without_pool(self, mod, monkeypatch) -> None:
        monkeypatch.setattr(mod, "MANIFEST_URL", "https://example.com/manifest.json")
        monkeypatch.setattr(
            mod, "download_json",
            lambda url, timeout=60: {
                "seeds": [{"frame_id": "f0", "image_url": "x", "boxes": []}], "pool": [],
            },
        )
        with pytest.raises(RuntimeError, match="sem pool"):
            mod.main()
