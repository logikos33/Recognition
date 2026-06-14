-- 050_loading_sessions_fields.sql
--
-- CD-03 / CD-06 / CD-07 (Carga & Descarga Fase 1 — Rocabella):
-- estende public.counting_sessions (criada na 049, ADR-0018) com os campos
-- de sessão de carga/descarga: baia, placa do caminhão, direção,
-- esperado/divergência (CD-10 dormante), evidência em vídeo (CD-06) e
-- contagem manual + status de aceite (CD-07 — modo validação/aceite).
--
-- Todas as colunas são NULL para não quebrar sessões existentes
-- (sessões EPI/contagem genérica simplesmente não as preenchem).
--
-- Idempotente: ADD COLUMN IF NOT EXISTS / CREATE INDEX IF NOT EXISTS.
-- Sem DROP, sem ALTER TYPE — forward-only.

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS bay_id UUID;

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS truck_plate TEXT;

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS direction TEXT
        CHECK (direction IN ('load', 'unload'));

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS expected_count INTEGER;

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS divergence INTEGER;

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS video_clip_url TEXT;

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS manual_count INTEGER;

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS acceptance_status TEXT
        CHECK (acceptance_status IN ('pending', 'accepted', 'rejected'));

CREATE INDEX IF NOT EXISTS idx_counting_sessions_tenant_bay
    ON public.counting_sessions (tenant_id, bay_id);
