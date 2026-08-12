-- 117_edge_monitoring_thresholds.sql
--
-- Limiares editáveis da página /monitoring (observabilidade da frota edge,
-- superadmin-only). Uma linha por site: JSONB livre com os limiares que o
-- painel usa para colorir/alarmar telemetria (ex.: cpu_pct_max, gpu_temp_c_max,
-- ingest_lag_s_max). O conteúdo é validado na API (chaves string, valores
-- numéricos/booleanos, máx 64 chaves) — o banco só persiste.
--
-- ADR-0020: o box só disca para fora (outbound) — a nuvem nunca alcança o
-- device diretamente. Os limiares vivem aqui no cloud e são aplicados sobre
-- a telemetria que o box empurra (heartbeats/eventos) ou responde via fila
-- de comandos (public.edge_commands, command_type 'monitoring.*').
--
-- public.* com tenant_id (ADR-0016): dado de plataforma por site, consultado
-- pela visão de frota cross-tenant do superadmin — não vive em {tenant_schema}.
--
-- Forward-only e idempotente: apenas CREATE TABLE/INDEX IF NOT EXISTS.
-- Sem DROP. Seguro rodar múltiplas vezes.

-- tenant_id com ON DELETE CASCADE: mesmo comportamento de TODAS as tabelas
-- irmãs (edge_sites, edge_commands, edge_events, device_tokens) — sem isso,
-- esta tabela bloquearia o DELETE de um tenant (provado no harness local:
-- FK NO ACTION dispara antes do cascade via site_id).
CREATE TABLE IF NOT EXISTS public.edge_monitoring_thresholds (
    site_id    UUID PRIMARY KEY REFERENCES public.edge_sites(id) ON DELETE CASCADE,
    tenant_id  UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    thresholds JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_by UUID,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_edge_monitoring_thresholds_tenant
    ON public.edge_monitoring_thresholds (tenant_id);

COMMENT ON TABLE public.edge_monitoring_thresholds IS
    'Limiares por site da página /monitoring (superadmin). JSONB validado na '
    'API: chaves string, valores numéricos ou booleanos, máx 64 chaves. '
    'Upsert via ON CONFLICT (site_id).';
