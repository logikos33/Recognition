"""
Unit tests: operações canônicas do cenário RVB multi-módulo (tasks 109/110, ADR-0053).

- CrowdZoneOperation: aglomeração N+ objetos × M frames consecutivos
- DwellZoneOperation: permanência atípica (terminologia neutra, sem claim de furto)
- AttentionPointsOperation: multi-atributo por ROI → payload monofatura
- StageTimerOperation: cronômetro de etapa (entrada → saída, grace de oclusão)
"""
from app.domain.services.operations.canonical.attention_points import (
    AttentionPointsOperation,
)
from app.domain.services.operations.canonical.crowd_zone import CrowdZoneOperation
from app.domain.services.operations.canonical.dwell_zone import DwellZoneOperation
from app.domain.services.operations.canonical.stage_timer import StageTimerOperation
from app.domain.services.operations.registry import OperationTypeRegistry

FULL_ZONE = [[0, 0], [1, 0], [1, 1], [0, 1]]
META = {"width": 640, "height": 360}


def _person(cx_px=320, cy_px=180, conf=0.9, track_id=None):
    det = {"class": "person", "confidence": conf, "bbox": [cx_px - 10, cy_px - 10, 20, 20]}
    if track_id is not None:
        det["track_id"] = track_id
    return det


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_new_operations_registered():
    counting = {c["type_id"] for c in OperationTypeRegistry.to_catalog("counting")}
    quality = {c["type_id"] for c in OperationTypeRegistry.to_catalog("quality")}
    assert {"crowd_zone", "dwell_zone"} <= counting
    assert {"attention_points", "stage_timer"} <= quality


# ---------------------------------------------------------------------------
# CrowdZone (task-110)
# ---------------------------------------------------------------------------

def test_crowd_zone_requires_persistence():
    op = CrowdZoneOperation(
        {"zone_points": FULL_ZONE, "target_class": "person", "min_count": 2, "min_frames": 3}
    )
    state: dict = {}
    dets = [_person(100, 100), _person(300, 200)]
    for i in range(2):  # 2 frames < min_frames=3
        out = op.evaluate(dets, META, state)
        state = out["state_next"]
        assert out["condition_satisfied"] is False
    out = op.evaluate(dets, META, state)  # 3º frame consecutivo
    assert out["condition_satisfied"] is True
    assert out["result"]["count_in_zone"] == 2


def test_crowd_zone_resets_on_dispersal():
    op = CrowdZoneOperation(
        {"zone_points": FULL_ZONE, "target_class": "person", "min_count": 2, "min_frames": 2}
    )
    state = op.evaluate([_person(), _person(300, 200)], META, {})["state_next"]
    out = op.evaluate([_person()], META, state)  # dispersou
    assert out["state_next"]["consecutive"] == 0
    assert out["condition_satisfied"] is False


def test_crowd_zone_validate():
    op = CrowdZoneOperation({})
    errors = op.validate_config({"zone_points": [[0, 0]], "min_count": 1})
    assert any("zone_points" in e for e in errors)
    assert any("target_class" in e for e in errors)
    assert any("min_count" in e for e in errors)


# ---------------------------------------------------------------------------
# DwellZone (task-110)
# ---------------------------------------------------------------------------

def test_dwell_zone_triggers_after_limit_with_track_id():
    op = DwellZoneOperation(
        {"zone_points": FULL_ZONE, "target_class": "person", "max_dwell_seconds": 10}
    )
    state: dict = {}
    out = op.evaluate([_person(track_id=7)], {**META, "timestamp": 0.0}, state)
    assert out["condition_satisfied"] is False
    out = op.evaluate([_person(track_id=7)], {**META, "timestamp": 11.0}, out["state_next"])
    assert out["condition_satisfied"] is True
    assert out["result"]["objects_over_limit"][0]["dwell_seconds"] == 11.0


def test_dwell_zone_grace_covers_short_occlusion():
    op = DwellZoneOperation(
        {"zone_points": FULL_ZONE, "target_class": "person",
         "max_dwell_seconds": 10, "grace_seconds": 3}
    )
    s = op.evaluate([_person(track_id=1)], {**META, "timestamp": 0.0}, {})["state_next"]
    s = op.evaluate([], {**META, "timestamp": 2.0}, s)["state_next"]  # oclusão < grace
    assert "t1" in s["dwell"], "oclusão curta não pode expulsar o objeto"
    s = op.evaluate([], {**META, "timestamp": 6.0}, s)["state_next"]  # > grace
    assert "t1" not in s["dwell"], "ausência longa deve expirar o objeto"


