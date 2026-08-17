"""Cobertura de anotação por câmera — metas, ranking de lacunas, avisos.

Consome os blocos crus de AnnotationRepository.get_coverage_matrix (que já
conta IGUAL ao export de treino) e produz a estrutura que a tela desenha:
matriz classe × câmera com células zeradas visíveis, cada classe pintada
contra a meta, e o ranking das lacunas que mais destravam a próxima volta.

Puro Python, sem I/O — testável sem banco.

Metas (derivação no PR / REGISTRO D-104):
  N_IMAGES=100 · M_CAMERAS=5 · MAX_CAMERA_SHARE=0.50
  100 img × 20% de validação = 20 positivos de val por classe → resolução de
  recall ≤5% (contra passos de 17% a k=6, onde F1 0,07 é indistinguível de 0).
  ≥5 câmeras permite validação com câmera RETIDA (mede generalização, não
  decorar ângulo). Teto de 50% ataca a concentração (hoje Canal 8 = 71% de
  Botas). PISO de interpretabilidade (abaixo = ruído): ≥40 img em ≥4 câmeras.
"""
from typing import Any

N_IMAGES = 100
M_CAMERAS = 5
MAX_CAMERA_SHARE = 0.50
FLOOR_IMAGES = 40
FLOOR_CAMERAS = 4
IMBALANCE_RATIO = 10  # alerta quando maior/menor classe passa de ~10×


def _i(v: Any) -> int:
    return int(v) if v is not None else 0


def _class_status(images: int, cameras: int, max_share: float) -> str:
    """met | concentracao | abaixo_meta | abaixo_piso — pinta a linha da classe."""
    if images >= N_IMAGES and cameras >= M_CAMERAS and max_share <= MAX_CAMERA_SHARE:
        return "met"
    if images < FLOOR_IMAGES or cameras < FLOOR_CAMERAS:
        return "abaixo_piso"
    if max_share > MAX_CAMERA_SHARE:
        return "concentracao"
    return "abaixo_meta"


