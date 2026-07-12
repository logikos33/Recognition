-- 100_model_deployments.sql
-- Cria tabela model_deployments: vínculo auditável entre modelo
-- treinado, câmera e módulo, com configuração de geometria e histórico
-- de rollbacks (ADR-0032).
--
-- Por quê: {schema}.models gerencia pin/canary ativo por módulo (acesso
-- rápido pelo inference worker); esta tabela registry-level rastreia
-- HISTÓRICO completo de deployments, configurações de geometria
-- (ROI, linhas de contagem, classes habilitadas, thresholds por classe)
-- e permite rollback (reativar deployment anterior). Separação mantém
-- a semântica de cada tabela clara (ADR-0037).
--
-- config JSONB: {roi: [[x,y],...], line: [[x,y],[x,y]], classes: [],
--               thresholds: {"helmet": 0.6, ...}}
-- Geometrias normalizadas 0..1 (validação server-side no handler).
--
-- Idempotência:
--   CREATE TABLE IF NOT EXISTS — no-op se já existir.
--   CHECK via DO $$ EXCEPTION WHEN duplicate_object — idempotente.
--   CREATE INDEX IF NOT EXISTS — idempotente.
-- Rodar 2× não produz erros.

CREATE TABLE IF NOT EXISTS public.model_deployments (
    id             UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id      UUID        NOT NULL REFERENCES public.tenants(id),
    model_id       UUID        NOT NULL REFERENCES public.trained_models(id),
    camera_id      UUID        NOT NULL REFERENCES public.cameras(id),
    module_code    VARCHAR(50) NOT NULL DEFAULT 'epi',
    config         JSONB       NOT NULL DEFAULT '{}',
    status         VARCHAR(20) NOT NULL DEFAULT 'active',
    deployed_by    UUID        REFERENCES public.users(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deactivated_at TIMESTAMPTZ
);

DO $$
BEGIN
    ALTER TABLE public.model_deployments
        ADD CONSTRAINT chk_model_deployments_status
        CHECK (status IN ('active', 'inactive', 'rolled_back'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Índice principal: lookup de deployment ativo por câmera+módulo
-- (inference resolver e GET /api/cameras/<id>/model-config)
CREATE INDEX IF NOT EXISTS idx_model_deployments_camera_module
    ON public.model_deployments(tenant_id, camera_id, module_code, status);

-- Índice de linhagem: todos os deployments de um modelo
-- (GET /api/v1/models/<id> — detalhe expandido)
CREATE INDEX IF NOT EXISTS idx_model_deployments_model
    ON public.model_deployments(model_id);
