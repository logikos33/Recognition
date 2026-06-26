-- ============================================================
-- Migration 052 — Inventário de câmeras: campos de onboarding e probe
--
-- Adiciona campos de inventário/edge à tabela public.cameras:
--   site_id, brand, model, ip, rtsp_substream_url, codec_detected,
--   substream_ok, max_connections, last_probe_at, probe_status, notes
--
-- Idempotente: seguro rodar múltiplas vezes.
-- Nunca DROP — apenas ADD COLUMN IF NOT EXISTS.
-- ============================================================

DO $$ BEGIN
    IF EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'cameras'
    ) THEN
        -- Identificador de site/localidade (agrupamento físico de câmeras)
        ALTER TABLE public.cameras
            ADD COLUMN IF NOT EXISTS site_id UUID;

        -- Marca/fabricante amigável (ex: "Intelbras", "Hikvision")
        ALTER TABLE public.cameras
            ADD COLUMN IF NOT EXISTS brand TEXT;

        -- Modelo do equipamento (ex: "VIP 3220 SD", "DS-2CD2143G2-I")
        ALTER TABLE public.cameras
            ADD COLUMN IF NOT EXISTS model TEXT;

        -- IP de acesso (endereço IP externo/público, pode diferir de host)
        ALTER TABLE public.cameras
            ADD COLUMN IF NOT EXISTS ip TEXT;

        -- URL RTSP do substream (canal de baixa resolução para inferência)
        ALTER TABLE public.cameras
            ADD COLUMN IF NOT EXISTS rtsp_substream_url TEXT;

        -- Codec detectado via probe (ex: "H.264", "H.265")
        ALTER TABLE public.cameras
            ADD COLUMN IF NOT EXISTS codec_detected TEXT;

        -- Substream acessível e funcional
        ALTER TABLE public.cameras
            ADD COLUMN IF NOT EXISTS substream_ok BOOLEAN;

        -- Número máximo de conexões simultâneas suportado pela câmera
        ALTER TABLE public.cameras
            ADD COLUMN IF NOT EXISTS max_connections INTEGER DEFAULT 4;

        -- Data/hora do último probe
        ALTER TABLE public.cameras
            ADD COLUMN IF NOT EXISTS last_probe_at TIMESTAMPTZ;

        -- Status do último probe: pending | ok | error | timeout
        ALTER TABLE public.cameras
            ADD COLUMN IF NOT EXISTS probe_status TEXT DEFAULT 'pending';

        -- Notas livres do admin (ex: localização física, observações)
        ALTER TABLE public.cameras
            ADD COLUMN IF NOT EXISTS notes TEXT;

        RAISE NOTICE 'migration 052: colunas de inventário adicionadas a public.cameras';
    ELSE
        RAISE NOTICE 'migration 052: tabela public.cameras não encontrada — skip';
    END IF;
END $$;

-- Índices para filtragem no inventário
CREATE INDEX IF NOT EXISTS idx_cameras_probe_status
    ON public.cameras (probe_status)
    WHERE probe_status IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cameras_site_id
    ON public.cameras (site_id)
    WHERE site_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cameras_brand
    ON public.cameras (brand)
    WHERE brand IS NOT NULL;
