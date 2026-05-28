-- Migration 037: Tabela de vídeos demo para modo demonstração (superadmin only)
-- Vídeos MP4 armazenados no R2 que substituem o feed HLS durante demos comerciais.
-- NUNCA retornados para tenants clientes — isolamento garantido na camada de serviço.
--
-- Idempotente: pode ser executado múltiplas vezes sem erro.

CREATE TABLE IF NOT EXISTS demo_videos (
    id               SERIAL         PRIMARY KEY,
    module           VARCHAR(50)    NOT NULL,          -- 'fueling', 'epi', 'access_control', etc
    camera_id        UUID           REFERENCES cameras(id) ON DELETE CASCADE,
    label            VARCHAR(255),                     -- nome amigável ("Pátio Bay 1")
    r2_key           VARCHAR(500)   NOT NULL,           -- chave no Cloudflare R2
    r2_url           VARCHAR(1000)  NOT NULL,           -- URL pública/presigned
    file_size_bytes  BIGINT,
    duration_seconds NUMERIC(10, 2),
    uploaded_by      UUID           REFERENCES users(id),
    active           BOOLEAN        DEFAULT true,
    created_at       TIMESTAMP      DEFAULT NOW(),
    updated_at       TIMESTAMP      DEFAULT NOW()
);

-- Índice para busca rápida por câmera (filtra somente ativos)
CREATE INDEX IF NOT EXISTS idx_demo_videos_camera
    ON demo_videos (camera_id)
    WHERE active = true;

-- Índice para listagem por módulo (filtra somente ativos)
CREATE INDEX IF NOT EXISTS idx_demo_videos_module
    ON demo_videos (module)
    WHERE active = true;