def build_coverage(raw: dict[str, Any]) -> dict[str, Any]:
    classes = raw["classes"]
    cameras = raw["cameras"]
    cells = raw["cells"]
    rollup = {c["camera_id"]: c for c in raw["camera_rollup"]}
    prov = {p["class_id"]: p for p in raw["provenance"]}

    # Índices células por classe e por (classe, câmera).
    by_class: dict[int, list[dict]] = {}
    cell_lookup: dict[tuple[int, Any], dict] = {}
    for cell in cells:
        by_class.setdefault(cell["class_id"], []).append(cell)
        cell_lookup[(cell["class_id"], cell["camera_id"])] = cell

    active_cam_ids = [c["camera_id"] for c in cameras if c["is_active"]]
    avail = {c["camera_id"]: _i(c["available_frames"]) for c in cameras}

    # --- Classes (linhas da matriz) pintadas contra a meta ---
    # Linhas = classes ativas (incl. ZERO) + "stragglers": classes que o export
    # ainda conta mas que saíram da taxonomia ativa (ex.: hardhat, 1 caixa, fora
    # do D-103). Sem elas, a soma das linhas não bateria com o total do export —
    # o mesmo pecado que a tela deve evitar. Ficam marcadas in_taxonomy=False.
    active_ids = {c["class_id"] for c in classes}
    straggler_meta = {}
    for cell in cells:
        if cell["class_id"] not in active_ids:
            straggler_meta.setdefault(cell["class_id"], cell)
    row_specs = [(c, True) for c in classes] + [
        (m, False) for m in straggler_meta.values()
    ]

    class_rows: list[dict] = []
    for cls, in_taxonomy in row_specs:
        cid = cls["class_id"]
        my_cells = by_class.get(cid, [])
        boxes = sum(_i(c["boxes"]) for c in my_cells)
        images = sum(_i(c["images"]) for c in my_cells)
        cams_present = len({c["camera_id"] for c in my_cells})
        max_box = max((_i(c["boxes"]) for c in my_cells), default=0)
        max_share = (max_box / boxes) if boxes else 0.0
        pv = prov.get(cid, {})
        class_rows.append({
            "class_id": cid,
            "class_name": cls["class_name"],
            "color": cls["color"],
            "display_order": cls["display_order"],
            "in_taxonomy": in_taxonomy,
            "boxes": boxes,
            "images": images,
            "cameras_present": cams_present,
            "max_camera_share": round(max_share, 3),
            "humana": _i(pv.get("humana")),
            "auto_aprovada": _i(pv.get("auto_aprovada")),
            "status": "straggler" if not in_taxonomy
                      else _class_status(images, cams_present, max_share),
        })
    class_rows.sort(key=lambda r: (
        r["display_order"] is None, r["display_order"] if r["display_order"] is not None else 0, r["class_id"],
    ))

    # --- Câmeras (colunas) com rollup + classes zeradas ---
    camera_cols: list[dict] = []
    for cam in cameras:
        cam_id = cam["camera_id"]
        r = rollup.get(cam_id, {})
        present = {cell["class_id"] for cell in cells if cell["camera_id"] == cam_id}
        zero = [c["class_name"] for c in classes if c["class_id"] not in present]
        last = r.get("last_annotation")
        camera_cols.append({
            "camera_id": cam_id,
            "camera_name": cam["camera_name"],
            "is_active": cam["is_active"],
            "images": _i(r.get("images")),
            "boxes": _i(r.get("boxes")),
            "classes_present": _i(r.get("classes")),
            "days": _i(r.get("days")),
            "last_annotation": last.isoformat() if hasattr(last, "isoformat") else last,
            "available_frames": avail.get(cam_id, 0),
            "classes_zero": zero,
            "classes_zero_count": len(zero),
        })
    # Câmera com anotação primeiro, depois ativas por frames disponíveis desc.
    camera_cols.sort(key=lambda c: (-c["boxes"], not c["is_active"], -c["available_frames"], c["camera_name"]))

    # --- Células (matriz) — só > 0; o front preenche os zeros ---
    matrix = [{
        "class_id": c["class_id"],
        "camera_id": c["camera_id"],
        "boxes": _i(c["boxes"]),
        "images": _i(c["images"]),
    } for c in cells]

    # --- Ranking das lacunas: (classe, câmera) vazias que mais destravam ---
    # Round-robin por classe: sem isso, a classe mais carente inunda o top-10
    # (10 linhas da mesma classe) e a tela deixa de ser diversa/acionável.
    # Só classes DA taxonomia que ainda não bateram a meta entram.
    cam_name = {c["camera_id"]: c["camera_name"] for c in camera_cols}
    per_class: dict[int, list[dict]] = {}
    for cls in class_rows:
        if not cls["in_taxonomy"] or cls["status"] == "met":
            continue
        img_deficit = max(0.0, (N_IMAGES - cls["images"]) / N_IMAGES)
        cam_deficit = max(0.0, (M_CAMERAS - cls["cameras_present"]) / M_CAMERAS)
        cands = []
        for cam_id in active_cam_ids:
            if (cls["class_id"], cam_id) in cell_lookup:
                continue  # já tem anotação dessa classe nessa câmera
            a = avail.get(cam_id, 0)
            readiness = 1.0 if a >= 20 else 0.5 if a > 0 else 0.1
            score = (cls["max_camera_share"] + img_deficit + cam_deficit) * readiness
            if a == 0:
                reason = "⚠️ precisa coletar"
            elif cls["cameras_present"] < M_CAMERAS:
                reason = "amplia cobertura"
            elif cls["max_camera_share"] > MAX_CAMERA_SHARE:
                reason = "quebra concentração"
            else:
                reason = "reforça volume"
            cands.append({
                "class_id": cls["class_id"], "class_name": cls["class_name"],
                "camera_id": cam_id, "camera_name": cam_name[cam_id],
                "available_frames": a, "score": round(score, 3), "reason": reason,
            })
        cands.sort(key=lambda g: (-g["score"], -g["available_frames"], g["camera_name"]))
        if cands:
            per_class[cls["class_id"]] = cands

    # Classes ordenadas pela prioridade da sua melhor câmera; round-robin até 10.
    ordered = sorted(per_class, key=lambda cid: -per_class[cid][0]["score"])
    top_gaps: list[dict] = []
    rnd = 0
    while len(top_gaps) < 10 and any(len(per_class[c]) > rnd for c in ordered):
        for cid in ordered:
            if len(per_class[cid]) > rnd:
                top_gaps.append(per_class[cid][rnd])
                if len(top_gaps) == 10:
                    break
        rnd += 1

    # --- Câmeras que precisam voltar a coletar (derivado da matriz) ---
    # Ativa e sem material bruto para anotar agora (avail==0), ou "magra"
    # (0 anotações e poucos frames → esgota rápido, precisa de coleta p/ ir fundo).
    needs_collection = [{
        "camera_id": c["camera_id"], "camera_name": c["camera_name"],
        "available_frames": c["available_frames"], "boxes": c["boxes"],
        "reason": "sem frames para anotar" if c["available_frames"] == 0
                  else "material raso (esgota antes da meta)",
    } for c in camera_cols
        if c["is_active"] and (c["available_frames"] == 0
                               or (c["boxes"] == 0 and c["available_frames"] < N_IMAGES))]

    # --- Alerta de desbalanceamento (estende FILTRO §2.3) ---
    # Só classes da taxonomia ativa — um straggler de 1 caixa (hardhat) não deve
    # dominar a razão maior/menor.
    nonzero = [r for r in class_rows if r["boxes"] > 0 and r["in_taxonomy"]]
    imbalance = None
    if len(nonzero) >= 2:
        hi = max(nonzero, key=lambda r: r["boxes"])
        lo = min(nonzero, key=lambda r: r["boxes"])
        ratio = hi["boxes"] / lo["boxes"] if lo["boxes"] else 0
        if ratio >= IMBALANCE_RATIO:
            imbalance = {
                "ratio": round(ratio, 1),
                "high": {"name": hi["class_name"], "boxes": hi["boxes"]},
                "low": {"name": lo["class_name"], "boxes": lo["boxes"]},
            }

    # --- Avisos: caixa órfã (não some) + arquivadas (confirmadas fora) ---
    orphans = raw["orphans"]
    warnings = {
        "orphan_boxes": sum(_i(o["boxes"]) for o in orphans),
        "orphans": [{
            "class_id": o["class_id"],
            "class_name": o.get("class_name"),
            "camera_name": o["camera_name"],
            "boxes": _i(o["boxes"]),
        } for o in orphans],
        "archived_excluded": [{
            "class_name": a["class_name"], "boxes": _i(a["boxes"]),
        } for a in raw["archived_excluded"]],
    }

    totals = raw["totals"]
    rows_boxes = sum(r["boxes"] for r in class_rows)
    return {
        "targets": {
            "images_per_class": N_IMAGES, "cameras_per_class": M_CAMERAS,
            "max_camera_share": MAX_CAMERA_SHARE,
            "floor_images": FLOOR_IMAGES, "floor_cameras": FLOOR_CAMERAS,
        },
        "totals": {
            "boxes": _i(totals.get("boxes")), "images": _i(totals.get("images")),
            # completude: a soma das linhas (incl. stragglers) bate com o export.
            "boxes_in_rows": rows_boxes,
            "rows_match_export": rows_boxes == _i(totals.get("boxes")),
            "cameras_total": len(cameras),
            "cameras_active": sum(1 for c in cameras if c["is_active"]),
            "cameras_with_annotation": sum(1 for c in camera_cols if c["boxes"] > 0),
            "classes_met": sum(1 for r in class_rows if r["status"] == "met"),
            "classes_active": sum(1 for r in class_rows if r["in_taxonomy"]),
        },
        "classes": class_rows,
        "cameras": camera_cols,
        "matrix": matrix,
        "gaps": top_gaps,
        "needs_collection": needs_collection,
        "imbalance": imbalance,
        "warnings": warnings,
    }
