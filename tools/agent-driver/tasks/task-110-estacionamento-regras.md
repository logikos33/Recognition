---
title: "Estacionamento: pessoa/veículo + linha de cruzamento + aglomeração + zona/permanência (v1 faseado)"
risk: default
adr: 0053
---

# Task 110 — Estacionamento (ADR-0053)

## Objetivo
- Detecção pessoa/veículo (8×2MP, YOLOX-Tiny/Nano) + **linha de cruzamento** (entrada/saída) +
  **regra de aglomeração** (N pessoas numa zona por T segundos).
- "Furto/material indevido" = **regra de zona/permanência** (permanência anômala perto de veículo)
  — **v1 faseado: NÃO alegar detecção de furto**; alertar "permanência atípica em zona".

## Critérios de aceitação
- [ ] Regras de linha/zona/permanência configuráveis por câmera, avaliadas sobre o stream de detecções.
- [ ] Nenhuma claim de "furto" na UI/alertas — terminologia neutra de permanência/zona.
- [ ] Simulável no stress (task-111).
