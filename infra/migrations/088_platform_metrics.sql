-- 088_platform_metrics.sql
--
-- Série temporal genérica de métricas de plataforma (WS11 — Observability).
-- Alimentada pelo coletor de snapshots (60s) no processo worker e pelo
-- endpoint POST /api/v1/admin/observability/collect.
--
-- tenant_id NULLABLE: NULL = métrica global de plataforma; quando preenchido,
-- referencia public.tenants(id) (C-01 — coluna multi-tenant presente).
--
-- scope  ∈ api | db | redis | r2 | celery | edge | workers | ws
-- metric ex.: queue_depth, queue_oldest_age_s, task_fail_24h, conn_active,
--             conn_idle, conn_max, redis_mem_mb, redis_clients, latency_ms,
--             http_count, http_5xx, http_4xx, http_avg_ms, sites_offline,
--             sites_degraded, workers_online
-- labels ex.: {"queue": "inference_tenant_x"}
--
-- Append-only (BIGSERIAL, sem UPDATE/DELETE via migration) — padrão-casa
-- 068_edge_heartbeats.sql / ADR-0016. Retenção em runtime (coletor, env
-- PLATFORM_METRICS_RETENTION_DAYS, default 30d) — nunca via migration.
--
-- Idempotente: CREATE TABLE/INDEX IF NOT EXISTS — rodável 2x sem erro.

CREATE TABLE IF NOT EXISTS public.platform_metrics (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID REFERENCES public.tenants(id),
    scope       TEXT NOT NULL,
    metric      TEXT NOT NULL,
    value       NUMERIC NOT NULL,
    labels      JSONB NOT NULL DEFAULT '{}',
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Consulta principal do dashboard: série de uma métrica num intervalo.
CREATE INDEX IF NOT EXISTS idx_pm_scope_metric_time
    ON public.platform_metrics (scope, metric, recorded_at DESC);

-- Métricas escopadas por tenant (parcial — maioria é global/NULL).
CREATE INDEX IF NOT EXISTS idx_pm_tenant_time
    ON public.platform_metrics (tenant_id, recorded_at DESC)
    WHERE tenant_id IS NOT NULL;

-- BRIN barato para pruning/range scans em tabela append-only.
CREATE INDEX IF NOT EXISTS idx_pm_recorded_brin
    ON public.platform_metrics USING BRIN (recorded_at);
