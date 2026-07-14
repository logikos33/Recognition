---
title: "Deployment modes: fluxo cloud-only para cliente SEM edge (feature)"
pr_title: "feat(platform): fluxo cloud-only (cliente sem edge) como feature"
commit_message: "feat(platform): suporte a cliente sem edge (cloud-only)"
eval: default
risk: security
depende_de: ADR-0046, task-093
bloco: 6 (Deployment modes)
---

# Task 094 — Fluxo cloud-only

## Objetivo
Cliente sem edge opera direto na nuvem. Tratar como feature explícita, ciente do trade-off de isolamento de câmera.

## Escopo
- Caminho câmera→nuvem quando `mode=cloud_only`; documentar a limitação de segurança (lockout de câmera) e quando
  exige um edge mínimo.
- Live view e evidência resolvidos pela nuvem nesse modo.

## Aceite
- [ ] Um tenant cloud-only opera (câmeras/evidência/live) sem edge; limitações documentadas.

## Checkpoint
- STOP-for-review.
