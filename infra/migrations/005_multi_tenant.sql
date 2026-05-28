-- 005_multi_tenant.sql
-- Adds multi-tenancy support with tenant isolation

-- Create tenants table
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Default tenant for existing data
INSERT INTO tenants (id, name, slug)
VALUES ('00000000-0000-0000-0000-000000000001', 'Default', 'default')
ON CONFLICT DO NOTHING;

-- Add tenant_id to users
ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
UPDATE users SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;

-- Add tenant_id to cameras (works for either `cameras` or `ip_cameras`)
DO $$ BEGIN
    -- Try ip_cameras first (V1 schema)
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ip_cameras') THEN
        ALTER TABLE ip_cameras ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
        UPDATE ip_cameras SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
        CREATE INDEX IF NOT EXISTS idx_ip_cameras_tenant ON ip_cameras(tenant_id);
    END IF;
    -- Try cameras (V2 schema)
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cameras') THEN
        ALTER TABLE cameras ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
        UPDATE cameras SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
        CREATE INDEX IF NOT EXISTS idx_cameras_tenant ON cameras(tenant_id);
    END IF;
END $$;

-- Add tenant_id to alerts
DO $$ BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alerts') THEN
        ALTER TABLE alerts ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
        UPDATE alerts SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
        CREATE INDEX IF NOT EXISTS idx_alerts_tenant ON alerts(tenant_id);
    END IF;
END $$;

-- Add tenant_id to training_jobs if exists
DO $$ BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'training_jobs') THEN
        ALTER TABLE training_jobs ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);
        UPDATE training_jobs SET tenant_id = '00000000-0000-0000-0000-000000000001' WHERE tenant_id IS NULL;
        CREATE INDEX IF NOT EXISTS idx_training_jobs_tenant ON training_jobs(tenant_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
