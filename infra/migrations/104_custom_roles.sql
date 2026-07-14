-- Migration 052: Custom roles por tenant (deliverable k)
-- Regras:
--   - Apenas CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS (append-only)
--   - Toda tabela com tenant_id (multi-tenant)
--   - Idempotente: rodar 2x sem erro

-- Tabela de roles customizadas por tenant
CREATE TABLE IF NOT EXISTS public.custom_roles (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID        NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    permissions JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS custom_roles_tenant_name
    ON public.custom_roles (tenant_id, name);

CREATE INDEX IF NOT EXISTS custom_roles_tenant_idx
    ON public.custom_roles (tenant_id);

-- Coluna custom_role_id em users para apontar para role customizada
-- (não substitui a coluna role existente — complementa para permissões granulares)
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS custom_role_id UUID REFERENCES public.custom_roles(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS users_custom_role_idx
    ON public.users (custom_role_id)
    WHERE custom_role_id IS NOT NULL;
