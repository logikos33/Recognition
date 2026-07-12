-- ============================================================
-- Migration 090 — Dono, origem e tenant em trained_models (WS5)
--   Adiciona created_by (dono), origin (proveniência do treino) e
--   tenant_id (isolamento multi-tenant C-01) à tabela trained_models.
--   Backfills idempotentes: só atualizam linhas ainda não preenchidas.
--
-- Valores de origin (sem CHECK — mapeados na UI):
--   'vast_ai' | 'ultralytics_hub' | 'colab' | 'simulated'
--   | 'training_service' | 'unknown'
--
-- Forward-only e idempotente: seguro rodar múltiplas vezes.
-- Nunca DROP — apenas ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS.
-- ============================================================

ALTER TABLE public.trained_models
  ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id);

ALTER TABLE public.trained_models
  ADD COLUMN IF NOT EXISTS origin VARCHAR(30) NOT NULL DEFAULT 'unknown';

ALTER TABLE public.trained_models
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);

CREATE INDEX IF NOT EXISTS idx_trained_models_tenant
  ON public.trained_models(tenant_id);

COMMENT ON COLUMN public.trained_models.created_by IS
  'Usuário que disparou o treino (dono do modelo). Default histórico: user_id.';

COMMENT ON COLUMN public.trained_models.origin IS
  'Proveniência do treino: vast_ai | ultralytics_hub | colab | simulated | training_service | unknown';

COMMENT ON COLUMN public.trained_models.tenant_id IS
  'Tenant dono do modelo (C-01). Backfill via users.tenant_id.';

-- Backfills idempotentes (apenas linhas ainda não preenchidas)

UPDATE public.trained_models
   SET created_by = user_id
 WHERE created_by IS NULL;

UPDATE public.trained_models tm
   SET tenant_id = u.tenant_id
  FROM users u
 WHERE tm.user_id = u.id
   AND tm.tenant_id IS NULL;

UPDATE public.trained_models
   SET origin = 'vast_ai'
 WHERE origin = 'unknown'
   AND model_path LIKE '%/vast/%';
