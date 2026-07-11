-- 094_training_images_sources.sql
-- Estende training_frames para suportar múltiplas fontes de imagens:
-- video (extração de vídeo), upload (batch manual), nvr (playback
-- gravado), auto (captura automática de alertas).
--
-- Por quê: o flywheel de dados exige imagens de múltiplas origens.
-- video_id torna-se opcional — frames de upload/auto não têm vídeo
-- associado. r2_key padroniza a chave R2 (filename era a chave legada:
-- frames/{user_id}/{video_id}/frame_NNNN.jpg).
--
-- Idempotência:
--   ADD COLUMN IF NOT EXISTS — no-op se já existir.
--   CHECK via DO $$ EXCEPTION WHEN duplicate_object — idempotente.
--   DROP NOT NULL via DO $$ EXCEPTION WHEN others — no-op em coluna
--     já nullable (PostgreSQL retorna sem erro).
--   Backfill WHERE IS NULL — idempotente.
--   CREATE INDEX IF NOT EXISTS — idempotente.
-- Rodar 2× não produz erros.

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'video';

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS camera_id UUID REFERENCES public.cameras(id);

-- recorder_id: UUID sem FK aqui; recorders é criada em 099.
-- FK adicionada em 099 após criação da tabela.
ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS recorder_id UUID;

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS r2_key TEXT;

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS captured_at TIMESTAMPTZ;

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS model_confidence DOUBLE PRECISION;

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS width INTEGER;

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS height INTEGER;

-- Backfill r2_key com filename (chave R2 legada) onde ainda não preenchido
UPDATE public.training_frames
   SET r2_key = filename
 WHERE r2_key IS NULL;

-- CHECK de source — guardado em DO $$ para ser idempotente na 2ª execução
DO $$
BEGIN
    ALTER TABLE public.training_frames
        ADD CONSTRAINT chk_training_frames_source
        CHECK (source IN ('auto', 'nvr', 'upload', 'video'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- video_id: tornar nullable para uploads e auto-captura.
-- ADR-0031: justificativa — frames sem vídeo de origem são legítimos.
-- DROP NOT NULL em coluna já nullable é no-op no PostgreSQL 15.
DO $$
BEGIN
    ALTER TABLE public.training_frames
        ALTER COLUMN video_id DROP NOT NULL;
EXCEPTION
    WHEN others THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_training_frames_tenant_source
    ON public.training_frames(tenant_id, source);

CREATE INDEX IF NOT EXISTS idx_training_frames_tenant_annotated
    ON public.training_frames(tenant_id, is_annotated);
