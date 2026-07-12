"""Tests: eval_metrics.py — IoU/greedy matching/AP/confusion matrix (WS-C1)."""
from __future__ import annotations

from app.domain.services.eval_metrics import (
    average_precision,
    confusion_matrix,
    greedy_match,
    iou_xywh,
    merge_confusion_matrices,
    merge_match_results,
    precision_recall_map,
)


class TestIouXywh:
    def test_identical_boxes_iou_1(self):
        assert iou_xywh([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0

    def test_no_overlap_iou_0(self):
        assert iou_xywh([0, 0, 10, 10], [100, 100, 10, 10]) == 0.0

    def test_partial_overlap(self):
        # dois quadrados 10x10 sobrepostos em 5x10 -> inter=50, union=150
        result = iou_xywh([0, 0, 10, 10], [5, 0, 10, 10])
        assert abs(result - 50 / 150) < 1e-9

    def test_full_containment(self):
        outer = [0, 0, 10, 10]
        inner = [2, 2, 4, 4]
        # inter = área do menor (16), union = área do maior (100)
        assert abs(iou_xywh(outer, inner) - 16 / 100) < 1e-9


class TestGreedyMatch:
    def test_perfect_match_single_class(self):
        preds = [{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        gts = [{"class": "helmet", "bbox": [0, 0, 10, 10]}]
        result = greedy_match(preds, gts)
        assert result["helmet"]["tp"] == 1
        assert result["helmet"]["fp"] == 0
        assert result["helmet"]["fn"] == 0

    def test_false_positive_no_gt(self):
        preds = [{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        gts: list[dict] = []
        result = greedy_match(preds, gts)
        assert result["helmet"]["tp"] == 0
        assert result["helmet"]["fp"] == 1
        assert result["helmet"]["n_gt"] == 0

    def test_false_negative_missed_gt(self):
        preds: list[dict] = []
        gts = [{"class": "helmet", "bbox": [0, 0, 10, 10]}]
        result = greedy_match(preds, gts)
        assert result["helmet"]["fn"] == 1
        assert result["helmet"]["tp"] == 0

    def test_no_cross_class_matching(self):
        """Pred de uma classe nunca casa com GT de outra classe."""
        preds = [{"class": "vest", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        gts = [{"class": "no_vest", "bbox": [0, 0, 10, 10]}]
        result = greedy_match(preds, gts)
        assert result["vest"]["tp"] == 0
        assert result["vest"]["fp"] == 1
        assert result["no_vest"]["fn"] == 1

    def test_confidence_tie_break_higher_confidence_wins_best_gt(self):
        """Duas preds da mesma classe competindo por um único GT — a de
        maior confiança (processada primeiro) fica com o TP."""
        preds = [
            {"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]},
            {"class": "helmet", "confidence": 0.5, "bbox": [0, 0, 10, 10]},
        ]
        gts = [{"class": "helmet", "bbox": [0, 0, 10, 10]}]
        result = greedy_match(preds, gts)
        assert result["helmet"]["tp"] == 1
        assert result["helmet"]["fp"] == 1
        matches = result["helmet"]["matches"]
        assert matches[0] == (0.9, True)
        assert matches[1] == (0.5, False)

    def test_below_iou_threshold_is_false_positive(self):
        preds = [{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        gts = [{"class": "helmet", "bbox": [50, 50, 10, 10]}]
        result = greedy_match(preds, gts, iou_threshold=0.5)
        assert result["helmet"]["tp"] == 0
        assert result["helmet"]["fp"] == 1
        assert result["helmet"]["fn"] == 1


class TestAveragePrecision:
    def test_no_gt_returns_zero(self):
        assert average_precision([(0.9, True)], n_gt=0) == 0.0

    def test_no_matches_returns_zero(self):
        assert average_precision([], n_gt=5) == 0.0

    def test_perfect_detections_ap_is_1(self):
        matches = [(0.9, True), (0.8, True), (0.7, True)]
        assert average_precision(matches, n_gt=3) == 1.0

    def test_all_false_positives_ap_is_0(self):
        matches = [(0.9, False), (0.8, False)]
        assert average_precision(matches, n_gt=2) == 0.0


class TestPrecisionRecallMap:
    def test_map_averages_only_classes_with_gt(self):
        matches_by_class = greedy_match(
            preds=[
                {"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]},
                {"class": "vest", "confidence": 0.8, "bbox": [0, 0, 10, 10]},
            ],
            gts=[
                {"class": "helmet", "bbox": [0, 0, 10, 10]},
                # "vest" sem GT no split — classe deve aparecer com ap=None
            ],
        )
        result = precision_recall_map(matches_by_class)
        assert result["per_class"]["helmet"]["ap"] == 1.0
        assert result["per_class"]["vest"]["ap"] is None
        assert result["map50"] == 1.0  # média só considera helmet


class TestMergeMatchResults:
    def test_merges_and_resorts_by_confidence_across_images(self):
        image_1 = greedy_match(
            preds=[{"class": "helmet", "confidence": 0.5, "bbox": [0, 0, 10, 10]}],
            gts=[{"class": "helmet", "bbox": [0, 0, 10, 10]}],
        )
        image_2 = greedy_match(
            preds=[{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}],
            gts=[{"class": "helmet", "bbox": [0, 0, 10, 10]}],
        )
        merged = merge_match_results([image_1, image_2])
        assert merged["helmet"]["n_gt"] == 2
        assert merged["helmet"]["tp"] == 2
        # reordenado por confiança desc, não pela ordem de merge das imagens
        assert merged["helmet"]["matches"][0][0] == 0.9
        assert merged["helmet"]["matches"][1][0] == 0.5

    def test_merges_classes_absent_from_some_images(self):
        image_1 = greedy_match(
            preds=[{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}],
            gts=[{"class": "helmet", "bbox": [0, 0, 10, 10]}],
        )
        image_2 = greedy_match(
            preds=[{"class": "vest", "confidence": 0.8, "bbox": [0, 0, 10, 10]}],
            gts=[{"class": "vest", "bbox": [0, 0, 10, 10]}],
        )
        merged = merge_match_results([image_1, image_2])
        assert merged["helmet"]["n_gt"] == 1
        assert merged["vest"]["n_gt"] == 1


class TestMergeConfusionMatrices:
    def test_sums_counts_across_images(self):
        m1 = confusion_matrix(
            preds=[{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}],
            gts=[{"class": "helmet", "bbox": [0, 0, 10, 10]}],
        )
        m2 = confusion_matrix(
            preds=[{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}],
            gts=[{"class": "helmet", "bbox": [0, 0, 10, 10]}],
        )
        merged = merge_confusion_matrices([m1, m2])
        assert merged["helmet"]["helmet"] == 2


class TestConfusionMatrix:
    def test_correct_prediction_diagonal(self):
        preds = [{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        gts = [{"class": "helmet", "bbox": [0, 0, 10, 10]}]
        matrix = confusion_matrix(preds, gts)
        assert matrix["helmet"]["helmet"] == 1

    def test_cross_class_confusion_recorded(self):
        """greedy_match NÃO detecta isso (casa só por classe) — confusion_matrix sim."""
        preds = [{"class": "vest", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        gts = [{"class": "no_vest", "bbox": [0, 0, 10, 10]}]
        matrix = confusion_matrix(preds, gts)
        assert matrix["no_vest"]["vest"] == 1

    def test_false_positive_background_row(self):
        preds = [{"class": "helmet", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
        gts: list[dict] = []
        matrix = confusion_matrix(preds, gts)
        assert matrix["background"]["helmet"] == 1

    def test_false_negative_background_column(self):
        preds: list[dict] = []
        gts = [{"class": "helmet", "bbox": [0, 0, 10, 10]}]
        matrix = confusion_matrix(preds, gts)
        assert matrix["helmet"]["background"] == 1
