-- 050_edge_sites.sql
--
-- Sites físicos onde o edge roda (Mini PCs com inferência local).
-- Fundação do Edge Deployment Plan — Fase 1.
-- Um tenant pode ter N sites (cloud, edge ou híbrido).
-- Ver ADR-0016.
--
-- Idempotente: CREATE TABLE/INDEX IF NOT EXISTS, CREATE OR REPLACE FUNCTION.

CREATE TABLE IF NOT EXISTS public.edge_sites (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT,
    location        TEXT,
    deployment_mode TEXT NOT NULL
                    CHECK (deployment_mode IN ('cloud', 'edge', 'hybrid')),
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'inactive', 'maintenance', 'provisioning')),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    created_by      UUID
);

CREATE INDEX IF NOT EXISTS idx_edge_sites_tenant
    ON public.edge_sites (tenant_id);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_edge_sites_tenant_name
    ON public.edge_sites (tenant_id, name);

-- Trigger genérico de updated_at — idempotente via CREATE OR REPLACE.
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_edge_sites_updated_at ON public.edge_sites;
CREATE TRIGGER trg_edge_sites_updated_at
    BEFORE UPDATE ON public.edge_sites
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
