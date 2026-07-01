-- 052_camera_fps_quality.sql
-- Adiciona controle de FPS e qualidade de stream por câmera.
-- fps_target: frames por segundo alvo para inferência (1/5/10/15/30).
-- quality_preset: preset de qualidade do stream (low/medium/high).
-- Idempotente — seguro rodar múltiplas vezes.
-- Nunca DROP — apenas ADD COLUMN IF NOT EXISTS.

DO $$ BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cameras') THEN
        ALTER TABLE cameras ADD COLUMN IF NOT EXISTS fps_target INTEGER DEFAULT 5;
        ALTER TABLE cameras ADD COLUMN IF NOT EXISTS quality_preset TEXT DEFAULT 'medium';
        COMMENT ON COLUMN cameras.fps_target IS
            'FPS alvo para inferência YOLO. Valores válidos: 1, 5, 10, 15, 30.';
        COMMENT ON COLUMN cameras.quality_preset IS
            'Preset de qualidade do stream. Valores válidos: low, medium, high.';
    END IF;
END $$;

-- Legacy: tabela ip_cameras (V1)
DO $$ BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'ip_cameras') THEN
        ALTER TABLE ip_cameras ADD COLUMN IF NOT EXISTS fps_target INTEGER DEFAULT 5;
        ALTER TABLE ip_cameras ADD COLUMN IF NOT EXISTS quality_preset TEXT DEFAULT 'medium';
    END IF;
END $$;

-- Índice para queries de worker por fps_target (frequente no scheduler de inferência)
DO $$ BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'cameras') THEN
        CREATE INDEX IF NOT EXISTS idx_cameras_fps_target ON cameras (fps_target);
    END IF;
END $$;
