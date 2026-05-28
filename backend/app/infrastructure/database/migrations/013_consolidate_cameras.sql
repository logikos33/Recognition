-- 013_consolidate_cameras.sql
-- Resolve ambiguidade ip_cameras vs cameras.
-- Se ip_cameras existe e cameras não, renomeia.
-- Se ambas existem, mantém cameras e cria view ip_cameras.

DO $$
BEGIN
    -- Caso 1: só ip_cameras existe → renomear para cameras
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ip_cameras' AND table_schema = 'public')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'cameras' AND table_schema = 'public') THEN
        ALTER TABLE ip_cameras RENAME TO cameras;
        RAISE NOTICE 'ip_cameras renomeada para cameras';
    END IF;

    -- Caso 2: ambas existem → criar view de compatibilidade
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ip_cameras' AND table_schema = 'public')
       AND EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'cameras' AND table_schema = 'public') THEN
        -- Mover dados que só existem em ip_cameras
        INSERT INTO cameras (id, user_id, name, host, port, username, password_encrypted,
                             manufacturer, channel, subtype, location, is_active, created_at)
        SELECT id, user_id, name, host, port, username, password_encrypted,
               manufacturer, channel, subtype, location, is_active, created_at
        FROM ip_cameras
        WHERE id NOT IN (SELECT id FROM cameras)
        ON CONFLICT (id) DO NOTHING;

        DROP TABLE ip_cameras CASCADE;
        RAISE NOTICE 'ip_cameras migrada e dropada — cameras é a tabela canônica';
    END IF;
END $$;

-- Garantir índices na tabela cameras (independente do caso)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'cameras' AND table_schema = 'public') THEN
        CREATE INDEX IF NOT EXISTS idx_cameras_user ON cameras(user_id);
        CREATE INDEX IF NOT EXISTS idx_cameras_active ON cameras(is_active);
    END IF;
END $$;
