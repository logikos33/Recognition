"""Onboarding zero-shot pre-annotation (task-098, ADR-0047, ADR-0031 adendo).

Orchestrates a ONE-TIME, ON-DEMAND batch: given a set of frames captured
during a new tenant's onboarding and a list of text labels (the tenant's
class taxonomy — ADR-0031 estágio CLASSES precedes ANOTAÇÃO), runs a
`ZeroShotDetector` (see `zero_shot_detector.py`) over each frame and emits
suggestions in the EXACT `pre_annotations` dict shape the cloud already
consumes (`services/api/app/domain/services/annotation_service.py
::get_frame_annotations`, `frame_repository.py::get_pre_annotations`) — so a
human reviews them in the SAME AnnotationInterface.jsx screen already in
production, no new UI.

Why this is NOT wired into `services/api/app/domain/services/pre_annotation/`
(the cloud-side `PreAnnotationBackend` used by the "pré-anotar" button in the
AnnotationInterface, i.e. `DinoSamHttpBackend`): that interface's
`predict_and_store(frame_id, module_code) -> int` is a SYNCHRONOUS per-frame
HTTP proxy call (cloud → microservice, immediate response). Zero-shot on the
edge does not fit that shape — the edge only reaches the cloud via polling
(config_poller.py: 5 min interval; command_poller.py: 1 min interval, see
AGENT.md), so a synchronous cloud→edge→cloud round trip inside one HTTP
request is not viable with the polling architecture that exists today.
Zero-shot onboarding is instead a BATCH tool run on demand, on the edge
itself, by the operator doing the onboarding (ADR-0031: "quem treina:
híbrido — Logikos treina o inicial"). It reuses the SAME feature-flag names
and the SAME output format for governance/consistency, not the same
transport.

`services/edge-sync-agent` and `services/api` are independent deployables
with independent requirements.txt (see AGENT.md, task-091 section, on why
`onvif_recorder_client.py` PORTS instead of imports the monolith's ONVIF
client) — there is no shared-logic package between them
(`shared/python/recognition_shared` is Pydantic DTOs only). The flag
constant NAMES below are therefore duplicated from
`services/api/app/domain/services/pre_annotation/factory.py` by convention,
not by import; keep them in sync manually if either side's naming changes.

Scope discipline: this module must NEVER run in the continuous detection
loop. It is invoked once (or a handful of times) per new tenant, before any
custom model exists.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .zero_shot_detector import (
    ZeroShotDetection,
    ZeroShotDetector,
    ZeroShotDetectorError,
)

logger = logging.getLogger(__name__)

# Duplicated from services/api/app/domain/services/pre_annotation/factory.py
# (PRE_ANNOTATION_ENABLED_FLAG / PRE_ANNOTATION_BACKEND_FLAG) — see module
# docstring for why this is not a shared import.
PRE_ANNOTATION_ENABLED_FLAG = "pre_annotation_enabled"
PRE_ANNOTATION_BACKEND_FLAG = "pre_annotation_backend"
ZERO_SHOT_BACKEND_NAME = "zero_shot"


class FeatureFlagDisabledError(Exception):
    """Raised when the onboarding batch is invoked without the tenant's
    zero-shot flag turned on. No silent no-op — the normal onboarding path
    (upload manual + anotação humana, no pre-labels) is what runs when this
    is disabled, and running the batch anyway would be a silent behavior
    change the flag is supposed to gate (ADR-0031 discipline)."""


@dataclass(frozen=True)
class FrameInput:
    """One frame to pre-annotate: an opaque id (matches the cloud's
    `training_frames.id`) plus the raw image bytes."""

    frame_id: str
    image_bytes: bytes


@dataclass(frozen=True)
class FramePreAnnotationResult:
    """Pre-annotation output for one frame, ready to be persisted into
    `training_frames.pre_annotations` (wiring that write path — an API
    endpoint accepting this payload — is deferred; see PR description)."""

    frame_id: str
    pre_annotations: list[dict]


@dataclass
class OnboardingPreAnnotationReport:
    """Result of a full onboarding batch run."""

    text_labels: list[str]
    results: list[FramePreAnnotationResult] = field(default_factory=list)
    failed_frame_ids: list[str] = field(default_factory=list)

    @property
    def total_annotations(self) -> int:
        return sum(len(r.pre_annotations) for r in self.results)


def is_zero_shot_enabled(feature_flags: dict) -> bool:
    """Mirrors factory.py's `_enabled_for_tenant` + `_backend_name_for_tenant`
    combined: True only when the tenant has BOTH
    `pre_annotation_enabled: true` AND `pre_annotation_backend: "zero_shot"`
    set. No env-var fallback here (unlike factory.py's `PRE_ANNOTATION_ENABLED`
    env fallback) — the edge process has no notion of "the current tenant's
    default", only what the onboarding operator explicitly passes in for
    this run, so there is nothing safe to default to besides OFF."""
    if not bool(feature_flags.get(PRE_ANNOTATION_ENABLED_FLAG, False)):
        return False
    return feature_flags.get(PRE_ANNOTATION_BACKEND_FLAG) == ZERO_SHOT_BACKEND_NAME


def to_pre_annotation_dict(detection: ZeroShotDetection) -> dict:
    """Converts one `ZeroShotDetection` to the exact dict shape
    `annotation_service.get_frame_annotations` already parses for DINO+SAM
    pre-annotations: `bbox` as a `{cx,cy,w,h}` dict (see AI_NOTE in that
    module: "DINO salva bbox como dict {cx,cy,w,h}, legado como array"),
    `class` (not `label` — DINO's key, and the one the fallback prefers:
    `p.get("class") or p.get("label")`), and `confidence`."""
    return {
        "bbox": {
            "cx": detection.cx,
            "cy": detection.cy,
            "w": detection.w,
            "h": detection.h,
        },
        "class": detection.text_label,
        "confidence": detection.confidence,
    }


def to_pre_annotation_dicts(detections: list[ZeroShotDetection]) -> list[dict]:
    return [to_pre_annotation_dict(d) for d in detections]


def run_onboarding_pre_annotation(
    detector: ZeroShotDetector,
    frames: list[FrameInput],
    text_labels: list[str],
    feature_flags: dict,
    continue_on_frame_error: bool = False,
) -> OnboardingPreAnnotationReport:
    """Runs zero-shot pre-annotation over `frames`, gated by `feature_flags`.

    Raises `FeatureFlagDisabledError` immediately (before touching the
    detector or any frame) if the tenant's flags don't have zero-shot
    pre-annotation on — the whole batch is a no-op when the flag is off, by
    construction, not by convention.

    By default a per-frame detector failure aborts the whole batch (fail
    loud, no partial-and-silent result). Set `continue_on_frame_error=True`
    to skip failed frames and keep going — every skip is logged and recorded
    in `failed_frame_ids`, never silently dropped.
    """
    if not is_zero_shot_enabled(feature_flags):
        raise FeatureFlagDisabledError(
            f"tenant não tem zero-shot pre-annotation habilitado "
            f"({PRE_ANNOTATION_ENABLED_FLAG}=true e "
            f"{PRE_ANNOTATION_BACKEND_FLAG}={ZERO_SHOT_BACKEND_NAME!r} são "
            f"obrigatórios) — caminho normal de onboarding (sem pre-labels) "
            f"segue intacto."
        )
    if not text_labels:
        raise ValueError("text_labels vazio — nada para o zero-shot detectar")

    report = OnboardingPreAnnotationReport(text_labels=list(text_labels))
    for frame in frames:
        try:
            detections = detector.detect(frame.image_bytes, text_labels)
        except ZeroShotDetectorError as exc:
            logger.warning(
                "zero_shot_frame_failed frame_id=%s err=%s", frame.frame_id, exc
            )
            if not continue_on_frame_error:
                raise
            report.failed_frame_ids.append(frame.frame_id)
            continue

        report.results.append(
            FramePreAnnotationResult(
                frame_id=frame.frame_id,
                pre_annotations=to_pre_annotation_dicts(detections),
            )
        )

    logger.info(
        "zero_shot_onboarding_batch_done frames=%d ok=%d failed=%d annotations=%d",
        len(frames), len(report.results), len(report.failed_frame_ids),
        report.total_annotations,
    )
    return report


# ── CLI (on-demand invocation during onboarding) ───────────────────────────


def _load_frames_from_dir(frames_dir: Path) -> list[FrameInput]:
    """Reads every `*.jpg`/`*.jpeg`/`*.png` in `frames_dir`; the filename
    stem (without extension) is used as `frame_id` — the operator is
    expected to have named files after the cloud's `training_frames.id`
    (e.g. exported alongside the extraction step, ADR-0031 estágio DADOS)."""
    frames: list[FrameInput] = []
    for pattern in ("*.jpg", "*.jpeg", "*.png"):
        for path in sorted(frames_dir.glob(pattern)):
            frames.append(FrameInput(frame_id=path.stem, image_bytes=path.read_bytes()))
    return frames


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Pré-anotação zero-shot de onboarding (task-098) — roda uma vez "
            "sobre um diretório de frames, produz um JSON com sugestões no "
            "formato pre_annotations para revisão humana."
        )
    )
    parser.add_argument("--frames-dir", required=True, type=Path)
    parser.add_argument(
        "--text-labels", required=True,
        help="Lista separada por vírgula, ex.: 'capacete de segurança,colete refletivo'",
    )
    parser.add_argument(
        "--feature-flags", required=True,
        help=(
            "JSON com as flags do tenant, ex.: "
            '\'{"pre_annotation_enabled": true, "pre_annotation_backend": "zero_shot"}\''
        ),
    )
    parser.add_argument("--engine-path", required=True, help="Path do engine TensorRT NanoOWL")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--continue-on-frame-error", action="store_true",
        help="Não aborta o lote inteiro se um frame falhar (default: aborta).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover — thin CLI wiring
    logging.basicConfig(
        level="INFO", format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    try:
        feature_flags = json.loads(args.feature_flags)
    except json.JSONDecodeError as exc:
        logger.error("feature_flags_invalid_json %s", exc)
        return 1

    from .zero_shot_detector import OwlVitZeroShotDetector  # noqa: PLC0415

    try:
        detector = OwlVitZeroShotDetector(engine_path=args.engine_path)
        frames = _load_frames_from_dir(args.frames_dir)
        text_labels = [label.strip() for label in args.text_labels.split(",") if label.strip()]
        report = run_onboarding_pre_annotation(
            detector=detector,
            frames=frames,
            text_labels=text_labels,
            feature_flags=feature_flags,
            continue_on_frame_error=args.continue_on_frame_error,
        )
    except (FeatureFlagDisabledError, ZeroShotDetectorError, ValueError) as exc:
        logger.error("zero_shot_onboarding_failed %s", exc)
        return 1

    output_payload = [
        {"frame_id": r.frame_id, "pre_annotations": r.pre_annotations}
        for r in report.results
    ]
    args.output.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
    logger.info("zero_shot_onboarding_output_written path=%s", args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
