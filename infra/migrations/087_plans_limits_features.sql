-- ============================================================
-- 087 — Plans: limites de usuários e funcionalidades por módulo (WS8)
--
-- Forward-only e idempotente (rodável 2x sem erro).
--
-- NOTA (exceção consciente à regra de tenant_id): public.plans é
-- tabela GLOBAL de plataforma (padrão pré-existente da 029, como
-- platform_feature_flags) — não recebe tenant_id.
--
-- Semântica das colunas novas:
--   max_users       INT  — NULL = ilimitado (não-regressivo: planos
--                          existentes ficam NULL). Herança em runtime:
--                          COALESCE(tenants.max_seats, plans.max_users).
--   module_features JSONB — {"epi": ["vms","alerts"], ...}. Chave ausente
--                          ou lista vazia = TODAS as funcionalidades do
--                          módulo liberadas (backward-compatible).
-- ============================================================

ALTER TABLE public.plans
  ADD COLUMN IF NOT EXISTS max_users INT,
  ADD COLUMN IF NOT EXISTS module_features JSONB DEFAULT '{}';

-- Flag global de enforcement dos limites do plano (default OFF).
-- Ligável pela UI existente de Feature Flags (/admin — superadmin).
INSERT INTO public.platform_feature_flags (flag_key, flag_value, description)
VALUES (
  'enforce_plan_limits',
  false,
  'Aplica limites do plano (módulos e câmeras) em runtime'
)
ON CONFLICT (flag_key) DO NOTHING;
