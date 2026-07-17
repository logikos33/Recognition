-- 105_dashboard_observability.sql
--
-- Observabilidade integrada do dashboard (task-112, ADR-0053): duas séries
-- persistidas que alimentam o Dashboard Integrado do Recognition — sem HTML
-- solto, tudo tenant/site-scoped dentro da plataforma.
--
--   1. public.model_training_metrics — curvas de treino por época por modelo
--      (Training Studio analytics): mAP@0.5:0.95, mAP_small/medium/large,
--      losses, LR etc. em JSONB. Fonte: extrator mm/extract_train_metrics.py
--      (docs/edge/train_metrics/*.jsonl).
--   2. public.edge_telemetry_samples — telemetria do Jetson ao vivo/histórica
--      (GPU/temps/rails/RAM/FPS) por site. Fonte: sampler da campanha
--      (docs/edge/evidence/mm-2026-07-17/telemetry_mm.jsonl) via ingest.
--
-- Padrão-casa 088_platform_metrics.sql / ADR-0016: tabelas PÚBLICAS com
-- coluna tenant_id (C-01, multi-tenant explícito) — NÃO schema-per-tenant.
-- Isso evita redefinir create_tenant_schema (append-only, feedback de memória)
-- e mantém a série de observabilidade num lugar só, como platform_metrics.
--
-- tenant_id NOT NULL REFERENCES public.tenants(id): telemetria e métricas de
-- treino são SEMPRE de um tenant (RVB no cenário) — sem métrica global aqui,
-- ao contrário de platform_metrics. Cross-tenant é filtrado por tenant_id na
-- query (repository), nunca exposto (C-01 → lista vazia / 404).
--
-- Idempotente: CREATE TABLE/INDEX IF NOT EXISTS — rodável 2x sem erro.
-- Forward-only: nenhum DROP/ALTER TYPE/DELETE.

-- ---------------------------------------------------------------------------
-- 1. Métricas de treino por época por modelo (Training Studio analytics)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.model_training_metrics (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES public.tenants(id),
    model_name  TEXT NOT NULL,
    framework   TEXT,
    epoch       INT  NOT NULL,
    metrics     JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Upsert por (tenant, modelo, época): re-ingerir a mesma época atualiza,
    -- nunca duplica a curva.
    UNIQUE (tenant_id, model_name, epoch)
);

-- Consulta principal do dashboard: curva de um modelo (todas as épocas) e
-- lista de modelos do tenant.
CREATE INDEX IF NOT EXISTS idx_mtm_tenant_model
    ON public.model_training_metrics (tenant_id, model_name);

-- ---------------------------------------------------------------------------
-- 2. Amostras de telemetria do edge (Jetson) por site
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.edge_telemetry_samples (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES public.tenants(id),
    site_id     UUID,
    label       TEXT,
    sampled_at  TIMESTAMPTZ NOT NULL,
    payload     JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Consulta principal: série temporal recente de um site (janela + ordenação).
CREATE INDEX IF NOT EXISTS idx_ets_tenant_site_time
    ON public.edge_telemetry_samples (tenant_id, site_id, sampled_at DESC);

-- BRIN barato para pruning/range scans em tabela de série temporal.
CREATE INDEX IF NOT EXISTS idx_ets_sampled_brin
    ON public.edge_telemetry_samples USING BRIN (sampled_at);
