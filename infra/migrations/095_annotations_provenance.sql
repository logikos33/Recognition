-- 095_annotations_provenance.sql
-- Adiciona proveniência a frame_annotations: source (manual vs
-- pré-anotação automática), created_by (quem anotou) e reviewed_by
-- (quem aceitou/rejeitou a sugestão).
--
-- Por quê: o fluxo accept-suggestions (pre_annotations JSONB →
-- frame_annotations) exige distinguir anotações manuais de sugestões
-- aceitas para auditoria e métricas de qualidade do modelo de pré-
-- anotação.
--
-- Idempotência:
--   ADD COLUMN IF NOT EXISTS — no-op se já existir.
--   CHECK via DO $$ EXCEPTION WHEN duplicate_object — idempotente.
-- Rodar 2× não produz erros.

ALTER TABLE public.frame_annotations
    ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'manual';

ALTER TABLE public.frame_annotations
    ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES public.users(id);

ALTER TABLE public.frame_annotations
    ADD COLUMN IF NOT EXISTS reviewed_by UUID REFERENCES public.users(id);

-- CHECK de source — guardado em DO $$ para idempotência
DO $$
BEGIN
    ALTER TABLE public.frame_annotations
        ADD CONSTRAINT chk_frame_annotations_source
        CHECK (source IN ('manual', 'pre_annotation'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;
