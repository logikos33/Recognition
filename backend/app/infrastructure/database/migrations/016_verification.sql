-- Migration 016: AI verification columns for alerts
-- Idempotente: ADD COLUMN IF NOT EXISTS
-- Safety-net: garante tenant_id caso migration 005 tenha rodado antes da tabela alerts existir

DO $$ BEGIN
    IF EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'alerts'
    ) THEN
        -- Garante tenant_id (005 pode ter skippado se alerts nao existia ainda)
        ALTER TABLE alerts ADD COLUMN IF NOT EXISTS tenant_id UUID;

        ALTER TABLE alerts ADD COLUMN IF NOT EXISTS class_name VARCHAR(100);
        ALTER TABLE alerts ADD COLUMN IF NOT EXISTS verification_status VARCHAR(20) NOT NULL DEFAULT 'pending';
        ALTER TABLE alerts ADD COLUMN IF NOT EXISTS verification_verdict VARCHAR(20);
        ALTER TABLE alerts ADD COLUMN IF NOT EXISTS verification_reason TEXT;
        ALTER TABLE alerts ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
        ALTER TABLE alerts ADD COLUMN IF NOT EXISTS verified_by VARCHAR(50);

        CREATE INDEX IF NOT EXISTS idx_alerts_verification_status
            ON alerts (verification_status);
    END IF;
END $$;
