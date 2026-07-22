---
title: "Estacionamento: detecção + regras (aglomeração, furto/material indevido, linha de cruzamento)"
pr_title: "feat(operations): módulo estacionamento — counting + regras de aglomeração/zona"
commit_message: "feat(operations): estacionamento com linha de cruzamento e regras de zona/aglomeração"
eval: default
risk: security
depende_de: ADR-0048, task-107, task-024 (operation-types)
bloco: RVB multi-módulo
---

# Task 110 — Estacionamento (detecção + regras)

## Objetivo
Módulo de estacionamento nas 8 câmeras: pessoa/veículo + comportamentos.

## Escopo
- Detecção leve (YOLOX-Tiny/Nano, pessoa/veículo) + **linha de cruzamento** (counting_line, task-024).
- **Regras:** aglomeração = densidade de pessoas em zona > limiar (fácil); **furto / material indevido** = regra de
  zona/permanência/objeto (loitering, objeto deixado/retirado, horário). **Faseado** — começar por regra, evoluir.
  NÃO alegar "detecta furto" com detecção pura (alinhamento de expectativa registrado no ADR-0048).

## Aceite
- [ ] 8 câmeras com pessoa/veículo + linha de cruzamento + regra de aglomeração; regra de zona/permanência para suspeita (v1).

## Checkpoint
- STOP-for-review.
