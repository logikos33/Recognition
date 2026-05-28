-- 010_add_module_code.sql
-- Adiciona module_code nas tabelas existentes

-- ip_cameras
DO $$
BEGIN
    ALTER TABLE ip_cameras ADD COLUMN module_code VARCHAR(50) DEFAULT 'epi';
EXCEPTION
    WHEN duplicate_column THEN NULL;
END $$;

-- alerts
DO $$
BEGIN
    ALTER TABLE alerts ADD COLUMN module_code VARCHAR(50) DEFAULT 'epi';
EXCEPTION
    WHEN duplicate_column THEN NULL;
END $$;

-- training_frames
DO $$
BEGIN
    ALTER TABLE training_frames ADD COLUMN module_code VARCHAR(50) DEFAULT 'epi';
EXCEPTION
    WHEN duplicate_column THEN NULL;
END $$;

-- training_videos (se existir)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'training_videos') THEN
        ALTER TABLE training_videos ADD COLUMN IF NOT EXISTS module_code VARCHAR(50) DEFAULT 'epi';
    END IF;
END $$;

-- models (se existir)
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'models') THEN
        ALTER TABLE models ADD COLUMN IF NOT EXISTS module_code VARCHAR(50) DEFAULT 'epi';
    END IF;
END $$;

-- Índices
CREATE INDEX IF NOT EXISTS idx_cameras_module ON ip_cameras(tenant_id, module_code);
CREATE INDEX IF NOT EXISTS idx_alerts_module ON alerts(tenant_id, module_code);
CREATE INDEX IF NOT EXISTS idx_training_frames_module ON training_frames(module_code);
