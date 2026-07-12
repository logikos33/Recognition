-- Migration 052: integrations store (credenciais cifradas por tenant)
-- Idempotente: usa IF NOT EXISTS em todos os DDLs.
-- Forward-only: sem DROP, sem ALTER COLUMN TYPE.

CREATE TABLE IF NOT EXISTS public.integrations (
  id               UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  tenant_id        UUID        NOT NULL REFERENCES public.tenants(id),
  integration_type TEXT        NOT NULL,
  -- 'r2' | 'vast_ai' | 'generic_gpu' | 'notification' | 'byo_db'
  label            TEXT        NOT NULL,
  -- nome amigável p/ display
  config           JSONB       NOT NULL DEFAULT '{}',
  -- campos não-sensíveis: bucket, endpoint, region, url…
  secret_encrypted TEXT,
  -- Fernet(chave/secret completa)
  last4            TEXT,
  -- últimos 4 chars do secret original (display: ••••XXXX)
  status           TEXT        NOT NULL DEFAULT 'unconfigured',
  -- 'unconfigured' | 'ok' | 'error'
  last_tested_at   TIMESTAMPTZ,
  last_error       TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, integration_type, label)
);

CREATE INDEX IF NOT EXISTS idx_integrations_tenant
  ON public.integrations (tenant_id, integration_type);

CREATE INDEX IF NOT EXISTS idx_integrations_status
  ON public.integrations (status, updated_at DESC);
