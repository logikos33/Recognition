CREATE TABLE IF NOT EXISTS rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    template_type VARCHAR(50),
    event_type VARCHAR(50) NOT NULL,
    event_config JSONB NOT NULL DEFAULT '{}',
    action_type VARCHAR(50) NOT NULL,
    action_config JSONB NOT NULL DEFAULT '{}',
    camera_ids UUID[],
    cooldown_seconds INTEGER NOT NULL DEFAULT 0,
    min_confidence FLOAT NOT NULL DEFAULT 0.5,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rules_user ON rules(user_id);
CREATE INDEX IF NOT EXISTS idx_rules_active ON rules(is_active);

CREATE TABLE IF NOT EXISTS counting_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    camera_id UUID REFERENCES ip_cameras(id) ON DELETE SET NULL,
    bay_id VARCHAR(50),
    truck_plate VARCHAR(20),
    ai_count INTEGER NOT NULL DEFAULT 0,
    operator_count INTEGER,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMP,
    duration_seconds INTEGER,
    status VARCHAR(30) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','pending_validation','validated','rejected')),
    validated_by VARCHAR(200),
    validated_at TIMESTAMP,
    validation_notes TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON counting_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON counting_sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON counting_sessions(started_at DESC);

CREATE TABLE IF NOT EXISTS session_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES counting_sessions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    class_name VARCHAR(100),
    confidence FLOAT,
    details JSONB DEFAULT '{}',
    occurred_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sess_events_session ON session_events(session_id);
CREATE INDEX IF NOT EXISTS idx_sess_events_occurred ON session_events(occurred_at DESC);
