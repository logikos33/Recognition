-- 098_models_registry_lineage.sql
-- Estende trained_models com campos de linhagem do registry MLOps:
-- framework, chaves R2 de artefatos (onnx/pesos), metrics detalhadas
-- por classe, dataset_version_id e module_code.
--
-- Por quê: trained_models é o registry canônico (ADR-0031). Os novos
-- campos permitem rastrear linhagem completa (dataset_version → job →
-- modelo) e localizar artefatos no R2 sem depender do model_path legado.
-- metrics aqui é por classe (mAP, P, R, matriz de confusão resumida) —
-- complementa map50/precision/recall já existentes.
--
-- tenant_id, created_by e origin já existem desde a migration 090.
-- idx_trained_models_tenant já existe (090); não recriar.
--
-- Idempotência:
--   ADD COLUMN IF NOT EXISTS — no-op se já existir.
--   CREATE INDEX IF NOT EXISTS — idempotente.
-- Rodar 2× não produz erros.

ALTER TABLE public.trained_models
    ADD COLUMN IF NOT EXISTS framework VARCHAR(20);

ALTER TABLE public.trained_models
    ADD COLUMN IF NOT EXISTS r2_onnx_key TEXT;

ALTER TABLE public.trained_models
    ADD COLUMN IF NOT EXISTS r2_weights_key TEXT;

-- metrics: métricas detalhadas por classe; complementa map50/precision/recall
ALTER TABLE public.trained_models
    ADD COLUMN IF NOT EXISTS metrics JSONB NOT NULL DEFAULT '{}';

ALTER TABLE public.trained_models
    ADD COLUMN IF NOT EXISTS dataset_version_id UUID REFERENCES public.dataset_versions(id);

ALTER TABLE public.trained_models
    ADD COLUMN IF NOT EXISTS module_code VARCHAR(50) NOT NULL DEFAULT 'epi';

-- Índice para lookup de modelo ativo por tenant+módulo (inference resolver)
CREATE INDEX IF NOT EXISTS idx_trained_models_tenant_module
    ON public.trained_models(tenant_id, module_code, is_active);

-- Índice para linhagem job → modelo (GET /api/v1/models/<id> expandido)
CREATE INDEX IF NOT EXISTS idx_trained_models_job
    ON public.trained_models(job_id);
