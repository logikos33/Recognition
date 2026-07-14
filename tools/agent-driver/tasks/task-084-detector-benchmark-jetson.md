---
title: "Detector: benchmark RF-DETR vs YOLOX no Orin NX 16GB (GPU vs DLA, FP16 vs INT8, 28 câmeras) — HARDWARE"
pr_title: "docs(edge): benchmark de detector no Jetson Orin NX + escolha de default"
commit_message: "docs(edge): benchmark RF-DETR/YOLOX no Orin NX 16GB"
eval: manual-hardware
risk: security
requires_hardware: true
depende_de: ADR-0044, task-082
bloco: 2 (Detector)
---

# Task 084 — Benchmark de detector no Jetson (HARDWARE)

## Objetivo
Decidir empiricamente o default de produção: RF-DETR vs YOLOX no Orin NX 16GB, com 28 câmeras.

## Escopo
- Medir FPS/latência/precisão: RF-DETR vs YOLOX · GPU vs **DLA** · FP16 vs **INT8** · até 28 streams.
- Registrar ponto de degradação e o default recomendado por deployment.

## Aceite
- [ ] Relatório com números reais no Orin NX 16GB; default de produção definido; sem AGPL.

## Checkpoint
- BLOQUEADA-HARDWARE. Roda no box (amanhã). Fora da queue.txt autônoma.
