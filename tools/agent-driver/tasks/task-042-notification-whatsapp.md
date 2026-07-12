---
title: "Notificação de alerta (WhatsApp/Telegram) + snapshot — melhoria A (migration)"
pr_title: "feat(notify): entrega de alerta crítico via WhatsApp/Telegram com snapshot (idempotente)"
commit_message: "feat(notify): notification_channels + notification_log + entrega externa de alerta tenant-scoped"
eval: default
budget_minutes: 90
risk: security
requires_migration: true
status: GATED-MIGRATION — NÃO colocar na queue.txt autônoma; fluxo de migration com checkpoint humano
---

# Tarefa 042 — Notificação de alerta (WhatsApp/Telegram) · melhoria A · GATED por migration

## Objetivo
Fechar o buraco operacional: hoje geramos alerta + evidência mas **não entregamos ao humano**. Entregar alerta
crítico a um canal externo (**WhatsApp Cloud API** ou **Telegram Bot**) com **snapshot + timestamp + câmera/zona**,
com rate-limit/agrupamento (anti-spam) e idempotência. Ver `ARQUITETURA_E_MELHORIAS.md` (A).

## Migration (APENAS aditivo — Migration Protocol)
- `CREATE TABLE IF NOT EXISTS notification_channels` (id, tenant_id UUID REFERENCES tenants(id), type, config JSONB,
  enabled, created_at) — **segredos NÃO em claro** (referência a secret/env, não o token).
- `CREATE TABLE IF NOT EXISTS notification_log` (id, tenant_id, alert_id, channel_id, status, x_dedup_key, sent_at)
  — idempotência por `x_dedup_key` (UNIQUE) pra não duplicar envio.
- Idempotente; sem DROP/ALTER TYPE.

## Comportamento (depois da migration)
- Ao disparar um `alert_rule` crítico → enfileira notificação → envia ao canal do tenant com snapshot (link R2 assinado).
- Rate-limit/agrupamento por câmera/regra; reenvio não duplica (x_dedup_key). Tudo tenant-scoped (C-01); canal/recipiente do registro do tenant, nunca do body.
- Falha de envio = retry com backoff; status auditado em notification_log.

## Arquivos
- infra/migrations/NNN_notification.sql · model/repo/service de notificação · hook no engine de alert_rules · tests.

## Eval (default) — testes (DB real)
- alerta dispara → 1 envio (mock do provedor) + 1 linha em notification_log; reenvio idempotente (sem duplicar).
- isolamento tenant (C-01); segredo não persistido em claro; sem JWT → 401 nos endpoints de config.
- ruff + pytest + tsc verdes.

## Critérios de aceitação
- [ ] Migration aditiva + entrega WhatsApp/Telegram com snapshot + idempotência + rate-limit + auditoria; tenant-scoped.

## Checkpoint
- MIGRATION: eu escrevo a migration, você valida o duplo-boot em staging ANTES do merge. NÃO entra na fila autônoma.
