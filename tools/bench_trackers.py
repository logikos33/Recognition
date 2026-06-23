#!/usr/bin/env python3
"""
Recognition — bench_trackers (CD-02).

Harness OFFLINE de bancada: roda o pipeline de contagem (YOLO +
CountingLineOperation) sobre um vídeo gravado da doca, comparando
DeepSORT vs ByteTrack, e reporta contagens in/out/net + estimativa de
ID-switches por tracker.

Não toca banco nem Redis — é para decidir e travar o tracker do produto
com vídeo real (ver Roccatextil/tasks-carga-descarga-fase1.md, CD-02).

Uso:
    python3 tools/bench_trackers.py --video doca_baia3.mp4 --target-class roll
    python3 tools/bench_trackers.py --video doca.mp4 --line 0.5,0,0.5,1 \
        --trackers deepsort,bytetrack --max-frames 3000 --output bench.json

Dependências (instalar na bancada, não na API):
    pip install ultralytics opencv-python deep-sort-realtime supervision
ByteTrack vem do pacote `supervision`; se algum tracker não estiver
instalado, o harness roda só com os disponíveis e avisa com clareza.
"""
import argparse
import importlib.util
import json
import logging
import sys
import types
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("bench_trackers")

REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_DIR = REPO_ROOT / "services" / "api" / "app" / "domain" / "services" / "operations"

# Mesmos parâmetros do inference_engine.py (DeepSORT de produção).
DEEPSORT_MAX_AGE = 30
DEEPSORT_N_INIT = 3


class TrackerUnavailableError(RuntimeError):
    """Tracker não instalado neste ambiente — mensagem explica como instalar."""


