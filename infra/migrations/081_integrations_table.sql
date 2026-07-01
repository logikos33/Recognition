-- Migration 081: integrations table (task-056 — admin test console secrets)
-- Armazena chaves de integração cifradas por tenant (Vast.ai, etc.)
-- Idempotente: CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS

CREATE TABLE IF NOT EXISTS public.integrations (
    id          UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id   UUID        NOT NULL REFERENCES public.tenants(id),
    key         TEXT        NOT NULL,
    value_encrypted TEXT    NOT NULL,
    created_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, key)
);

CREATE INDEX IF NOT EXISTS idx_integrations_tenant_id
    ON public.integrations (tenant_id);
