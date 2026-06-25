-- 053_edge_heartbeats.sql
--
-- Telemetria time-series enviada pelos dispositivos edge a cada N segundos.
-- Armazena métricas de hardware, inferência, câmeras e conectividade.
-- BIGSERIAL (append-only): sem UPDATE, sem DELETE — particionamento futuro por received_at.
-- Ver ADR-0016.
--
-- Idempotente: CREATE TABLE/INDEX IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS public.edge_heartbeats (
    id                   BIGSERIAL PRIMARY KEY,
    tenant_id            UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    site_id              UUID NOT NULL REFERENCES public.edge_sites(id) ON DELETE CASCADE,
    device_id            TEXT NOT NULL,
    received_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Métricas de hardware
    cpu_pct              NUMERIC(5,2),
    mem_pct              NUMERIC(5,2),
    gpu_pct              NUMERIC(5,2),
    gpu_mem_pct          NUMERIC(5,2),
    disk_pct             NUMERIC(5,2),
    -- Métricas de inferência
    inference_fps        NUMERIC(6,2),
    inference_latency_ms NUMERIC(8,2),
    -- Estado das câmeras no site
    cameras_online       INT,
    cameras_total        INT,
    queue_depth          INT,
    -- Conectividade de rede
    upload_kbps          NUMERIC(10,2),
    download_kbps        NUMERIC(10,2),
    -- Estado geral reportado pelo agente
    status               TEXT CHECK (status IN ('healthy', 'degraded', 'critical', 'offline')),
    last_error           TEXT,
    edge_version         TEXT
);

-- Consulta principal: últimos N heartbeats de um site (dashboard em tempo real).
CREATE INDEX IF NOT EXISTS idx_edge_heartbeats_site_time
    ON public.edge_heartbeats (site_id, received_at DESC);

-- Consulta por tenant (visão consolidada multi-site).
CREATE INDEX IF NOT EXISTS idx_edge_heartbeats_tenant_time
    ON public.edge_heartbeats (tenant_id, received_at DESC);

-- Alertas: filtrar apenas heartbeats degradados/críticos/offline por site.
CREATE INDEX IF NOT EXISTS idx_edge_heartbeats_status
    ON public.edge_heartbeats (site_id, status, received_at DESC)
    WHERE status IN ('degraded', 'critical', 'offline');
