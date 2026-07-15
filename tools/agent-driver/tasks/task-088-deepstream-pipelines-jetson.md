---
title: "Edge Jetson: pipelines DeepStream EPI + Contagem (Qualidade após ONNX) — reescreve task-032 — HARDWARE"
pr_title: "feat(edge): pipelines DeepStream no Orin (EPI/Contagem) + TensorRT INT8/DLA"
commit_message: "feat(edge): DeepStream EPI+Contagem no Jetson (RF-DETR/YOLOX)"
eval: manual-hardware
risk: security
requires_hardware: true
supersede: task-032 (OBSOLETA — mini-PC descartado, assumia ultralytics)
depende_de: task-087, task-082, ADR-0044
bloco: 4 (Edge Jetson + VST)
---

# Task 088 — Pipelines DeepStream no Jetson (reescreve 032)

## Objetivo
Rodar EPI e Contagem em DeepStream no Orin, com o detector ONNX Apache (RF-DETR/YOLOX). Qualidade entra depois do
porte ONNX (task-079).

## Escopo
- Pipelines EPI + Contagem; engines TensorRT (INT8/FP16), avaliar **DLA** para descarregar GPU.
- Detecções → Redis local (`detections:*`) → edge-sync-agent.

## Aceite
- [ ] EPI + Contagem processando N câmeras no box; detecções no Redis; sem AGPL.

## Checkpoint
- BLOQUEADA-HARDWARE. Substitui 032. Qualidade fica gated por 079.
