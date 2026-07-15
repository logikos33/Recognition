---
title: "Treino LGPD-clean: pipeline RF-DETR (Vast.ai/local) → export ONNX → registry; Roboflow opcional"
pr_title: "feat(training): treino RF-DETR com export ONNX; Roboflow atrás de flag+DPA"
commit_message: "feat(training): pipeline de treino RF-DETR Apache → ONNX → registry"
eval: default
risk: security
depende_de: ADR-0047, ADR-0044, task-085
bloco: 3 (Treino LGPD-clean)
---

# Task 086 — Pipeline de treino RF-DETR

## Objetivo
Treinar RF-DETR (open-source Apache) no compute atual, exportar ONNX, registrar — sem depender do Roboflow cloud.

## Escopo
- Treino RF-DETR (dataset COCO versionado) via TrainingCompute (Vast.ai/local — ADR-0039) → export ONNX → registry/linhagem.
- Roboflow cloud = opcional atrás de flag + DPA + anonimização (não default).

## Aceite
- [ ] Um treino RF-DETR end-to-end (fallback local) gera ONNX servível; registry atualizado; sem envio a terceiro por padrão.

## Checkpoint
- STOP-for-review (fluxo de treino).
