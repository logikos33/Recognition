"""Régua de altura-de-pessoa (Apache-2.0, LOCAL) para triagem de frames.

NÃO é treino em dado de terceiro: usa um detector de prateleira (YOLOX-s COCO,
Apache-2.0 / Megvii) só como INSTRUMENTO DE MEDIDA. Roda LOCAL ou no box —
frames com pessoas identificáveis nunca saem para nuvem de terceiro.
ZERO ultralytics/AGPL (ADR-0043).

Preprocessamento: BGR 0-255 (o que o YOLOX stock do Megvii espera; é também o
preproc do edge — ver landmine "preproc BGR 0-255" e D-66 no REGISTRO). NÃO usa
o `_preprocess` de `app.domain.detectors.onnx_yolox` (normaliza RGB/255 e zera
as detecções do modelo COCO stock); reusa apenas os helpers numpy Apache de
decode/NMS.

Mede, por frame, a altura em px de cada pessoa e classifica o frame pela pessoa
MAIS ALTA (a mais anotável) em 3 faixas (regra: capacete ~ 1/7 da altura da
pessoa; detecção degrada muito abaixo de ~32 px de lado = "small" do COCO):
  >= 140 px  -> anotável   (capacete ~20 px)
  80..140 px -> duvidoso   (Vitor decide)
  <  80 px   -> descartar  (capacete < 12 px)
Frames sem pessoa contados à parte (possível negativo).

Uso:
  # lote real: use conf 0.10 p/ separar "pessoa pequena" de "sem pessoa" (D-65)
  python scripts/triage/measure_person_heights.py \
      --model yolox_s.onnx --frames-dir <dir> --conf 0.10 \
      [--camera-map cam.csv] [--out result.json] [--debug]

Modelo: yolox_s.onnx (Apache-2.0) —
  github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.onnx
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import cv2  # type: ignore
import numpy as np
import onnxruntime as ort  # type: ignore

# Reusa só os helpers numpy Apache (decode/NMS/classes) do detector sancionado.
_HERE = Path(__file__).resolve()
_CANDS = [_HERE.parents[2] / "services" / "api"] + [
    Path.home() / "Logikos Recogntion" / d / "services" / "api"
    for d in ("Recognition", "wt-triage-679", "wt-tenant-sweep")
]
for _cand in _CANDS:
    if (_cand / "app" / "domain" / "detectors" / "onnx_yolox.py").is_file():
        sys.path.insert(0, str(_cand))
        break
from app.domain.detectors.onnx_yolox import (  # noqa: E402
    COCO_CLASSES,
    _decode_positions,
    _nms,
)

PERSON_ID = COCO_CLASSES.index("person")  # 0
INPUT = 640
BANDS = (("anotavel_>=140", 140.0), ("duvidoso_80-140", 80.0), ("descartar_<80", 0.0))


def _band(height: float) -> str:
    for name, lo in BANDS:
        if height >= lo:
            return name
    return BANDS[-1][0]


def _preprocess_bgr255(img: np.ndarray) -> tuple[np.ndarray, float]:
    """Letterbox p/ 640x640, BGR 0-255, CHW — o que o YOLOX stock espera."""
    h, w = img.shape[:2]
    scale = min(INPUT / h, INPUT / w)
    nh, nw = int(round(h * scale)), int(round(w * scale))
    resized = cv2.resize(img, (nw, nh))
    padded = np.full((INPUT, INPUT, 3), 114.0, dtype=np.float32)
    padded[:nh, :nw] = resized
    blob = padded.transpose(2, 0, 1)[None].astype(np.float32)  # [1,3,640,640]
    return blob, scale


def detect_person_heights(session, input_name, img, conf) -> list[float]:
    """Alturas (px, coords da imagem original) de cada pessoa detectada."""
    blob, scale = _preprocess_bgr255(img)
    raw = session.run(None, {input_name: blob})[0]  # [1, 8400, 85] (stock = raw)
    dec = _decode_positions(raw, INPUT, INPUT)[0]
    obj = dec[:, 4]
    cls = dec[:, 5:]
    cid = cls.argmax(1)
    score = obj * cls[np.arange(len(cls)), cid]
    mask = (score >= conf) & (cid == PERSON_ID)
    if not np.any(mask):
        return []
    d, sc = dec[mask], score[mask]
    cx, cy, bw, bh = d[:, 0], d[:, 1], d[:, 2], d[:, 3]
    x1, y1 = (cx - bw / 2) / scale, (cy - bh / 2) / scale
    x2, y2 = (cx + bw / 2) / scale, (cy + bh / 2) / scale
    boxes = np.stack([x1, y1, x2, y2], axis=1)
    keep = _nms(boxes, sc, 0.45)
    return [float(boxes[i, 3] - boxes[i, 1]) for i in keep]


def _load_camera_map(path: str | None) -> dict[str, str]:
    """CSV opcional frame_stem -> camera/canal. Ausente => 'desconhecida' (D-64)."""
    if not path:
        return {}
    mp: dict[str, str] = {}
    with open(path, newline="") as fh:
        for row in csv.reader(fh):
            if len(row) >= 2:
                mp[row[0].strip()] = row[1].strip()
    return mp


def measure(session, input_name, frames, camera_map, conf, debug=False) -> dict:
    per_frame: list[dict] = []
    all_heights: list[float] = []
    band_counts: dict[str, int] = defaultdict(int)
    no_person = 0
    per_cam: dict[str, dict] = defaultdict(
        lambda: {"frames": 0, "no_person": 0, "bands": defaultdict(int), "tallest": []}
    )
    for fp in frames:
        img = cv2.imread(str(fp))
        if img is None:
            continue
        h_img = img.shape[0]
        heights = detect_person_heights(session, input_name, img, conf)
        all_heights.extend(heights)
        cam = camera_map.get(fp.stem, "desconhecida")
        cb = per_cam[cam]
        cb["frames"] += 1
        if not heights:
            no_person += 1
            cb["no_person"] += 1
            per_frame.append({"frame": fp.name, "camera": cam, "n_persons": 0,
                              "tallest_px": None, "band": "sem_pessoa", "img_h": h_img})
            if debug:
                print(f"  {fp.name}: SEM PESSOA")
            continue
        tallest = max(heights)
        band = _band(tallest)
        band_counts[band] += 1
        cb["bands"][band] += 1
        cb["tallest"].append(tallest)
        per_frame.append({"frame": fp.name, "camera": cam, "n_persons": len(heights),
                          "tallest_px": round(tallest, 1),
                          "tallest_frac_img_h": round(tallest / h_img, 3),
                          "band": band, "img_h": h_img})
        if debug:
            print(f"  {fp.name}: {len(heights)} pessoa(s), maior={tallest:.0f}px "
                  f"({tallest / h_img:.0%} da altura), banda={band}")

    def _stats(xs: list[float]) -> dict | None:
        if not xs:
            return None
        s = sorted(xs)
        return {"min": round(s[0], 1), "median": round(s[len(s) // 2], 1),
                "max": round(s[-1], 1)}

    return {
        "total_frames": len(per_frame),
        "no_person_frames": no_person,
        "band_counts_by_tallest_person": dict(band_counts),
        "n_person_detections": len(all_heights),
        "annotatable_frames": [f["frame"] for f in per_frame
                               if f["band"] == "anotavel_>=140"],
        "doubtful_frames": [f["frame"] for f in per_frame
                            if f["band"] == "duvidoso_80-140"],
        "per_camera": {c: {"frames": v["frames"], "no_person": v["no_person"],
                           "bands": dict(v["bands"]), "tallest_px": _stats(v["tallest"])}
                       for c, v in per_cam.items()},
        "per_frame": per_frame,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, help="caminho do yolox_s.onnx (Apache-2.0)")
    ap.add_argument("--frames-dir")
    ap.add_argument("--frame", action="append", default=[])
    ap.add_argument("--conf", type=float, default=0.10,
                    help="0.10 no lote real (separa pessoa pequena de sem pessoa, D-65)")
    ap.add_argument("--camera-map", help="CSV frame_stem,camera (D-64)")
    ap.add_argument("--out")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()

    frames = [Path(f) for f in a.frame]
    if a.frames_dir:
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.PNG"):
            frames.extend(Path(a.frames_dir).glob(ext))
    frames = sorted(set(frames))
    if not frames:
        print("Nenhum frame (--frames-dir/--frame).", file=sys.stderr)
        return 2

    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    session = ort.InferenceSession(a.model, sess_options=opts,
                                   providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name

    print(f"Medindo {len(frames)} frame(s), conf={a.conf}, preproc=BGR-0-255 ...")
    res = measure(session, input_name, frames, _load_camera_map(a.camera_map),
                  a.conf, a.debug)
    print("\n=== RESUMO ===")
    print(f"frames: {res['total_frames']}  |  sem pessoa: {res['no_person_frames']}")
    print(f"faixas (pela pessoa mais alta): {res['band_counts_by_tallest_person']}")
    print(f"anotáveis: {len(res['annotatable_frames'])}  |  "
          f"duvidosos: {len(res['doubtful_frames'])}")
    print(f"detecções de pessoa: {res['n_person_detections']}")
    for cam, s in res["per_camera"].items():
        print(f"  camera[{cam}]: {s['frames']} frames, bandas={s['bands']}, "
              f"altura_px={s['tallest_px']}")
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=2, ensure_ascii=False))
        print(f"\nJSON -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
