"""ZeroShotDetector — abstract interface over a text-conditioned (zero-shot)
object detector running on the edge device.

Task-098 (ADR-0047, ADR-0031 adendo 2026-07-12): during onboarding of a new
tenant, before any custom model has been trained, the edge (Jetson) can run a
zero-shot detector — guided by a list of *text* labels instead of fixed
training classes — to pre-label frames for human review. It is the same
plugável/flag-OFF discipline ADR-0031 established for DINO+SAM, applied to a
different model family that runs on-device instead of in a cloud
microservice.

Same shape as `recorder_client.py::RecorderClient` (task-090/091): a
`typing.Protocol` contract, a `NotConfiguredZeroShotDetector` default that
fails loud instead of silently pretending to detect anything, a deterministic
`StubZeroShotDetector` for tests, and a real implementation
(`OwlVitZeroShotDetector`) that wraps the actual model but is never exercised
against real weights in this repo's test suite (no GPU/Jetson available in
this environment — see AGENT.md "Sem validação em hardware real").

Model/license: NanoOWL (github.com/NVIDIA-AI-IOT/nanoowl, Apache-2.0 per the
repository's GitHub license metadata) is NVIDIA's TensorRT optimization of
OWL-ViT for Jetson. The weights it wraps (`google/owlvit-base-patch32` on
Hugging Face) are Apache-2.0 per the model card's own metadata
(`license: apache-2.0` in the repo's README front-matter and the Hub API's
`cardData.license`). Both confirmed from the primary source at
implementation time (2026-07-15) — see the PR description for the exact
commands used. If a different checkpoint/variant is substituted later,
re-verify its license before enabling the flag for any tenant; do not assume
it inherits OWL-ViT's Apache-2.0 without checking that specific artifact.

Scope discipline (task-098): this is an ONBOARDING/bootstrap tool, not a
production serving path. It is invoked on demand (batch, CLI — see
`zero_shot_pre_annotation.py`) to pre-label a set of frames once, before the
tenant has a trained model. It must never run in the continuous inference
loop that serves detections to the customer (that is DeepStream + the
ONNX RF-DETR/YOLOX detector, an entirely different code path).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ZeroShotDetection:
    """One text-guided detection: a box + the text label that matched it.

    `cx, cy, w, h` are normalized to [0, 1] (center-x, center-y, width,
    height), the same convention `pre_annotations` already uses for the
    dict-shaped bbox (see AI_NOTE in
    services/api/app/domain/services/annotation_service.py:
    "DINO salva bbox como dict {cx,cy,w,h}").
    """

    text_label: str
    confidence: float
    cx: float
    cy: float
    w: float
    h: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence fora de [0,1]: {self.confidence}")
        for name, value in (("cx", self.cx), ("cy", self.cy), ("w", self.w), ("h", self.h)):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} fora de [0,1]: {value}")


class ZeroShotDetectorError(Exception):
    """Raised when the detector cannot fulfil a request (not configured, model
    load failure, inference error, ...)."""


@runtime_checkable
class ZeroShotDetector(Protocol):
    """Contract every zero-shot backend (OWL-ViT/NanoOWL, mock) must satisfy.

    Implementations are injected into the onboarding orchestration (see
    `zero_shot_pre_annotation.py`); callers never talk to the underlying
    model library directly.
    """

    def detect(
        self, image_bytes: bytes, text_labels: list[str]
    ) -> list[ZeroShotDetection]:
        """Run text-conditioned detection on one frame.

        `text_labels` are free-text prompts (e.g. "capacete de segurança",
        "colete refletivo") — typically the tenant's module class taxonomy
        (ADR-0031, estágio CLASSES), supplied by the onboarding operator.
        Returns one `ZeroShotDetection` per matched box (possibly empty — a
        frame with no matches is not an error). Raises
        `ZeroShotDetectorError` on any failure to run inference at all
        (model not loaded, corrupt image, backend crash).
        """
        ...


class NotConfiguredZeroShotDetector:
    """Default ZeroShotDetector — fails loud until a real backend is wired.

    Prevents the onboarding flow from silently "succeeding" with zero
    detections when no model is actually loaded. Mirrors
    `recorder_client.NotConfiguredRecorderClient`.
    """

    _MESSAGE = (
        "Nenhum ZeroShotDetector real configurado — injete uma implementação "
        "concreta (ex. OwlVitZeroShotDetector) antes de rodar a pré-anotação "
        "de onboarding. Sem hardware Jetson disponível para validar a "
        "inferência real nesta sessão (task-098) — ver AGENT.md."
    )

    def detect(
        self, image_bytes: bytes, text_labels: list[str]
    ) -> list[ZeroShotDetection]:
        raise ZeroShotDetectorError(self._MESSAGE)


class StubZeroShotDetector:
    """Deterministic stub ZeroShotDetector for tests and local development.

    Not wired as the production default — callers must opt in explicitly.
    Returns a fixed set of detections regardless of image bytes, filtered to
    only the requested `text_labels` (so tests can assert label-filtering
    behavior without a real model).
    """

    def __init__(
        self,
        detections: list[ZeroShotDetection] | None = None,
        raise_on_empty_labels: bool = True,
    ) -> None:
        self._detections = detections if detections is not None else [
            ZeroShotDetection(
                text_label="capacete de segurança",
                confidence=0.87,
                cx=0.5, cy=0.4, w=0.2, h=0.3,
            ),
        ]
        self._raise_on_empty_labels = raise_on_empty_labels

    def detect(
        self, image_bytes: bytes, text_labels: list[str]
    ) -> list[ZeroShotDetection]:
        if not text_labels and self._raise_on_empty_labels:
            raise ZeroShotDetectorError("text_labels vazio — nenhum prompt para detectar")
        if not image_bytes:
            raise ZeroShotDetectorError("image_bytes vazio")
        wanted = {label.strip().lower() for label in text_labels}
        return [d for d in self._detections if d.text_label.strip().lower() in wanted]


class OwlVitZeroShotDetector:
    """Real backend: NanoOWL (TensorRT-optimized OWL-ViT) on the Jetson.

    NOT exercised against real weights anywhere in this repo's test suite —
    there is no Jetson/GPU available in this environment (same limitation as
    every other task-09x edge module, see AGENT.md "Sem validação em
    hardware real"). Import of the heavy dependency (`nanoowl`, which pulls
    in TensorRT/torch) is deferred to `__init__` so importing this *module*
    never requires those packages to be installed — only instantiating this
    class does.

    License (verified 2026-07-15, see module docstring): NanoOWL and the
    OWL-ViT weights it wraps are both Apache-2.0. Do not swap in a different
    checkpoint/library without re-verifying its license the same way.
    """

    def __init__(self, engine_path: str, image_encoder_engine_path: str | None = None) -> None:
        try:
            from nanoowl.owl_predictor import OwlPredictor  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover — no nanoowl/TensorRT in CI or this env
            raise ZeroShotDetectorError(
                "nanoowl não instalado — dependência real do backend NanoOWL "
                "(requirements/edge-inference.txt, quando existir). Este "
                "caminho não é exercitado nos testes desta sessão (sem "
                "hardware Jetson/TensorRT disponível)."
            ) from exc
        self._predictor = OwlPredictor(  # pragma: no cover — requires real TensorRT engine
            image_encoder_engine=image_encoder_engine_path,
            engine=engine_path,
        )

    def detect(
        self, image_bytes: bytes, text_labels: list[str]
    ) -> list[ZeroShotDetection]:  # pragma: no cover — requires real TensorRT engine
        if not text_labels:
            raise ZeroShotDetectorError("text_labels vazio — nenhum prompt para detectar")
        try:
            from io import BytesIO  # noqa: PLC0415

            from PIL import Image  # noqa: PLC0415

            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            text_encodings = self._predictor.encode_text(text_labels)
            output = self._predictor.predict(
                image=image, text=text_labels, text_encodings=text_encodings,
            )
        except Exception as exc:
            raise ZeroShotDetectorError(f"inferência NanoOWL falhou: {exc}") from exc

        width, height = image.size
        detections: list[ZeroShotDetection] = []
        for box, label_idx, score in zip(
            output.boxes, output.labels, output.scores, strict=False
        ):
            x0, y0, x1, y1 = (float(v) for v in box)
            cx = ((x0 + x1) / 2.0) / width
            cy = ((y0 + y1) / 2.0) / height
            w = (x1 - x0) / width
            h = (y1 - y0) / height
            detections.append(
                ZeroShotDetection(
                    text_label=text_labels[int(label_idx)],
                    confidence=float(score),
                    cx=min(max(cx, 0.0), 1.0),
                    cy=min(max(cy, 0.0), 1.0),
                    w=min(max(w, 0.0), 1.0),
                    h=min(max(h, 0.0), 1.0),
                )
            )
        return detections
