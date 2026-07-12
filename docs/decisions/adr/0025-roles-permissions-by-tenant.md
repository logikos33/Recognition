# ADR-0025 — Roles and Permissions by Tenant

## Status: Accepted (2026-07-01)

## Contexto

O sistema atual tem três roles fixos definidos em código (`super_admin`, `admin`, `operator`),
hardcoded em `app/constants.py` (enum `UserRole`). Isso é suficiente para o MVP, mas
clientes enterprise precisam de granularidade maior:

- Tenant A quer um role "supervisor" que vê alertas mas não configura câmeras
- Tenant B quer "auditor" com acesso read-only a relatórios e exportação
- Super-admin da plataforma precisa impersonar qualquer tenant para suporte

O modelo atual não suporta customização por tenant: qualquer mudança de role afeta
todos os tenants.

Alternativas consideradas:

| Abordagem | Descrição | Descartada porque |
|-----------|-----------|-------------------|
| Enum fixo ampliado | Adicionar mais roles ao enum | Não customizável por tenant |
| ABAC (attribute-based) | Permissões por atributo de recurso | Complexidade excessiva para MVP |
| **RBAC por tenant com JSONB** | Tabela `{schema}.roles` com permissions JSONB | Simples, flexível, já usa psycopg2+JSONB |

## Decisão

Implementar RBAC customizável por tenant:

### Schema

```sql
-- Migration: criar na migration numerada adequada
CREATE TABLE IF NOT EXISTS {schema}.roles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    name        TEXT NOT NULL,
    description TEXT,
    permissions JSONB NOT NULL DEFAULT '[]',
    is_system   BOOLEAN NOT NULL DEFAULT false,  -- roles padrão não deletáveis
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

-- Roles padrão são criados como is_system=true por migration seed (não hardcoded)
-- permissions exemplo: ["cameras:read", "cameras:write", "alerts:read", "reports:export"]
```

### Permissões como strings hierárquicas

Formato: `{recurso}:{ação}` com suporte a wildcard `{recurso}:*`.

Recursos: `cameras`, `alerts`, `rules`, `models`, `training`, `reports`,
`users`, `roles`, `modules`, `settings`.

Ações: `read`, `write`, `delete`, `export`, `admin`.

### Verificação no backend

```python
# app/core/auth.py — novo helper
def require_permission(permission: str):
    """Decorator que verifica se o usuário tem a permissão no tenant."""
    # Carrega roles do usuário → expande permissions JSONB → checa wildcard
    # Super-admin (role global) bypassa todas as verificações
```

### Endpoint CRUD

- `GET  /api/roles` — lista roles do tenant (tenant admin) ou todos (super-admin)
- `POST /api/roles` — cria role customizado (apenas tenant admin)
- `PUT  /api/roles/{id}` — atualiza permissions (não permite editar is_system=true)
- `DELETE /api/roles/{id}` — remove role customizado (bloqueia is_system=true)
- `PUT  /api/users/{id}/role` — atribui role a usuário do tenant

### Visibilidade

- Super-admin vê e gerencia roles de todos os tenants.
- Tenant admin vê e gerencia apenas roles do próprio tenant.
- Operator não acessa o módulo de gestão de roles.

### UX no admin

Nova seção "Perfis de Acesso" no painel administrativo do tenant:
tabela de roles com botão de edição de permissões via checklist.
Usa `<Drawer>` (ADR-0023) para o formulário de edição.

## Consequências

- Flexibilidade enterprise: tenants definem granularidade sem deploy.
- Migração necessária: usuários existentes recebem roles padrão (`is_system=true`)
  criados pela migration seed.
- Risco de misconfiguration: tenant admin pode criar role com permissões excessivas.
  Mitigação: validação no backend impede permissions fora do enum definido.
- Super-admin bypass é explícito no código — não implícito — reduzindo risco de
  privilege escalation acidental.
- Débito: roles fixos em `UserRole` enum permanecem para compatibilidade retroativa
  durante período de migração; remover em sprint de limpeza após rollout completo.