def test_dwell_zone_result_uses_neutral_terminology():
    """v1 faseado: nenhuma claim de furto no output (ADR-0053)."""
    op = DwellZoneOperation(
        {"zone_points": FULL_ZONE, "target_class": "person", "max_dwell_seconds": 1}
    )
    out = op.evaluate([_person(track_id=1)], {**META, "timestamp": 0.0}, {})
    text = str(out) + op.description + op.type_label
    assert "furto" not in text.lower()
    assert "theft" not in text.lower()


# ---------------------------------------------------------------------------
# AttentionPoints (task-109)
# ---------------------------------------------------------------------------

ROI_LEFT = [[0, 0], [0.5, 0], [0.5, 1], [0, 1]]
ROI_RIGHT = [[0.5, 0], [1, 0], [1, 1], [0.5, 1]]


def test_attention_points_present_and_absent():
    op = AttentionPointsOperation({
        "points": [
            {"name": "solda_ok", "roi": ROI_LEFT, "target_class": "weld",
             "ok_when": "present", "min_confidence": 0.5},
            {"name": "sem_defeito", "roi": ROI_RIGHT, "target_class": "defect",
             "ok_when": "absent", "min_confidence": 0.5},
        ]
    })
    dets = [
        {"class": "weld", "confidence": 0.8, "bbox": [150, 170, 20, 20]},     # ROI esquerda
        {"class": "defect", "confidence": 0.9, "bbox": [470, 170, 20, 20]},   # ROI direita
    ]
    out = op.evaluate(dets, META, {})
    attrs = {a["name"]: a for a in out["result"]["attributes"]}
    assert attrs["solda_ok"]["ok"] is True
    assert attrs["solda_ok"]["confidence"] == 0.8
    assert attrs["sem_defeito"]["ok"] is False, "defeito presente → atributo falha"
    assert out["result"]["ok"] is False
    assert out["condition_satisfied"] is True  # há falha → dispara


def test_attention_points_all_ok_feeds_monofatura_shape():
    op = AttentionPointsOperation({
        "points": [{"name": "peca_presente", "roi": FULL_ZONE, "target_class": "piece",
                    "ok_when": "present"}]
    })
    out = op.evaluate(
        [{"class": "piece", "confidence": 0.7, "bbox": [300, 170, 20, 20]}], META, {}
    )
    # shape consumido por InspectionService.complete_stage (task-108)
    assert set(out["result"].keys()) == {"ok", "attributes"}
    assert out["result"]["ok"] is True


def test_attention_points_validate_duplicates():
    op = AttentionPointsOperation({})
    errors = op.validate_config({
        "points": [
            {"name": "a", "roi": ROI_LEFT, "target_class": "x", "ok_when": "present"},
            {"name": "a", "roi": ROI_LEFT, "target_class": "x", "ok_when": "nope"},
        ]
    })
    assert any("duplicado" in e for e in errors)
    assert any("ok_when" in e for e in errors)


# ---------------------------------------------------------------------------
# StageTimer (task-109)
# ---------------------------------------------------------------------------

def test_stage_timer_full_cycle():
    op = StageTimerOperation(
        {"zone_points": FULL_ZONE, "target_class": "piece", "exit_grace_seconds": 2}
    )
    piece = {"class": "piece", "confidence": 0.9, "bbox": [300, 170, 20, 20]}
    s = op.evaluate([piece], {**META, "timestamp": 10.0}, {})["state_next"]   # entra
    out = op.evaluate([piece], {**META, "timestamp": 40.0}, s)
    assert out["result"]["running_seconds"] == 30.0
    s = out["state_next"]
    s = op.evaluate([], {**META, "timestamp": 41.0}, s)["state_next"]         # some < grace
    out = op.evaluate([], {**META, "timestamp": 44.0}, s)                     # saiu de fato
    assert out["condition_satisfied"] is True
    assert out["result"]["completed_elapsed_s"] == 30.0, (
        "tempo da etapa = última presença (40s) - entrada (10s)"
    )
    assert out["result"]["piece_in_stage"] is False


def test_stage_timer_occlusion_does_not_close_stage():
    op = StageTimerOperation(
        {"zone_points": FULL_ZONE, "target_class": "piece", "exit_grace_seconds": 5}
    )
    piece = {"class": "piece", "confidence": 0.9, "bbox": [300, 170, 20, 20]}
    s = op.evaluate([piece], {**META, "timestamp": 0.0}, {})["state_next"]
    out = op.evaluate([], {**META, "timestamp": 3.0}, s)   # oclusão < grace
    assert out["condition_satisfied"] is False
    assert out["result"]["piece_in_stage"] is True
