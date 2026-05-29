# PEND-011 — Coluna `status` sem CHECK constraint em tenant schema cameras

**Status:** Pendente — sprint de qualidade futura  
**Criado em:** Sprint 0.5 (descoberto ao corrigir `_count_active_cameras`)

---

## Contexto

A função `create_tenant_schema()` (migrations 024/028/033) define:

```sql
CREATE TABLE IF NOT EXISTS %I.cameras (
    ...
    status VARCHAR(50) DEFAULT 'inactive',
    ...
)
```

Sem CHECK constraint. Valores são strings livres.

## Problema

Inconsistência potencial:

- `'active'`, `'Active'`, `'ACTIVE'` tratados como valores diferentes
- `'enabled'`, `'on'`, `'live'` poderiam aparecer por bugs de código
- Queries `WHERE status = 'active'` retornam contagens incorretas se algum
  lugar gravar com case diferente ou valor não canônico

## Plano

1. Auditar todos os locais que escrevem em `cameras.status`
2. Definir valores canônicos: `'active'`, `'inactive'`, `'maintenance'`
3. Migration que normaliza valores existentes (`UPDATE ... WHERE LOWER(status) = ...`)
4. Migration que adiciona CHECK constraint
5. Documentar enum no código (idealmente compartilhado via `recognition_shared`)

## Prioridade

Baixa. Comportamento funcional hoje — apenas higiene arquitetural.

## Refs

- `ec44e55` — Sprint 0.5 BLOCO 5 (descoberta original)
- `_count_active_cameras` em `services/api/app/api/v1/health/routes.py`
- Migrations: `024_tenant_schema_function.sql`, `028_quality_module.sql`, `033_quality_rvb.sql`
