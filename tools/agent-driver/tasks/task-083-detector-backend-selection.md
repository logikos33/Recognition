---
title: "Detector: seleção de backend (RF-DETR/YOLOX) por câmera/modelo + hot-reload"
pr_title: "feat(models): backend de detecção selecionável por câmera com hot-reload"
commit_message: "feat(models): arquitetura de detecção no registry + resolução por câmera"
eval: default
risk: security
depende_de: task-082, task-045 (seleção de modelo por câmera)
bloco: 2 (Detector)
---

# Task 083 — Seleção de backend por câmera/modelo

## Objetivo
Permitir escolher a arquitetura (RF-DETR/YOLOX) por câmera/modelo, reusando o mecanismo de model-config
(task-045) e o hot-reload Redis existente.

## Escopo
- Estender o registry/model-config com `arch` (rf_detr|yolox); resolução do detector efetivo por câmera.
- Hot-reload já existe (`camera:model:{id}` + pub/sub) — propagar a arquitetura junto.

## Aceite
- [ ] Trocar a arquitetura por câmera aplica sem restart; testes; UI reflete o backend efetivo.

## Checkpoint
- STOP-for-review.
