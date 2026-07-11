-- 101_model_eval_drift.sql
-- Cria model_evaluations (avaliação campeão×desafiante) e
-- model_drift_metrics (monitoramento de drift por janela temporal).
--
-- Por quê: o pipeline MLOps exige gate de avaliação antes de ativar
-- um modelo (ADR-0031 — seção "Ciclo de vida"). model_evaluations
-- registra o resultado da comparação campeão×desafiante com métricas
-- por classe, matriz de confusão e verdict (promote/reject). Sem
-- campeão → verdict = promote automático.
--
-- model_drift_metrics suporta o Celery beat compute_drift_metrics
-- (diário): agrega alerts por câmera×modelo em janela de 24h,
-- calcula drift_score = |avg_conf - baseline| + L1(class_distribution).
-- drift_score alto → log + gancho check_auto_retraining (stub honesto).
--
-- verdict: 'promote' se mAP_challenger >= mAP_champion - 0.01 e
-- nenhuma classe crítica cai >5pp; 'reject' caso contrário.
--
-- Idempotência:
--   CREATE TABLE IF NOT EXISTS — no-op se já existir.
--   CHECK via DO $$ EXCEPTION WHEN duplicate_object — idempotente.
--   CREATE INDEX IF NOT EXISTS — idempotente.
-- Rodar 2× não produz erros.

CREATE TABLE IF NOT EXISTS public.model_evaluations (
    id                 UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id          UUID        NOT NULL REFERENCES public.tenants(id),
    model_id           UUID        REFERENCES public.trained_models(id),
    champion_model_id  UUID        REFERENCES public.trained_models(id),
    dataset_version_id UUID        REFERENCES public.dataset_versions(id),
    metrics            JSONB       NOT NULL DEFAULT '{}',
    confusion_matrix   JSONB,
    verdict            VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
    ALTER TABLE public.model_evaluations
        ADD CONSTRAINT chk_model_evaluations_verdict
        CHECK (verdict IN ('pending', 'promote', 'reject'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Lookup por tenant+modelo (GET /api/v1/models/<id>/eval)
CREATE INDEX IF NOT EXISTS idx_model_evaluations_tenant_model
    ON public.model_evaluations(tenant_id, model_id);

-- Lookup de avaliações pendentes para o gate de activate
CREATE INDEX IF NOT EXISTS idx_model_evaluations_verdict
    ON public.model_evaluations(verdict, created_at DESC);

CREATE TABLE IF NOT EXISTS public.model_drift_metrics (
    id                 UUID             NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id          UUID             NOT NULL REFERENCES public.tenants(id),
    model_id           UUID             REFERENCES public.trained_models(id),
    camera_id          UUID             REFERENCES public.cameras(id),
    window_start       TIMESTAMPTZ,
    window_end         TIMESTAMPTZ,
    detections_count   INTEGER          NOT NULL DEFAULT 0,
    avg_confidence     DOUBLE PRECISION,
    class_distribution JSONB,
    drift_score        DOUBLE PRECISION,
    created_at         TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

-- Lookup por tenant+modelo+janela (GET /api/v1/models/<id>/drift)
CREATE INDEX IF NOT EXISTS idx_model_drift_metrics_tenant_model
    ON public.model_drift_metrics(tenant_id, model_id, window_start DESC);

-- Lookup por câmera para o beat diário (agrupamento por câmera×modelo)
CREATE INDEX IF NOT EXISTS idx_model_drift_metrics_camera
    ON public.model_drift_metrics(camera_id, window_start DESC);
