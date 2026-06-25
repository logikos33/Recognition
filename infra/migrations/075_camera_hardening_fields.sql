-- 060_camera_hardening_fields.sql
--
-- Campos de hardening por câmera — task-041 (contenção R1/R2/R4):
--   detection_stream_url (substream de detecção), video_codec (preferir h265),
--   max_auth_failures (anti-lockout).
-- As câmeras vivem em {tenant_schema}.cameras (ver create_tenant_schema / 054).
-- Esta migration faz BACKFILL nos schemas dos tenants existentes (mesmo padrão de loop
-- usado em 052/054). Idempotente: ADD COLUMN IF NOT EXISTS. Sem DROP.
--
-- NOTA (append-only): a PRÓXIMA redefinição de public.create_tenant_schema() deve incluir
-- estas 3 colunas no CREATE TABLE de %I.cameras, para que NOVOS tenants já nasçam com elas.
-- O backfill abaixo cobre todos os tenants ATUAIS (ex.: RVB).

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
            SELECT FROM information_schema.schemata WHERE schema_name = r.schema_name
        ) THEN
            CONTINUE;
        END IF;
        EXECUTE format('ALTER TABLE %I.cameras ADD COLUMN IF NOT EXISTS detection_stream_url TEXT', r.schema_name);
        EXECUTE format('ALTER TABLE %I.cameras ADD COLUMN IF NOT EXISTS video_codec TEXT', r.schema_name);
        EXECUTE format('ALTER TABLE %I.cameras ADD COLUMN IF NOT EXISTS max_auth_failures INTEGER DEFAULT 5', r.schema_name);
    END LOOP;
END $$;
