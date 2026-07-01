---
title: "Gateway mgmt (O2/MikroTik) — migration site_gateways + API de provisionamento"
pr_title: "feat(edge): site_gateways (migration) + API de provisionamento de gateway (WireGuard)"
commit_message: "feat(edge): tabela site_gateways + API de enrollment/estado do gateway (MikroTik WireGuard)"
eval: default
budget_minutes: 75
risk: security
requires_migration: true
status: GATED-MIGRATION — NÃO colocar na queue.txt autônoma; fluxo de migration com checkpoint humano
---

# Tarefa 031 — Gerência de gateway do site (O2 / MikroTik) · GATED por migration

> ⚠️ Cria `site_gateways` → checkpoint de migration. Lado cloud do ADR-0020 (MikroTik = camada de VPN segura).
> O provisionamento físico/RouterOS real e o config-pelo-front são HARDWARE/033 e capacidade gated futura.

## Objetivo
Modelar o gateway (MikroTik) de cada site como entidade gerenciável e expor a API que o cloud usa pra
provisionar/inspecionar: enrollment do gateway (recebe par de chaves WG), estado na overlay, last_seen.
Ver ADR-0020.

## Migration
- `public.site_gateways` (id, tenant_id NOT NULL, site_id, type 'mikrotik', wg_public_key, overlay_ip,
  status, last_seen_at, routeros_cred_ref [referência a segredo, NÃO a credencial], created_at). Índices por (tenant_id, site_id).

## API (vira AUTO após migration)
- Enrollment do gateway (one-time atômico, padrão task-004), estado/heartbeat do gateway, listar por site.
- tenant/site do enrollment, nunca do body; credencial RouterOS guardada como referência a segredo (nunca em claro).

## Eval (default, banco REAL)
- enrollment cria gateway ligado ao tenant/site do token (one-time atômico); cross-tenant isolado; credencial não exposta.

## Critérios de aceitação
- [ ] Migration idempotente; enrollment one-time; tenant-scoped (C-01); segredo protegido (C-05).
- [ ] Testes DB real. PR (migration via checkpoint).

## Checkpoint
- CHECKPOINT humano antes da migration. Provisionamento RouterOS real + config-pelo-front = HARDWARE/033 + gated futuro.
