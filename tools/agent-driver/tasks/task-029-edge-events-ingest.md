---
title: "Events batch ingest (Fase 2) — migration edge_events + endpoint idempotente"
pr_title: "feat(edge): edge_events (migration) + POST /api/v1/edge/events batch idempotente"
commit_message: "feat(edge): tabela edge_events + ingest batch idempotente (X-Batch-Id) device-authed"
eval: default
budget_minutes: 75
risk: security
requires_migration: true
status: GATED-MIGRATION — NÃO colocar na queue.txt autônoma; roda pelo fluxo de migration com checkpoint humano
---

# Tarefa 029 — Ingest de eventos de detecção (Fase 2) · GATED por migration

> ⚠️ Cria a tabela `edge_events` → passa pelo **checkpoint de migration** (não autônomo). Depois de a migration
> estar aplicada/validada, a parte do endpoint vira AUTO.

## Objetivo
Receber em batch os eventos de detecção que o edge envia (EPI/Qualidade/Counting), de forma idempotente,
autenticado por device token. É o que liga a inferência do edge ao histórico/alertas no cloud.

## Migration (forward-only, idempotente — ADR/constituição C-02)
- `infra/migrations/0NN_edge_events.sql`: `public.edge_events` (id, tenant_id NOT NULL FK, site_id, device_id,
  module_code, type/classe, confiança, bbox/geo, ts, batch_id, payload JSONB). Índices por (tenant_id, site_id, ts).
- Numeração: conferir a última no banco (harness) antes; só `CREATE TABLE IF NOT EXISTS`/índices.

## Endpoint (vira AUTO após a migration)
- POST /api/v1/edge/events: auth device token (RS256, padrão task-002, atribuição por enrollment), body = batch.
- Idempotência por **X-Batch-Id** (reenvio do mesmo batch não duplica). tenant/site do enrollment, nunca do body.

## Eval (default, banco REAL)
- batch válido → eventos persistidos; reenvio do mesmo X-Batch-Id → sem duplicar.
- token inválido/revogado → 401/403; tenant forjado no body ignorado (C-01); cross-tenant isolado.

## Critérios de aceitação
- [ ] Migration idempotente validada no harness (2x sem erro). Endpoint idempotente + device-authed + tenant-server-side.
- [ ] Testes DB real. PR para develop (migration via checkpoint).

## Checkpoint
- CHECKPOINT humano antes de aplicar a migration em staging/prod (duplo-boot idempotência). Endpoint só PR.
