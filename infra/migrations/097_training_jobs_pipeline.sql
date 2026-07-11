-- 097_training_jobs_pipeline.sql
-- Estende training_jobs com campos do pipeline MLOps: dataset_version_id,
-- framework, base_model, hyperparams, gpu_provider, gpu_instance_ref e
-- callback_token.
--
-- Por quê: o job precisa rastrear qual dataset_version originou o treino,
-- qual framework (rfdetr/yolox) foi usado, hiperparâmetros da execução e
-- referência da instância GPU para monitoramento/destruição.
--
-- callback_token (Ajuste Arquitetural C-1): token aleatório por job
-- (secrets.token_urlsafe(48) → 64 chars URL-safe) em vez de HMAC
-- determinístico. Revogado no stop; validado no endpoint
-- POST /api/v1/training/jobs/<id>/progress-callback.
--
-- tenant_id já existe desde a migration 005; apenas backfill de legados
-- e novo índice composto para queries por tenant+status.
--
-- Idempotência:
--   ADD COLUMN IF NOT EXISTS — no-op se já existir.
--   Backfill WHERE IS NULL — idempotente.
--   CREATE INDEX IF NOT EXISTS — idempotente.
-- Rodar 2× não produz erros.

ALTER TABLE public.training_jobs
    ADD COLUMN IF NOT EXISTS dataset_version_id UUID REFERENCES public.dataset_versions(id);

ALTER TABLE public.training_jobs
    ADD COLUMN IF NOT EXISTS framework VARCHAR(20) NOT NULL DEFAULT 'rfdetr';

ALTER TABLE public.training_jobs
    ADD COLUMN IF NOT EXISTS base_model VARCHAR(50);

ALTER TABLE public.training_jobs
    ADD COLUMN IF NOT EXISTS hyperparams JSONB NOT NULL DEFAULT '{}';

ALTER TABLE public.training_jobs
    ADD COLUMN IF NOT EXISTS gpu_provider VARCHAR(20);

ALTER TABLE public.training_jobs
    ADD COLUMN IF NOT EXISTS gpu_instance_ref TEXT;

-- callback_token: token por-job para autenticar o endpoint de progresso.
-- Gerado em dispatch; NULL = job não iniciou ou já parou.
ALTER TABLE public.training_jobs
    ADD COLUMN IF NOT EXISTS callback_token VARCHAR(64);

-- Backfill tenant_id de legados sem tenant (coluna existe desde 005)
UPDATE public.training_jobs tj
   SET tenant_id = u.tenant_id
  FROM public.users u
 WHERE tj.user_id = u.id
   AND tj.tenant_id IS NULL;

UPDATE public.training_jobs
   SET tenant_id = '00000000-0000-0000-0000-000000000001'
 WHERE tenant_id IS NULL;

-- Índice composto para queries por tenant+status (diferente do
-- idx_training_jobs_tenant criado em 005 que é só por tenant_id)
CREATE INDEX IF NOT EXISTS idx_training_jobs_tenant_status
    ON public.training_jobs(tenant_id, status);
