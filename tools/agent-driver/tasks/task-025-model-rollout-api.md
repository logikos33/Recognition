---
title: "Model rollout / version-pin API (por tenant×módulo)"
pr_title: "feat(models): manifesto de modelo + pin de versão por tenant×módulo (rollout staged)"
commit_message: "feat(models): API de rollout — manifesto + version pin + canário, por tenant×módulo"
eval: default
budget_minutes: 60
risk: security
---

# Tarefa 025 — API de rollout de modelo (cloud-side de O5)

## Objetivo
Lado cloud do O5: expor o **modelo ativo por (tenant × módulo)** como um manifesto versionado que o edge vai
poder consultar (no futuro), com **pin de versão** e marcação de **canário** (subconjunto). Sem aplicar no edge
ainda (isso é HARDWARE/035). Tabelas existentes (`models`, `model_events`). Sem migration, sem hardware.

## Contexto (LER — C-04, C-01)
- repos/migrations de model (003_training, 014_model_events, 032_version_git_sha), module/tenant_modules.
- ADR de staged rollout (HARNESS_PLANO §O5). _helpers_tenant + fixture Postgres efêmero.

## Comportamento
- GET /api/v1/models/active?module=<code> → manifesto: modelo ativo do tenant×módulo (id, versão, checksum, git_sha).
- POST /api/v1/models/<id>/pin (admin) → fixa a versão ativa do tenant×módulo; registra em model_events (auditoria).
- Suporte a flag `canary` (marca a versão como canário antes do rollout geral). tenant do JWT; cross-tenant → 404.

## Eval (default, banco REAL)
- pin troca o modelo ativo do tenant×módulo; manifesto reflete; model_events registra quem/quando.
- canário: versão marcada canário não vira "active" geral até promover.
- isolamento: pin/manifesto de outro tenant → 404 (helper).
- ruff + pytest (DB real) + tsc verdes.

## Critérios de aceitação
- [ ] Manifesto + pin + canário por tenant×módulo; auditado; tenant-scoped (C-01). PR para develop.

## NEEDS CLARIFICATION
- Confirmar como "modelo ativo por tenant/módulo" é representado hoje (coluna/flag) antes de assumir; reusar.

## Checkpoint
- Só PR (humano revisa — afeta qual modelo roda, risk security). Sem produção. Sem migration.
