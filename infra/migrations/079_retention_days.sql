-- 064_retention_days.sql
--
-- Tiers de retenção configuráveis por câmera/tenant — task-047.
--
-- Adiciona:
--   public.cameras.retention_days       INT DEFAULT NULL
--       NULL = herdar do tenant; valor explícito sobreescreve o default.
--   public.tenants.default_retention_days  INT DEFAULT NULL
--       NULL = herdar do plano (plans.video_retention_days); valor explícito
--       por tenant sobreescreve o plano sem precisar mudar o plano.
--   %I.cameras.retention_days per tenant (para workers/Celery).
--
-- Idempotente: ADD COLUMN IF NOT EXISTS. Sem DROP.

-- 1. Câmeras públicas (usadas pelo camera_repository da API)
ALTER TABLE public.cameras ADD COLUMN IF NOT EXISTS retention_days INT;

-- 2. Override de retenção por tenant (sem precisar alterar o plano)
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS default_retention_days INT;

-- 3. Índice auxiliar para o job de expiração (câmeras com override explícito)
CREATE INDEX IF NOT EXISTS idx_cameras_retention_days
    ON public.cameras (tenant_id, retention_days)
    WHERE retention_days IS NOT NULL;

-- 4. Backfill nos schemas per-tenant (usados pelos workers/Celery)
DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN
        SELECT schema_name
        FROM public.tenants
        WHERE schema_name IS NOT NULL
          AND schema_name <> ''
          AND schema_name <> 'public'
    LOOP
        IF NOT EXISTS (
            SELECT FROM information_schema.schemata
            WHERE schema_name = r.schema_name
        ) THEN
            CONTINUE;
        END IF;
        IF EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = r.schema_name AND table_name = 'cameras'
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I.cameras ADD COLUMN IF NOT EXISTS retention_days INT',
                r.schema_name
            );
        END IF;
    END LOOP;
END $$;
