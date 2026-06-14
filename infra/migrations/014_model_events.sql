-- Migration 014: model activation audit log
-- Idempotente: CREATE TABLE IF NOT EXISTS

CREATE TABLE IF NOT EXISTS model_activation_log (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id       UUID NOT NULL,
    activated_by   UUID NOT NULL,
    activated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    previous_model_id UUID
);

CREATE INDEX IF NOT EXISTS idx_model_activation_log_model_id
    ON model_activation_log (model_id);

CREATE INDEX IF NOT EXISTS idx_model_activation_log_activated_by
    ON model_activation_log (activated_by);
