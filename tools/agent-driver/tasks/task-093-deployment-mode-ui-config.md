---
title: "Deployment modes: edge/dual/cloud-only configurável na UI por tenant/site (sem código)"
pr_title: "feat(platform): modo de deployment por site editável na UI (edge/dual/cloud-only)"
commit_message: "feat(platform): DEPLOYMENT_MODE como config de tenant/site na UI"
eval: default
risk: security
requires_migration: talvez (coluna deployment_mode em site/tenant)
depende_de: ADR-0046
bloco: 6 (Deployment modes)
---

# Task 093 — Modo de deployment na UI

## Objetivo
Tornar o modo (edge | dual | cloud_only) configuração por tenant/site editável na plataforma, não env hard-coded.

## Escopo
- Persistir o modo por site (migration aditiva se preciso, forward-only, commit separado).
- UI role-gated para setar o modo; backend resolve o comportamento (origem de vídeo/evidência) por modo.

## Aceite
- [ ] Admin troca o modo pela UI; comportamento muda sem deploy; tenant-scoped (404 cross-tenant).

## Checkpoint
- STOP-for-review. Migration (se houver) separada da lógica.
