# ADR 0004 — Schema-per-Tenant como Estratégia de Multi-tenancy

## Status

Aceito (herdado)

## Data

2026-05-28

## Contexto

A plataforma Recognition é multi-tenant: cada cliente (tenant) deve enxergar apenas seus próprios dados. Três estratégias foram avaliadas:

- **Shared schema com `tenant_id`**: todas as tabelas possuem coluna `tenant_id NOT NULL`. Simples de migrar, mas requer que toda query filtre corretamente — risco de vazamento cross-tenant por query incorreta.
- **Schema-per-tenant**: cada tenant recebe um schema PostgreSQL dedicado (nomeado pelo slug do tenant). Isolamento forte por design; permissões de banco podem ser restringidas por schema.
- **Banco separado por tenant**: máximo isolamento, mas operacionalmente inviável na escala atual (Railway gerencia um único plugin PostgreSQL).

O volume atual de tenants (< 20) e o uso de Railway PostgreSQL (instância única) tornam a abordagem de banco separado inviável. O risco de query cross-tenant com shared schema é considerado alto dado o volume de queries e o perfil da equipe.

## Decisão

Adotar **schema-per-tenant via PostgreSQL**. Cada tenant recebe um schema nomeado `tenant_{slug}` criado pela função `create_tenant_schema()` no momento do onboarding.

Tabelas de infraestrutura global (tenants, edge_sites, device_tokens, ip_cameras, modules, tenant_modules) permanecem no schema `public` com `tenant_id NOT NULL`. Tabelas de dados operacionais (cameras, alerts, frames, detections, models, training_jobs) ficam no schema do tenant.

Queries de infraestrutura usam `public.tabela`; queries de dados operacionais usam `{tenant_schema}.tabela` obtido via `get_tenant_schema()` em `app/core/auth.py`.

## Consequências

- Isolamento forte: impossível vazar dados entre tenants por query sem schema explícito.
- Migrations devem iterar sobre `SELECT slug FROM public.tenants` para aplicar DDL em todos os schemas de tenant. Scripts de migration precisam ser idempotentes (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`).
- Novo tenant requer chamada explícita a `create_tenant_schema()` — processo de onboarding deve incluir este passo.
- Backup e restore por tenant são triviais: `pg_dump --schema=tenant_{slug}`.
- Ferramenta de migration deve executar DDL no schema correto; migrations globais e de tenant são separadas.
- Número de schemas cresce linearmente com tenants — sem impacto de performance até centenas de tenants no PostgreSQL.
