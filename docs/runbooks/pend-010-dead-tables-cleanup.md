# PEND-010 — Dead Tables Cleanup em public

## Status
Aberto — 2026-05-28

## Contexto

Após migration 042 desativar o tenant default, as tabelas em `public` que continham
dados desse tenant ficam como "dead tables" — estrutura mantida, dados deletados.

ADR-0017 decidiu manter as estruturas por segurança (rollback facilitado).
Este runbook tracked a limpeza posterior quando confirmado que o sistema está estável.

## Tabelas afetadas (schema public)

Tabelas que existiam como "schema do tenant default" por confusão histórica:

- `public.cameras` — 5 câmeras de teste deletadas pela migration 042
- `public.alerts` — 13 alertas de batch deletados pela migration 042
- `public.quality_*` — tabelas de quality do tenant default (se existirem em public)
- `public.users` — usuário `admin@epimonitor.com` desativado

## Ação necessária (NÃO executar ainda)

Aguardar confirmação de que:
1. Deploy pós-migration 042 está estável por ≥ 7 dias
2. Nenhum usuário ativo reportou acesso negado
3. Logs não mostram referências ao tenant 0001

Após confirmação:
```sql
-- APENAS quando PEND-010 for formalmente aprovado para execução
DROP TABLE IF EXISTS public.cameras CASCADE;
DROP TABLE IF EXISTS public.alerts CASCADE;
-- demais tabelas do tenant default conforme auditoria
```

## Responsável
Sprint de estabilização pós-Sprint 0.5 (≥ 7 dias após deploy de migration 042)

## Relacionado
- ADR-0017 Decisão Complementar — Tenant Default Removal
- Migration 046: `046_deactivate_default_tenant.sql`
- PEND-009: audit WHERE tenant_id
