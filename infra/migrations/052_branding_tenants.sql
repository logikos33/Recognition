-- 052_branding_tenants.sql
-- Adiciona coluna branding JSONB à tabela public.tenants para white-label por tenant (task-048).
-- Idempotente: ADD COLUMN IF NOT EXISTS
--
-- Estrutura esperada do JSONB:
--   {
--     "product_name":    "Recognition",
--     "color_primary":   "#06b6d4",
--     "color_secondary": "#ea580c",
--     "logo_url":        "https://...",
--     "favicon_url":     "https://..."
--   }

ALTER TABLE public.tenants
  ADD COLUMN IF NOT EXISTS branding JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN public.tenants.branding IS
  'White-label overrides: {product_name, color_primary, color_secondary, logo_url, favicon_url}';
