-- 051_device_tokens.sql
--
-- Autenticação de dispositivos edge (Mini PCs) via JWT RS256.
-- enrollment_tokens: token one-time para enrollment inicial do dispositivo.
-- device_tokens:     chave pública RSA + metadados do dispositivo após enrollment.
-- Ver ADR-0019 (Device Tokens RS256 + Escopos).
--
-- Idempotente: CREATE TABLE/INDEX IF NOT EXISTS.

-- Token de enrollment: uso único, pré-gerado pelo operator no painel.
CREATE TABLE IF NOT EXISTS public.enrollment_tokens (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    site_id          UUID NOT NULL REFERENCES public.edge_sites(id) ON DELETE CASCADE,
    token_hash       TEXT NOT NULL UNIQUE,
    expires_at       TIMESTAMPTZ NOT NULL,
    used_at          TIMESTAMPTZ,
    used_by_device_id TEXT,
    created_by       UUID,
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_enrollment_tokens_tenant_site
    ON public.enrollment_tokens (tenant_id, site_id);

-- Índice parcial: lookup eficiente de tokens ainda não usados e não expirados.
CREATE INDEX IF NOT EXISTS idx_enrollment_tokens_pending
    ON public.enrollment_tokens (expires_at)
    WHERE used_at IS NULL;

-- Registro permanente do dispositivo após enrollment bem-sucedido.
-- Chave pública armazenada em PEM; token é verificado por fingerprint (SHA-256).
CREATE TABLE IF NOT EXISTS public.device_tokens (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    site_id           UUID NOT NULL REFERENCES public.edge_sites(id) ON DELETE CASCADE,
    device_id         TEXT NOT NULL,
    device_name       TEXT,
    public_key_pem    TEXT NOT NULL,
    fingerprint       TEXT NOT NULL,
    revoked           BOOLEAN NOT NULL DEFAULT false,
    revoked_at        TIMESTAMPTZ,
    revoked_by        UUID,
    revocation_reason TEXT,
    last_seen_at      TIMESTAMPTZ,
    enrolled_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, device_id)
);

CREATE INDEX IF NOT EXISTS idx_device_tokens_tenant_site
    ON public.device_tokens (tenant_id, site_id);

-- Índice parcial: lookup rápido de dispositivos ativos por device_id.
CREATE INDEX IF NOT EXISTS idx_device_tokens_active
    ON public.device_tokens (tenant_id, device_id)
    WHERE revoked = false;

-- Lookup por fingerprint (verificação de JWT inbound).
CREATE INDEX IF NOT EXISTS idx_device_tokens_fingerprint
    ON public.device_tokens (fingerprint)
    WHERE revoked = false;
