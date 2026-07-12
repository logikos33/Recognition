-- 052_site_id_attribution.sql
--
-- Atribui site_id às tabelas operacionais de public e aos schemas de tenant.
-- Adiciona deployment_mode em tenants (default 'cloud' para não quebrar tenants existentes).
-- Depende de 050 (public.edge_sites deve existir).
-- Ver ADR-0016.
--
-- Idempotente: ADD COLUMN IF NOT EXISTS, CREATE INDEX IF NOT EXISTS.

-- deployment_mode por tenant: default 'cloud' preserva todos os tenants existentes.
ALTER TABLE public.tenants
    ADD COLUMN IF NOT EXISTS deployment_mode TEXT NOT NULL DEFAULT 'cloud'
    CHECK (deployment_mode IN ('cloud', 'edge', 'hybrid'));

-- site_id nas tabelas operacionais de public (nullable — câmeras/alertas cloud não têm site).
ALTER TABLE public.cameras
    ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id) ON DELETE SET NULL;

ALTER TABLE public.alerts
    ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id) ON DELETE SET NULL;

ALTER TABLE public.counting_events
    ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id) ON DELETE SET NULL;

ALTER TABLE public.operations
    ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_cameras_site
    ON public.cameras (site_id);

CREATE INDEX IF NOT EXISTS idx_alerts_site
    ON public.alerts (site_id);

CREATE INDEX IF NOT EXISTS idx_counting_events_site
    ON public.counting_events (site_id);

CREATE INDEX IF NOT EXISTS idx_operations_site
    ON public.operations (site_id);

-- site_id em quality_inspections e quality_recording_segments de cada schema de tenant.
-- Loop usa schema_name (padrão do projeto — ver 028, 033): schemas reais são 'admin', 'rvb', etc.
-- Não filtra por prefixo de schema — schemas são nomeados pelo slug do tenant diretamente.
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT schema_name
        FROM public.tenants
        WHERE is_active = true
          AND schema_name IS NOT NULL
          AND schema_name <> 'public'
    LOOP
        -- Verificar que o schema existe antes de operar (defensive).
        IF NOT EXISTS (
            SELECT FROM information_schema.schemata
            WHERE schema_name = r.schema_name
        ) THEN
            CONTINUE;
        END IF;

        -- quality_inspections (existe desde 024 em todos os schemas de tenant).
        IF EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = r.schema_name AND table_name = 'quality_inspections'
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I.quality_inspections ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id) ON DELETE SET NULL',
                r.schema_name
            );
        END IF;

        -- quality_recording_segments (existe desde 028 em todos os schemas de tenant).
        IF EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = r.schema_name AND table_name = 'quality_recording_segments'
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I.quality_recording_segments ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES public.edge_sites(id) ON DELETE SET NULL',
                r.schema_name
            );
        END IF;

    END LOOP;
END $$;
