---
title: "Admin: edge sites + enrollment tokens (Fase 2)"
pr_title: "feat(edge): admin endpoints — criar edge_site e gerar enrollment token"
commit_message: "feat(edge): admin edge sites + enrollment tokens (one-time, server-scoped)"
eval: default
budget_minutes: 60
---

# Tarefa 003 — Admin: edge sites + enrollment tokens

## Objetivo
Endpoints de admin (lado cloud) para o operador cadastrar um site físico de edge e gerar um
enrollment token one-time que o device usará para se registrar (task-004). Usa tabelas já existentes
(public.edge_sites, public.enrollment_tokens — Fase 1). Sem hardware, sem migration.

## Contexto (LER antes — C-04, não adivinhar)
- /constitution.md (C-01 multi-tenant, C-05 segurança), CLAUDE.md.
- app/core/auth.py: get_tenant_id(), get_role() (tenant e role vêm do JWT, NUNCA do body).
- app/api/v1/edge/routes.py (já existe, task-002) e como blueprints são registrados em app/__init__.py.
- recognition_shared (EdgeSite, SiteStatus, DeploymentMode) — reusar os models/enums.
- Um repository existente como referência (psycopg2 + RealDictCursor, SQL no repository, BaseRepository).
- migration 050 (edge_sites) e 051 (enrollment_tokens) para os campos reais das tabelas.

## Comportamento
Rotas (exigem JWT de usuário com role admin/superadmin; tenant_id sempre de get_tenant_id()):
- POST /api/v1/edge/sites — cria public.edge_sites (name, location, deployment_mode) sob o tenant do JWT.
  tenant_id NUNCA vem do body. Valida deployment_mode in (cloud|edge|hybrid). Retorna o site criado.
- GET /api/v1/edge/sites — lista os sites do tenant do JWT (filtra por tenant_id).
- POST /api/v1/edge/sites/<site_id>/enrollment-tokens — gera enrollment token one-time:
  - Validar que site_id pertence ao tenant do JWT (senão 404).
  - Gerar token aleatório forte (secrets.token_urlsafe). Guardar APENAS o hash (token_hash) em
    enrollment_tokens, com tenant_id+site_id do registro (server), expires_at (ex: agora + 24h), used_at NULL.
  - Retornar o token em texto puro UMA vez na resposta (nunca mais recuperável).

## Arquivos (criar/alterar — NÃO tocar fora disto; guard-rail bloqueia infra/migrations/)
- app/api/v1/edge/routes.py (adicionar as rotas) ou um sub-blueprint admin se fizer mais sentido
- app/infrastructure/database/repositories/edge_site_repository.py (novo)
- registro de blueprint se necessário
- tests novos em services/api/tests/

## Eval (default: ruff + pytest + tsc) — os testes SÃO o critério
- criar site → 201, tenant_id = do JWT (não do body, mesmo se o body mandar outro).
- listar sites → só os do tenant do JWT (seed de 2 tenants; um não vê o do outro — C-01).
- gerar enrollment token → 201, retorna token plaintext, e no banco fica só o hash (assert token_hash != plaintext), expires_at setado, used_at NULL.
- gerar token para site de OUTRO tenant → 404 (não vaza existência cross-tenant).
- sem JWT / role insuficiente → 401/403.

## Critérios de aceitação
- [ ] tenant_id sempre do JWT; site_id validado pertencer ao tenant; cross-tenant bloqueado (C-01).
- [ ] enrollment token: aleatório forte, armazenado como hash, plaintext retornado só uma vez, com expiração.
- [ ] Testes acima verdes; ruff + pytest + tsc verdes; sem print; SQL parametrizado (C-05).
- [ ] PR para develop (driver cuida).

## Checkpoint
- Só PR. Sem banco de produção. Sem migration (usar tabelas existentes). Faltou contexto → ler, não adivinhar.
