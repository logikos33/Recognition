-- 057_site_gateways.sql
--
-- Gateway de rede do site (MikroTik WireGuard) — O2 / task-031. Ver ADR-0020.
-- Depende de 050 (public.edge_sites).
-- SEGREDO: guardamos só a chave PÚBLICA WireGuard + endpoint; a chave privada
-- nunca é persistida aqui (fica no device / secret store).
--
-- Idempotente: CREATE TABLE/INDEX IF NOT EXISTS. Sem DROP.

CREATE TABLE IF NOT EXISTS public.site_gateways (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    site_id       UUID NOT NULL REFERENCES public.edge_sites(id) ON DELETE CASCADE,
    kind          TEXT NOT NULL DEFAULT 'mikrotik',
    model         TEXT,
    wg_public_key TEXT,
    wg_endpoint   TEXT,
    lan_subnet    TEXT,
    status        TEXT NOT NULL DEFAULT 'provisioning'
                  CHECK (status IN ('provisioning','active','inactive','error')),
    last_seen     TIMESTAMPTZ,
    config        JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_site_gateways_tenant ON public.site_gateways (tenant_id);

-- 1 gateway por site (por enquanto).
CREATE UNIQUE INDEX IF NOT EXISTS uniq_site_gateways_site ON public.site_gateways (site_id);
