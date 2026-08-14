"""Self-check das métricas por classe do remote_train (stdlib-puro, sem GPU).

Cobre a lógica não-trivial que roda no pod pago: IoU, matcher greedy
tp/fp/fn -> P/R/F1, e a contagem de suporte por split a partir dos COCO.
Roda direto (`python3 test_remote_train_metrics.py`) ou via pytest.
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "remote_train", Path(__file__).with_name("remote_train.py"))
rt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rt)


def test_iou():
    assert rt._iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert rt._iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    # meia sobreposição: inter=50, union=150 -> 1/3
    assert abs(rt._iou((0, 0, 10, 10), (5, 0, 15, 10)) - (50 / 150)) < 1e-6


def test_match_and_score_perfect_and_miss():
    # cat 1: 1 GT + 1 pred casado -> tp. cat 2: 1 GT sem pred -> fn.
    # cat 1 extra pred sem GT -> fp.
    gt = {1: [(1, (0, 0, 10, 10)), (2, (50, 50, 60, 60))]}
    pred = {1: [(1, (0, 0, 10, 10)), (1, (100, 100, 110, 110))]}
    per_cat, conf = rt._match_and_score(gt, pred)
    assert per_cat[1] == {"tp": 1, "fp": 1, "fn": 0}
    assert per_cat[2] == {"tp": 0, "fp": 0, "fn": 1}
    prf1 = rt._prf(**{k: per_cat[1][k] for k in ("tp", "fp", "fn")})
    assert prf1["precision"] == 0.5 and prf1["recall"] == 1.0
    prf2 = rt._prf(**{k: per_cat[2][k] for k in ("tp", "fp", "fn")})
    assert prf2["recall"] == 0.0 and prf2["f1"] == 0.0


def test_confusion_wrong_class_on_overlap():
    # pred cat 2 sobre a caixa de uma GT cat 1 -> fp de 2 + confusão 1->2
    gt = {1: [(1, (0, 0, 10, 10))]}
    pred = {1: [(2, (0, 0, 10, 10))]}
    per_cat, conf = rt._match_and_score(gt, pred)
    assert per_cat[2]["fp"] == 1
    assert per_cat[1]["fn"] == 1
    assert conf[(1, 2)] == 1


def test_count_coco_support():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "train").mkdir(); (root / "valid").mkdir()
        cats = [{"id": 1, "name": "mascara"}, {"id": 2, "name": "Botas"}]
        (root / "train" / rt._COCO_ANN).write_text(json.dumps({
            "categories": cats,
            "images": [{"id": 1}, {"id": 2}],
            "annotations": [
                {"image_id": 1, "category_id": 1, "bbox": [0, 0, 5, 5]},
                {"image_id": 1, "category_id": 1, "bbox": [6, 6, 5, 5]},
                {"image_id": 2, "category_id": 2, "bbox": [0, 0, 5, 5]},
            ],
        }))
        (root / "valid" / rt._COCO_ANN).write_text(json.dumps({
            "categories": cats,
            "images": [{"id": 9}],
            "annotations": [{"image_id": 9, "category_id": 1, "bbox": [0, 0, 5, 5]}],
        }))
        sup = rt.count_coco_support(root)
        assert sup["mascara"] == {"train_boxes": 2, "val_boxes": 1, "test_boxes": 0,
                                  "train_imgs": 1, "val_imgs": 1, "test_imgs": 0}
        assert sup["Botas"] == {"train_boxes": 1, "val_boxes": 0, "test_boxes": 0,
                                "train_imgs": 1, "val_imgs": 0, "test_imgs": 0}


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print("ok", fn.__name__)
    print(f"\n{len(fns)} checks passaram")
    sys.exit(0)
