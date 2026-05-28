-- Migration 012: campos adicionais para gerenciamento de câmeras
-- Adiciona rastreamento de erros, testes e timestamp de atualização

DO $$ BEGIN
    ALTER TABLE ip_cameras ADD COLUMN last_error TEXT;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;

DO $$ BEGIN
    ALTER TABLE ip_cameras ADD COLUMN last_tested_at TIMESTAMP WITH TIME ZONE;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;

DO $$ BEGIN
    ALTER TABLE ip_cameras ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE;
EXCEPTION WHEN duplicate_column THEN NULL; END $$;

-- Índice para listagem por usuário + status
CREATE INDEX IF NOT EXISTS idx_cameras_user_active ON ip_cameras(user_id, is_active);
