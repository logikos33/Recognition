-- Migration 015: counting sessions + events for DeepSORT anti-duplicate counting
-- Idempotente: CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS

CREATE TABLE IF NOT EXISTS counting_sessions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      UUID NOT NULL REFERENCES tenants(id),
    camera_id      UUID NOT NULL REFERENCES cameras(id),
    module_code    VARCHAR(50) NOT NULL,
    status         VARCHAR(20) NOT NULL DEFAULT 'running',
    started_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at       TIMESTAMPTZ,
    total_counts   JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS counting_events (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id     UUID NOT NULL REFERENCES counting_sessions(id) ON DELETE CASCADE,
    track_id       INTEGER NOT NULL,
    class_name     VARCHAR(100) NOT NULL,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at   TIMESTAMPTZ,
    confidence     FLOAT,
    UNIQUE (session_id, track_id)
);

CREATE INDEX IF NOT EXISTS idx_counting_sessions_tenant_id
    ON counting_sessions (tenant_id);

CREATE INDEX IF NOT EXISTS idx_counting_sessions_camera_id
    ON counting_sessions (camera_id);

CREATE INDEX IF NOT EXISTS idx_counting_sessions_status
    ON counting_sessions (status);

CREATE INDEX IF NOT EXISTS idx_counting_events_session_id
    ON counting_events (session_id);
