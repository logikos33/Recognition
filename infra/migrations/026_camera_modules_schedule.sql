-- 026_camera_modules_schedule.sql
-- Adiciona campos de módulo ativo, agendamento e modelos às câmeras.
-- Idempotente — seguro rodar múltiplas vezes.

-- Para tabela cameras (schema V2)
DO $$ BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cameras') THEN
        ALTER TABLE cameras ADD COLUMN IF NOT EXISTS active_module VARCHAR(50) DEFAULT 'epi';
        ALTER TABLE cameras ADD COLUMN IF NOT EXISTS schedule_rules JSONB DEFAULT '[]';
        ALTER TABLE cameras ADD COLUMN IF NOT EXISTS model_epi_id UUID;
        ALTER TABLE cameras ADD COLUMN IF NOT EXISTS model_quality_id UUID;
        ALTER TABLE cameras ADD COLUMN IF NOT EXISTS model_counting_id UUID;
        COMMENT ON COLUMN cameras.active_module IS
            'Módulo ativo padrão: epi | quality | counting | basic | none';
        COMMENT ON COLUMN cameras.schedule_rules IS
            'Regras de agendamento JSONB. Ex: [{"days":[1,2,3,4,5],"start":"08:00","end":"18:00","module":"epi"}]';
    END IF;
END $$;

-- Para tabela ip_cameras (schema V1 legacy)
DO $$ BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ip_cameras') THEN
        ALTER TABLE ip_cameras ADD COLUMN IF NOT EXISTS active_module VARCHAR(50) DEFAULT 'epi';
        ALTER TABLE ip_cameras ADD COLUMN IF NOT EXISTS schedule_rules JSONB DEFAULT '[]';
        ALTER TABLE ip_cameras ADD COLUMN IF NOT EXISTS model_epi_id UUID;
        ALTER TABLE ip_cameras ADD COLUMN IF NOT EXISTS model_quality_id UUID;
        ALTER TABLE ip_cameras ADD COLUMN IF NOT EXISTS model_counting_id UUID;
    END IF;
END $$;

-- Index para queries de módulo ativo (frequente no worker de inferência)
DO $$ BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cameras') THEN
        CREATE INDEX IF NOT EXISTS idx_cameras_active_module ON cameras(active_module);
    END IF;
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ip_cameras') THEN
        CREATE INDEX IF NOT EXISTS idx_ip_cameras_active_module ON ip_cameras(active_module);
    END IF;
END $$;
