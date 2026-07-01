-- 059_detection_feedback.sql
--
-- Feedback do operador sobre detecções (flywheel / active learning) — melhoria D / task-044.
-- detection_ref/frame_r2_key são TEXT (a evidência vive no R2; detecções em {schema}.*).
-- camera_id é UUID solto (câmeras em {schema}.cameras — sem FK cross-schema).
--
-- Idempotente: CREATE TABLE/INDEX IF NOT EXISTS. Sem DROP.

CREATE TABLE IF NOT EXISTS public.detection_feedback (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    module          TEXT,
    camera_id       UUID,
    detection_ref   TEXT,
    frame_r2_key    TEXT,
    verdict         TEXT NOT NULL CHECK (verdict IN ('correct','wrong','uncertain')),
    corrected_class TEXT,
    created_by      UUID,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_detection_feedback_tenant ON public.detection_feedback (tenant_id);
CREATE INDEX IF NOT EXISTS idx_detection_feedback_module ON public.detection_feedback (tenant_id, module);
