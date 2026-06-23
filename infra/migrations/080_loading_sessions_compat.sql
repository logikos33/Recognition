-- 080_loading_sessions_compat.sql
--
-- Representação completa do schema de carga/descarga e plataforma no develop.
--
-- Contexto (ADR-0021): a linhagem de staging aplicou esses campos como "050"
-- (loading_sessions_fields) e "051" (platform_limits_claim_codes). No develop
-- esses slots foram ocupados por 065_edge_sites e 066_device_tokens.
-- Em produção as colunas JÁ EXISTEM — ADD COLUMN IF NOT EXISTS é no-op.
-- Em ambiente novo (tenant novo, staging reconstruído do zero) essas colunas
-- seriam criadas aqui, garantindo que o repo seja fonte de verdade completa.
--
-- Idempotente: ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS. Sem DROP.
-- Forward-only.

-- ============================================================
-- counting_sessions: campos de carga/descarga (Carga & Descarga Fase 1)
-- ============================================================
ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS bay_id UUID;

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS truck_plate TEXT;

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS direction TEXT
        CHECK (direction IN ('load', 'unload'));

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS expected_count INTEGER;

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS divergence INTEGER;

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS video_clip_url TEXT;

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS manual_count INTEGER;

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS acceptance_status TEXT
        CHECK (acceptance_status IN ('pending', 'accepted', 'rejected'));

CREATE INDEX IF NOT EXISTS idx_counting_sessions_tenant_bay
    ON public.counting_sessions (tenant_id, bay_id);

-- ============================================================
-- tenants + plans: limites de plataforma e rate limiting
-- ============================================================
ALTER TABLE public.tenants
    ADD COLUMN IF NOT EXISTS max_seats INT,
    ADD COLUMN IF NOT EXISTS single_session BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS rate_limit_per_minute INT;

ALTER TABLE public.plans
    ADD COLUMN IF NOT EXISTS api_rate_per_minute INT DEFAULT 120;

-- ============================================================
-- device_claim_codes: claim codes de dispositivos (plug-and-play)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.device_claim_codes (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      UUID NOT NULL REFERENCES public.tenants(id),
    code_hash      VARCHAR(64) UNIQUE NOT NULL,
    created_by     UUID REFERENCES public.users(id),
    expires_at     TIMESTAMPTZ NOT NULL,
    used_at        TIMESTAMPTZ,
    used_by_device VARCHAR(255),
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dcc_tenant
    ON public.device_claim_codes (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_dcc_hash
    ON public.device_claim_codes (code_hash);

CREATE INDEX IF NOT EXISTS idx_dcc_expires
    ON public.device_claim_codes (expires_at);
