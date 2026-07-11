-- 099_recorders.sql
-- Cria tabela recorders: NVRs/DVRs que fornecem playback gravado
-- para extração de frames de treinamento (ADR-0034).
--
-- Por quê: câmeras IP fornecem stream ao vivo (source='auto'/'nvr'
-- via live); recorders fornecem timeline histórica via ONVIF Profile G,
-- Hikvision ISAPI, Dahua/Intelbras para extração source='nvr'.
-- password_encrypted segue padrão Fernet(CAMERA_SECRET_KEY) de
-- camera_service._encrypt_password.
--
-- Após criar a tabela, adiciona FK de training_frames.recorder_id
-- (coluna criada em 094 sem FK pois recorders não existia ainda).
--
-- Idempotência:
--   CREATE TABLE IF NOT EXISTS — no-op se já existir.
--   CHECK via DO $$ EXCEPTION WHEN duplicate_object — idempotente.
--   FK via DO $$ EXCEPTION WHEN duplicate_object — idempotente.
--   CREATE INDEX IF NOT EXISTS — idempotente.
-- Rodar 2× não produz erros.

CREATE TABLE IF NOT EXISTS public.recorders (
    id                 UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id          UUID         NOT NULL REFERENCES public.tenants(id),
    name               VARCHAR(255) NOT NULL,
    host               VARCHAR(255) NOT NULL,
    port               INTEGER      NOT NULL DEFAULT 80,
    username           VARCHAR(255),
    password_encrypted TEXT,
    protocol           VARCHAR(20)  NOT NULL DEFAULT 'onvif',
    manufacturer       VARCHAR(50),
    channels           INTEGER      NOT NULL DEFAULT 0,
    retention_days     INTEGER,
    status             VARCHAR(20)  NOT NULL DEFAULT 'unknown',
    last_tested_at     TIMESTAMPTZ,
    last_error         TEXT,
    created_by         UUID         REFERENCES public.users(id),
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
    ALTER TABLE public.recorders
        ADD CONSTRAINT chk_recorders_protocol
        CHECK (protocol IN ('onvif', 'hikvision', 'dahua', 'intelbras', 'rtsp'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE public.recorders
        ADD CONSTRAINT chk_recorders_status
        CHECK (status IN ('unknown', 'online', 'offline', 'error'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_recorders_tenant
    ON public.recorders(tenant_id);

-- Adicionar FK de training_frames.recorder_id (coluna criada em 094
-- sem referência pois recorders não existia). Idempotente via DO $$.
DO $$
BEGIN
    ALTER TABLE public.training_frames
        ADD CONSTRAINT fk_training_frames_recorder
        FOREIGN KEY (recorder_id) REFERENCES public.recorders(id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;
