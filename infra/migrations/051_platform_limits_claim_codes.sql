-- ============================================================
-- Migration 051 — Plataforma: limites por tenant + claim codes
--   1. Rate limiting por tenant (override) e por plano (default)
--   2. Seats (assentos) por tenant — max_seats (NULL = ilimitado)
--   3. Política de sessão única por tenant (single_session)
--   4. Claim codes de dispositivos (plug-and-play / enrollment)
-- Idempotente: seguro rodar múltiplas vezes.
-- Nunca DROP — apenas ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS.
-- ============================================================

-- ============================================================
-- Tenants: limites e políticas de plataforma
-- ============================================================
ALTER TABLE public.tenants
  ADD COLUMN IF NOT EXISTS max_seats INT,
  ADD COLUMN IF NOT EXISTS single_session BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS rate_limit_per_minute INT;

COMMENT ON COLUMN public.tenants.max_seats IS
  'Máximo de usuários ativos do tenant. NULL = ilimitado.';
COMMENT ON COLUMN public.tenants.single_session IS
  'Quando true, login novo revoga sessões anteriores do usuário (última sessão ganha).';
COMMENT ON COLUMN public.tenants.rate_limit_per_minute IS
  'Override de rate limit da API por tenant. NULL = herda do plano (plans.api_rate_per_minute).';

-- ============================================================
-- Plans: rate limit default por tier
-- ============================================================
ALTER TABLE public.plans
  ADD COLUMN IF NOT EXISTS api_rate_per_minute INT DEFAULT 120;

COMMENT ON COLUMN public.plans.api_rate_per_minute IS
  'Rate limit default da API (requests/minuto por usuário) para tenants do plano.';

-- ============================================================
-- Claim codes — embrião do plug-and-play de dispositivos.
-- Código curto (8 chars) gerado por um admin do tenant; o instalador
-- digita o código no dispositivo, que troca por um enrollment token.
-- Armazenado APENAS o hash SHA-256 do código (nunca plaintext).
-- ============================================================
CREATE TABLE IF NOT EXISTS public.device_claim_codes (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      UUID NOT NULL REFERENCES tenants(id),
  code_hash      VARCHAR(64) UNIQUE NOT NULL,
  created_by     UUID REFERENCES users(id),
  expires_at     TIMESTAMPTZ NOT NULL,
  used_at        TIMESTAMPTZ,
  used_by_device VARCHAR(255),
  created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dcc_tenant  ON public.device_claim_codes (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dcc_hash    ON public.device_claim_codes (code_hash);
CREATE INDEX IF NOT EXISTS idx_dcc_expires ON public.device_claim_codes (expires_at);
