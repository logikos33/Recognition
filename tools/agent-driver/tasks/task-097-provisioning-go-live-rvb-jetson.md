---
title: "Provisionamento RVB + go-live (Jetson) — reescreve task-037 para o box real — HARDWARE"
pr_title: "docs(edge): runbook de provisionamento RVB + go-live no Jetson Orin"
commit_message: "docs(edge): runbook go-live RVB no Jetson"
eval: manual-hardware
risk: security
requires_hardware: true
supersede: task-037 (assumia mini-PC + fluxo antigo)
depende_de: task-087, task-088, task-090, task-095
bloco: 7 (Portabilidade de rede)
---

# Task 097 — Provisionamento RVB + go-live (Jetson)

## Objetivo
Fechar o go-live no site: 28 câmeras EPI, cenários, enrollment, MikroTik, modelo por câmera, no Jetson.

## Escopo
- Seeds reais (site RVB, 28 câmeras, cenários EPI), enrollment tokens, pin de modelo.
- Runbook day-of: ligar box → install.sh (ARM) → rede/túnel → enrollment → pipelines processando → validar no painel.
- Evidência recorder-first validada no local; acesso remoto sob demanda.

## Aceite
- [ ] EPI no ar na RVB; eventos no cloud < 5s; painel mostrando; evidência acessível local e remota.

## Checkpoint
- BLOQUEADA-HARDWARE / on-site. Substitui 037.
