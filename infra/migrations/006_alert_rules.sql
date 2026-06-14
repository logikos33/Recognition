-- 006_alert_rules.sql
-- Alert rules with duration/occurrence conditions

CREATE TABLE IF NOT EXISTS alert_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    camera_id UUID,  -- NULL = all cameras for tenant
    violation_type VARCHAR(50) NOT NULL,
    min_duration_seconds INTEGER DEFAULT 3,
    min_occurrences INTEGER,
    time_window_seconds INTEGER,
    create_alert BOOLEAN DEFAULT TRUE,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_rules_tenant ON alert_rules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_alert_rules_camera ON alert_rules(camera_id) WHERE camera_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled) WHERE enabled = true;

-- Default rules for existing tenants
INSERT INTO alert_rules (tenant_id, violation_type, min_duration_seconds, create_alert)
SELECT id, 'no_helmet', 3, true FROM tenants
ON CONFLICT DO NOTHING;

INSERT INTO alert_rules (tenant_id, violation_type, min_duration_seconds, create_alert)
SELECT id, 'no_vest', 3, true FROM tenants
ON CONFLICT DO NOTHING;
