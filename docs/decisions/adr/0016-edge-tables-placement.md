# ADR-0016: Localização das tabelas de edge — public vs tenant_schema

## Status
Aceito

## Data
2026-05-28

## Contexto

O sistema usa **schema-per-tenant isolation** (descoberto no PR #4, documentado em
`docs/decisions/multi-tenancy-investigation.md`): tabelas de dados tenant-específicos
ficam em `<tenant_schema>.tabela` sem coluna `tenant_id` — o schema PostgreSQL é o
isolamento. Tabelas de infraestrutura global ficam em `public` com `tenant_id`.

As migrations 042-045 do EDGE_DEPLOYMENT_PLAN criam novas tabelas (`edge_sites`,
`device_tokens`, `enrollment_tokens`, `edge_heartbeats`) e adicionam `site_id` a
tabelas existentes. A questão: qual padrão seguir para cada tabela?

**Coexistência dos dois padrões no sistema atual:**

| Padrão | Exemplos | Isolamento |
|--------|---------|------------|
| `public` com `tenant_id` | `operations`, `ip_cameras`, `alerts` | Coluna tenant_id |
| `<tenant_schema>` sem `tenant_id` | `cameras`, `models`, `quality_inspections` | Schema PostgreSQL |

**Problema crítico identificado:** `quality_inspections` existe SOMENTE em `tenant_schema`.
Não há versão em `public`. Um simples `ALTER TABLE quality_inspections ADD COLUMN site_id`
falha porque a tabela não existe no schema `public`.

## Decisão

**Opção C (Híbrido):**

1. **Novas tabelas de controle de edge** → `public` com `tenant_id NOT NULL`
2. **`site_id` em tabelas public** → `ALTER TABLE` simples
3. **`site_id` em tabelas tenant_schema** → loop `EXECUTE format` sobre `tenants.slug`

### Tabelas novas (migrations 042/043)

```sql
-- public.edge_sites — registro de sites físicos de edge
CREATE TABLE IF NOT EXISTS public.edge_sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    location TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- public.device_tokens — credenciais de autenticação de dispositivos edge
CREATE TABLE IF NOT EXISTS public.device_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES public.edge_sites(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);
```

**Justificativa:** edge_sites e device_tokens são infraestrutura de orquestração global —
um site serve um tenant mas é gerenciado pela plataforma cloud. Consistente com `operations`
e `ip_cameras` (também infraestrutura global com tenant_id).

### `site_id` em tabelas existentes (migration 044)

**Tabelas public — ALTER TABLE simples:**
```sql
ALTER TABLE ip_cameras ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id);
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id);
ALTER TABLE counting_events ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id);
ALTER TABLE operations ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id);
```

**`camera_events` — excluída do escopo:**
Tabela criada em migration 002 mas sem uso em runtime (zero referências em `git grep camera_events backend/app/`).
É dead code. Não recebe `site_id`.

**`quality_inspections` (tenant_schema) — loop EXECUTE format:**
```sql
-- migration 044b
DO $$ DECLARE t RECORD; BEGIN
    FOR t IN SELECT slug FROM public.tenants WHERE is_active = true LOOP
        EXECUTE format(
            'ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id)',
            t.slug
        );
    END LOOP;
END $$;
```

**FK qualificada:** tabelas em `tenant_schema` que referenciam `public.edge_sites` devem
usar o schema explícito `REFERENCES public.edge_sites(id)` (não apenas `REFERENCES edge_sites(id)`),
porque o `search_path` resolve `edge_sites` para o schema do tenant primeiro, onde a tabela
não existe.

### Atualização de `create_tenant_schema()`

A função `public.create_tenant_schema(p_schema_name TEXT)` deve ser atualizada para incluir
`site_id` nos DDL das tabelas relevantes (ex: `quality_inspections`), garantindo que tenants
criados após migration 044 também tenham a coluna.

```sql
CREATE OR REPLACE FUNCTION public.create_tenant_schema(p_schema_name TEXT)
RETURNS void AS $$
BEGIN
    -- ... DDLs existentes ...
    EXECUTE format('
        CREATE TABLE IF NOT EXISTS %I.quality_inspections (
            ...
            site_id UUID REFERENCES public.edge_sites(id),
            ...
        )', p_schema_name);
END;
$$ LANGUAGE plpgsql;
```

## Alternativas Consideradas

### A: Tudo em `public` com `tenant_id`
- Prós: consistente e simples para todas as migrations
- Contras: diverge do padrão tenant_schema já estabelecido para quality_*; `quality_inspections`
  em public exigiria migration de dados (não temos dados ainda, mas cria divergência de padrão)

### B: Tudo em `tenant_schema` sem `tenant_id`
- Prós: isola completamente por schema
- Contras: dashboard global de edge (ver todos os sites de um tenant) requer UNION sobre schemas;
  device_tokens (dado de segurança) em tenant_schema complica revogação global

### C: Híbrido **(ESCOLHIDA)**
- Prós: segue a localização real de cada tabela; dashboard edge trivial (tudo em public);
  FK de security em public; sem migration de dados
- Contras: duas estratégias diferentes para `site_id` (ALTER vs EXECUTE format loop);
  `create_tenant_schema()` precisa de manutenção ativa

## Consequências

### Positivas
- Dashboard global de edge (listar todos os sites de um tenant) é query simples em public
- `device_tokens` em public facilita revogação global de tokens
- Migrations 042/043/044 de tabelas public são triviais
- FK `public.edge_sites` → `public.tenants` mantém integridade referencial

### Negativas
- Migration 044b requer loop sobre `tenants.slug` — pattern não convencional
- `create_tenant_schema()` precisa ser atualizada sempre que uma nova coluna `site_id`-related
  for adicionada a tabelas tenant_schema
- FK qualificada (`REFERENCES public.edge_sites(id)`) é necessária em todas as tabelas
  tenant_schema que referenciam edge_sites

### Neutras
- `tenant_schema.alerts` e `tenant_schema.camera_events` são dead code — não afetam decisão

## Referências

- OQ-008 em `docs/decisions/open-questions.md`
- `docs/decisions/multi-tenancy-investigation.md` — mapa completo PUBLIC vs TENANT_SCHEMA (§7)
- Migration 024: `backend/app/infrastructure/database/migrations/024_tenant_schema_function.sql`
- EDGE_DEPLOYMENT_PLAN.md — Fase 1, migrations 042-045
