"""Testes: coverage_service — metas, ranking de lacunas, avisos (Volta 1).

Puro Python (sem banco): alimenta build_coverage com um `raw` sintético e
verifica as decisões que a tela desenha.
"""
from app.domain.services import coverage_service as cs


def _cell(class_id, name, cam_id, cam_name, boxes, images, order=0):
    return {
        "class_id": class_id, "class_name": name, "color": "#111",
        "display_order": order, "camera_id": cam_id, "camera_name": cam_name,
        "boxes": boxes, "images": images,
    }


def _raw():
    classes = [
        {"class_id": 1, "class_name": "A", "color": "#1", "display_order": 0},
        {"class_id": 2, "class_name": "B", "color": "#2", "display_order": 1},
        {"class_id": 3, "class_name": "Z", "color": "#3", "display_order": 2},
        {"class_id": 4, "class_name": "M", "color": "#4", "display_order": 4},
    ]
    cameras = [
        {"camera_id": "c1", "camera_name": "Cam1", "is_active": True, "available_frames": 200},
        {"camera_id": "c2", "camera_name": "Cam2", "is_active": True, "available_frames": 50},
        {"camera_id": "c3", "camera_name": "Cam3", "is_active": True, "available_frames": 0},
        {"camera_id": "c4", "camera_name": "CamOff", "is_active": False, "available_frames": 200},
        {"camera_id": "c5", "camera_name": "Cam5", "is_active": True, "available_frames": 200},
    ]
    cells = [
        # A: concentrada (200 numa câmera, espalhada em 4) → status "concentracao"
        _cell(1, "A", "c1", "Cam1", 200, 150), _cell(1, "A", "c2", "Cam2", 20, 15),
        _cell(1, "A", "c3", "Cam3", 20, 15), _cell(1, "A", "c4", "CamOff", 20, 15),
        # B: minúscula, 1 câmera → status "abaixo_piso"
        _cell(2, "B", "c1", "Cam1", 5, 5, order=1),
        # M: 5 câmeras, 30 cada, share 0.2, 150 img → status "met"
        _cell(4, "M", "c1", "Cam1", 30, 30, order=4), _cell(4, "M", "c2", "Cam2", 30, 30, order=4),
        _cell(4, "M", "c3", "Cam3", 30, 30, order=4), _cell(4, "M", "c4", "CamOff", 30, 30, order=4),
        _cell(4, "M", "c5", "Cam5", 30, 30, order=4),
    ]
    camera_rollup = [
        {"camera_id": "c1", "camera_name": "Cam1", "boxes": 235, "images": 185,
         "classes": 3, "days": 4, "last_annotation": None},
    ]
    return {
        "classes": classes, "cameras": cameras, "cells": cells,
        "camera_rollup": camera_rollup,
        "provenance": [{"class_id": 1, "humana": 240, "auto_aprovada": 20}],
        "orphans": [{"class_id": 0, "class_name": "Capacete", "camera_name": "Cam1", "boxes": 1}],
        "archived_excluded": [{"class_name": "Protetor auricular", "boxes": 18}],
        "totals": {"boxes": 505, "images": 380},
    }


def test_zero_class_appears_as_row():
    out = cs.build_coverage(_raw())
    zed = next(r for r in out["classes"] if r["class_name"] == "Z")
    assert zed["boxes"] == 0 and zed["images"] == 0
    assert zed["status"] == "abaixo_piso"


def test_status_classification():
    rows = {r["class_name"]: r for r in cs.build_coverage(_raw())["classes"]}
    assert rows["M"]["status"] == "met"
    assert rows["A"]["status"] == "concentracao"   # share 200/260 > 0.5
    assert rows["B"]["status"] == "abaixo_piso"
    assert rows["A"]["max_camera_share"] > 0.5


def test_totals_and_counts_match_export_passthrough():
    out = cs.build_coverage(_raw())
    # totals vêm crus do repo (que conta = export) — não recalculados aqui.
    assert out["totals"]["boxes"] == 505
    assert out["totals"]["images"] == 380
    assert out["totals"]["classes_met"] == 1


def test_gap_ranking_excludes_filled_and_inactive_and_flags_collection():
    out = cs.build_coverage(_raw())
    gaps = out["gaps"]
    # nunca sugere uma célula que já existe (A já está em c1)
    assert not any(g["class_id"] == 1 and g["camera_id"] == "c1" for g in gaps)
    # câmera inativa (c4) nunca entra no ranking
    assert not any(g["camera_id"] == "c4" for g in gaps)
    # gap numa câmera ativa sem frames (c3) é marcado como precisa coletar
    c3 = [g for g in gaps if g["camera_id"] == "c3"]
    assert all(g["reason"] == "⚠️ precisa coletar" for g in c3)
    # classe abaixo de M câmeras (A: 4<5) numa câmera ativa com frames → amplia cobertura
    assert any(g["class_name"] == "A" and g["reason"] == "amplia cobertura"
               and g["available_frames"] > 0 for g in gaps)


def test_needs_collection_flags_active_camera_without_frames():
    out = cs.build_coverage(_raw())
    names = {c["camera_name"] for c in out["needs_collection"]}
    assert "Cam3" in names            # ativa, avail 0
    assert "CamOff" not in names      # inativa não conta


def test_imbalance_and_warnings():
    out = cs.build_coverage(_raw())
    assert out["imbalance"]["ratio"] >= 10
    assert out["imbalance"]["low"]["name"] == "B"
    assert out["warnings"]["orphan_boxes"] == 1
    assert out["warnings"]["orphans"][0]["class_name"] == "Capacete"
    assert out["warnings"]["archived_excluded"][0]["boxes"] == 18