def _load_counting_line():
    """Carrega CountingLineOperation direto do arquivo, sem importar o app Flask.

    Registra pacotes stub em sys.modules para satisfazer os imports
    absolutos `app.domain.services.operations.*` dos módulos da operação.
    """
    for name in ("app", "app.domain", "app.domain.services", "app.domain.services.operations"):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    def _load(mod_name: str, path: Path):
        spec = importlib.util.spec_from_file_location(mod_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
        return module

    _load("app.domain.services.operations.base", OPS_DIR / "base.py")
    counting = _load(
        "app.domain.services.operations.canonical.counting_line",
        OPS_DIR / "canonical" / "counting_line.py",
    )
    return counting.CountingLineOperation


class DeepSortAdapter:
    """DeepSORT (deep-sort-realtime) — mesmo setup do inference-service."""

    name = "deepsort"

    def __init__(self) -> None:
        try:
            from deep_sort_realtime.deepsort_tracker import DeepSort
        except ImportError as exc:
            raise TrackerUnavailableError(
                "DeepSORT indisponível — instale com: pip install deep-sort-realtime"
            ) from exc
        self._tracker = DeepSort(max_age=DEEPSORT_MAX_AGE, n_init=DEEPSORT_N_INIT)

    def update(self, frame, detections: list[dict]) -> list[dict]:
        """Atribui track_id às detecções (associação best-effort por classe)."""
        if not detections:
            return detections
        ds_input = [
            ([d["bbox"][0], d["bbox"][1], d["bbox"][2], d["bbox"][3]], d["confidence"], d["class"])
            for d in detections
        ]
        tracks = self._tracker.update_tracks(ds_input, frame=frame)
        tracked_by_class: dict[str, list] = {}
        for track in tracks:
            if not track.is_confirmed():
                continue
            tracked_by_class.setdefault(track.det_class or "", []).append(track)
        for det in detections:
            candidates = tracked_by_class.get(det["class"], [])
            if candidates:
                det["track_id"] = candidates[0].track_id
                candidates.pop(0)
        return detections


class ByteTrackAdapter:
    """ByteTrack via pacote `supervision` (sv.ByteTrack)."""

    name = "bytetrack"

    def __init__(self) -> None:
        try:
            import numpy as np
            import supervision as sv
        except ImportError as exc:
            raise TrackerUnavailableError(
                "ByteTrack indisponível — instale com: pip install supervision "
                "(traz sv.ByteTrack; numpy também é necessário)"
            ) from exc
        self._np = np
        self._sv = sv
        self._tracker = sv.ByteTrack()
        self._class_vocab: dict[str, int] = {}

    def _class_id(self, name: str) -> int:
        if name not in self._class_vocab:
            self._class_vocab[name] = len(self._class_vocab)
        return self._class_vocab[name]

    def update(self, frame, detections: list[dict]) -> list[dict]:
        """Atribui track_id às detecções via ByteTrack (match por IoU de bbox)."""
        np = self._np
        if not detections:
            return detections
        xyxy = np.array(
            [[d["bbox"][0], d["bbox"][1], d["bbox"][0] + d["bbox"][2], d["bbox"][1] + d["bbox"][3]]
             for d in detections],
            dtype=np.float32,
        )
        confidence = np.array([d["confidence"] for d in detections], dtype=np.float32)
        class_id = np.array([self._class_id(d["class"]) for d in detections], dtype=int)
        sv_dets = self._sv.Detections(xyxy=xyxy, confidence=confidence, class_id=class_id)
        tracked = self._tracker.update_with_detections(sv_dets)
        if tracked.tracker_id is None:
            return detections
        for t_xyxy, t_id in zip(tracked.xyxy, tracked.tracker_id):
            best_idx, best_iou = None, 0.1
            for i, det in enumerate(detections):
                if det.get("track_id") is not None:
                    continue
                iou = _iou_xyxy(t_xyxy, xyxy[i])
                if iou > best_iou:
                    best_idx, best_iou = i, iou
            if best_idx is not None:
                detections[best_idx]["track_id"] = int(t_id)
        return detections


def _iou_xyxy(a, b) -> float:
    """IoU entre dois bboxes [x1, y1, x2, y2]."""
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return float(inter / union) if union > 0 else 0.0


class IdSwitchEstimator:
    """Estimativa offline de ID-switch (sem ground truth, é um proxy).

    Conta como switch um track_id NOVO surgindo perto (raio normalizado)
    da última posição de um id que sumiu há poucos frames — padrão típico
    de reatribuição de identidade que gera cruzamento fantasma.
    """

    def __init__(self, radius: float = 0.08, gap_frames: int = 15) -> None:
        self._radius = radius
        self._gap = gap_frames
        self._last_pos: dict = {}    # track_id → (frame, cx, cy)
        self._seen: set = set()
        self.switches = 0

    def update(self, frame_index: int, detections: list[dict], fw: int, fh: int) -> None:
        active = set()
        for det in detections:
            tid = det.get("track_id")
            if tid is None:
                continue
            active.add(tid)
            bbox = det["bbox"]
            cx = (bbox[0] + bbox[2] / 2) / fw
            cy = (bbox[1] + bbox[3] / 2) / fh
            if tid not in self._seen:
                self._seen.add(tid)
                if self._is_reassignment(frame_index, cx, cy, active):
                    self.switches += 1
            self._last_pos[tid] = (frame_index, cx, cy)

    def _is_reassignment(self, frame_index: int, cx: float, cy: float, active: set) -> bool:
        for tid, (last_frame, lx, ly) in self._last_pos.items():
            if tid in active:
                continue
            if frame_index - last_frame > self._gap:
                continue
            dist = ((cx - lx) ** 2 + (cy - ly) ** 2) ** 0.5
            if dist <= self._radius:
                return True
        return False

    @property
    def unique_ids(self) -> int:
        return len(self._seen)


def _build_tracker(name: str):
    if name == "deepsort":
        return DeepSortAdapter()
    if name == "bytetrack":
        return ByteTrackAdapter()
    raise TrackerUnavailableError(f"Tracker desconhecido: {name} (use deepsort|bytetrack)")


def run_pipeline(args, tracker, operation_class) -> dict:
    """Roda YOLO + tracker + CountingLineOperation sobre o vídeo inteiro."""
    try:
        import cv2
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit(
            f"Dependência ausente ({exc.name}) — instale com: "
            "pip install ultralytics opencv-python"
        ) from exc

    x1, y1, x2, y2 = (float(v) for v in args.line.split(","))
    config = {
        "target_class": args.target_class,
        "line_points": [[x1, y1], [x2, y2]],
        "anchor_point": args.anchor,
        "confirm_samples": args.confirm_samples,
        "direction_debounce_frames": args.debounce,
        "confirmation_band": args.band,
        "confidence_threshold": args.conf,
    }
    operation = operation_class(config)
    errors = operation.validate_config(config)
    if errors:
        raise SystemExit(f"Config de contagem inválida: {'; '.join(errors)}")

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"Não consegui abrir o vídeo: {args.video}")

    model = YOLO(args.model)
    estimator = IdSwitchEstimator()
    state: dict = {}
    frame_index = 0
    crossings_total = 0

    while True:
        ok, frame = cap.read()
        if not ok or (args.max_frames and frame_index >= args.max_frames):
            break
        frame_index += 1
        fh, fw = frame.shape[:2]

        detections = []
        for result in model(frame, conf=args.conf, verbose=False):
            for box in result.boxes:
                bx1, by1, bx2, by2 = (float(v) for v in box.xyxy[0].tolist())
                detections.append({
                    "class": result.names[int(box.cls)],
                    "confidence": float(box.conf),
                    "bbox": [bx1, by1, bx2 - bx1, by2 - by1],
                    "track_id": None,
                })

        detections = tracker.update(frame, detections)
        estimator.update(frame_index, detections, fw, fh)

        out = operation.evaluate(
            detections,
            {"width": fw, "height": fh, "frame_index": frame_index},
            state,
        )
        state = out["state_next"]
        crossings_total += len(out["result"]["crossings"])

        if frame_index % 200 == 0:
            logger.info(
                "[%s] frame=%d counts=%s", tracker.name, frame_index, out["result"]["counts"]
            )

    cap.release()
    counts = (state.get("counts") or {"in": 0, "out": 0})
    return {
        "tracker": tracker.name,
        "frames": frame_index,
        "counts": {
            "in": counts.get("in", 0),
            "out": counts.get("out", 0),
            "net": counts.get("in", 0) - counts.get("out", 0),
        },
        "crossings_total": crossings_total,
        "unique_track_ids": estimator.unique_ids,
        "id_switches_estimated": estimator.switches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--video", required=True, help="Vídeo gravado da doca")
    parser.add_argument("--model", default="yolov8n.pt", help="Pesos YOLO (default yolov8n.pt)")
    parser.add_argument("--target-class", default="roll", help="Classe contada (default roll)")
    parser.add_argument(
        "--line", default="0.5,0,0.5,1",
        help="Linha x1,y1,x2,y2 normalizada (default vertical no meio)",
    )
    parser.add_argument(
        "--trackers", default="deepsort,bytetrack",
        help="Lista separada por vírgula: deepsort,bytetrack",
    )
    parser.add_argument("--anchor", default="bottom_center",
                        choices=["bottom_center", "centroid"])
    parser.add_argument("--confirm-samples", type=int, default=3)
    parser.add_argument("--debounce", type=int, default=5)
    parser.add_argument("--band", type=float, default=0.02,
                        help="Banda de histerese normalizada (default 0.02)")
    parser.add_argument("--conf", type=float, default=0.5)
    parser.add_argument("--max-frames", type=int, default=0, help="0 = vídeo inteiro")
    parser.add_argument("--output", default="", help="Arquivo JSON para salvar o relatório")
    args = parser.parse_args()

    operation_class = _load_counting_line()
    reports = []
    for name in [t.strip() for t in args.trackers.split(",") if t.strip()]:
        try:
            tracker = _build_tracker(name)
        except TrackerUnavailableError as exc:
            logger.warning("Pulando tracker '%s': %s", name, exc)
            continue
        logger.info("=== Rodando pipeline com %s ===", name)
        reports.append(run_pipeline(args, tracker, operation_class))

    if not reports:
        logger.error("Nenhum tracker disponível — nada a comparar.")
        return 1

    logger.info("=== Relatório (CD-02) ===")
    for rep in reports:
        logger.info(
            "%s: frames=%d in=%d out=%d net=%d unique_ids=%d id_switches~%d",
            rep["tracker"], rep["frames"], rep["counts"]["in"], rep["counts"]["out"],
            rep["counts"]["net"], rep["unique_track_ids"], rep["id_switches_estimated"],
        )
    payload = json.dumps({"video": args.video, "reports": reports}, indent=2)
    logger.info("JSON:\n%s", payload)
    if args.output:
        Path(args.output).write_text(payload)
        logger.info("Relatório salvo em %s", args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
