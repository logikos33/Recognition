-- 061 — Branding JSONB por tenant (white-label theming / task-048)
-- Idempotente: ADD COLUMN IF NOT EXISTS; seguro rodar 2x
-- Não faz DROP, não altera tipos, não apaga dados.
ALTER TABLE public.tenants
  ADD COLUMN IF NOT EXISTS branding JSONB NOT NULL DEFAULT '{}'::jsonb;
