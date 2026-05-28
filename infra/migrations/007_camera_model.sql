-- 007_camera_model.sql
-- Model registry and camera-model association

CREATE TABLE IF NOT EXISTS models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    model_key VARCHAR(500) NOT NULL,
    metrics JSONB DEFAULT '{}',
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_models_tenant ON models(tenant_id);

-- Add active_model_id to cameras (either ip_cameras or cameras table)
DO $$ BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cameras') THEN
        ALTER TABLE cameras ADD COLUMN IF NOT EXISTS active_model_id UUID REFERENCES models(id);
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ip_cameras') THEN
        ALTER TABLE ip_cameras ADD COLUMN IF NOT EXISTS active_model_id UUID REFERENCES models(id);
    END IF;
END $$;
