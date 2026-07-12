---
title: "Command queue (O3) — migration edge_commands + API + polling do edge"
pr_title: "feat(edge): edge_commands (migration) + fila de comandos remotos (N2) idempotente"
commit_message: "feat(edge): tabela edge_commands + API de comandos + consumo por polling idempotente"
eval: default
budget_minutes: 75
risk: security
requires_migration: true
status: GATED-MIGRATION — NÃO colocar na queue.txt autônoma; fluxo de migration com checkpoint humano
---

# Tarefa 030 — Fila de comandos remotos (O3, nível N2) · GATED por migration

> ⚠️ Cria `edge_commands` → checkpoint de migration. A parte de "o edge executa o comando" real é HARDWARE/034;
> aqui é o lado cloud (enfileirar + auditar + endpoint de consumo/report).

## Objetivo
Permitir agir na operação sem SSH: o cloud enfileira comandos (restart_pipeline, reload_model, recalibrate,
set_camera_fps, toggle_camera, rotate_device_token, pull_diagnostics, drain_buffer); o edge consome por polling
e reporta resultado. Ver EDGE_DEPLOYMENT_PLAN/HARNESS §O3.

## Migration
- `public.edge_commands` (id, tenant_id NOT NULL, site_id, type, payload JSONB, status, x_command_id idempotente,
  requested_by, requested_at, result JSONB, executed_at). Índices por (tenant_id, site_id, status).

## API (vira AUTO após migration)
- POST comando (admin, tenant-scoped, X-Command-Id idempotente); GET pendentes (device-authed, do próprio site);
  POST resultado (device-authed). Auditado. Comando sem token/escopo errado → 403.

## Eval (default, banco REAL)
- enfileirar é idempotente (mesmo X-Command-Id não duplica); device só vê comandos do seu site; report fecha o comando.
- cross-tenant isolado; token errado → 403.

## Critérios de aceitação
- [ ] Migration idempotente; comandos idempotentes/auditados; device-authed por site; tenant-scoped (C-01).
- [ ] Testes DB real. PR (migration via checkpoint).

## Checkpoint
- CHECKPOINT humano antes de aplicar a migration. Endpoint só PR. Execução real do comando = HARDWARE/034.
