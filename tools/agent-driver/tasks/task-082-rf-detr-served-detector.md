---
title: "Detector: implementar RF-DETR ONNX servido de verdade (decoder/post-proc) + YOLOX fallback"
pr_title: "feat(inference): detector RF-DETR ONNX (Apache) plugável com YOLOX fallback"
commit_message: "feat(inference): RF-DETR ONNX servido + seleção de backend por modelo"
eval: default
risk: security
depende_de: ADR-0044
bloco: 2 (Detector)
---

# Task 082 — RF-DETR servido

## Objetivo
Tornar RF-DETR um detector ONNX servido real (hoje só `YoloxOnnxDetector` existe; RF-DETR é só docstring).

## Escopo (confirmado — C-04)
- `services/inference/inference/detectors.py`: implementar `RfDetrOnnxDetector` (decode/post-proc DETR),
  mantendo `YoloxOnnxDetector`. `get_detector()` seleciona por arquitetura do modelo (registry).
- Registry/model-config carrega arquitetura junto do peso (RF-DETR vs YOLOX).

## Aceite
- [ ] RF-DETR ONNX detecta corretamente num frame de teste; YOLOX segue funcionando; seleção por modelo.
- [ ] Zero AGPL (Apache-only); pytest/ruff verdes.

## Checkpoint
- STOP-for-review (toca detecção/modelo).
