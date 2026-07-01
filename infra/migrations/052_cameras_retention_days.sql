-- 052_cameras_retention_days.sql
--
-- Adiciona coluna retention_days à tabela public.cameras.
-- NULL significa "herdar o default do tenant" (tenants.video_retention_days).
-- Os tiers suportados são 1, 7, 30, 90 dias.
--
-- Idempotente — ADD COLUMN IF NOT EXISTS.

ALTER TABLE public.cameras
    ADD COLUMN IF NOT EXISTS retention_days INT DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_cameras_retention_days
    ON public.cameras (retention_days)
    WHERE retention_days IS NOT NULL;
