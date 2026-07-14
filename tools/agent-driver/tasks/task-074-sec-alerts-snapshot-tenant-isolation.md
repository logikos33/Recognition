# Task 074 — [SEC] `GET /api/alerts/<id>/snapshot` sem tenant_id (achado #7)

**Status**: PENDING · **Risk**: security (P0 — leak cross-tenant)
**Branch**: fix/sec-alerts-snapshot-tenant-isolation (worktree a partir de origin/develop)
**Fonte**: docs/API_CONTRACT_MAP.md achado #7 · **Relaciona**: ADR-0017, C-01.

## Problema (produção)
`GET /api/alerts/<alert_id>/snapshot` faz query direta **sem filtro `tenant_id`** → um tenant pode ler
o snapshot (imagem do evento) de um alerta de **outro tenant**.

## Fix
- Filtrar `tenant_id` na busca do alerta antes de servir o snapshot. Alerta de outro tenant → 404.
- Conferir se o path do artefato (R2/local) também é escopado por tenant (não montar path a partir de
  input do usuário sem validar posse).

## Teste (falha-antes/passa-depois)
- Tenant A pede snapshot de alerta do tenant B → 404 (antes: 200 + imagem). Mesmo tenant → ok.

## Aceite
- Query com `tenant_id`; 404 cross-tenant; teste prova; ruff+pytest verde; PR develop; STOP.
