-- Migration 016: AI verification columns for alerts
-- Idempotente: ADD COLUMN IF NOT EXISTS

ALTER TABLE alerts ADD COLUMN IF NOT EXISTS class_name VARCHAR(100);
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS verification_status VARCHAR(20) NOT NULL DEFAULT 'pending';
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS verification_verdict VARCHAR(20);
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS verification_reason TEXT;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS verified_by VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_alerts_verification_status
    ON alerts (verification_status);
