-- 055_edge_events.sql
--
-- Ingest de eventos de detecção vindos do edge (Fase 2 / task-029).
-- Idempotência de batch via dedup_key (X-Batch-Id + hash do evento).
-- Depende de 050 (public.edge_sites). device_id é TEXT (igual edge_heartbeats).
-- camera_id é UUID solto (câmeras vivem em {schema}.cameras — sem FK cross-schema).
--
-- Idempotente: CREATE TABLE/INDEX IF NOT EXISTS. Sem DROP.

CREATE TABLE IF NOT EXISTS public.edge_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    site_id         UUID NOT NULL REFERENCES public.edge_sites(id) ON DELETE CASCADE,
    device_id       TEXT,
    camera_id       UUID,
    module          TEXT,
    event_type      TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}',
    evidence_r2_key TEXT,
    occurred_at     TIMESTAMPTZ,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    batch_id        TEXT,
    dedup_key       TEXT
);

CREATE INDEX IF NOT EXISTS idx_edge_events_tenant_site ON public.edge_events (tenant_id, site_id);
CREATE INDEX IF NOT EXISTS idx_edge_events_received_at ON public.edge_events (received_at);

-- Idempotência de ingest: o mesmo evento (dedup_key) não duplica por tenant.
CREATE UNIQUE INDEX IF NOT EXISTS uniq_edge_events_dedup
    ON public.edge_events (tenant_id, dedup_key) WHERE dedup_key IS NOT NULL;
