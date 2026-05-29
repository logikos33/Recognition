-- 048_counting_sessions_tenant_id.sql
--
-- Repair migration: backfill tenant_id in counting_sessions + counting_events.
--
-- Migration 015 declared tenant_id NOT NULL but the tables existed from an
-- earlier deploy without the column. CREATE TABLE IF NOT EXISTS skipped
-- recreation; the subsequent CREATE INDEX ON counting_sessions(tenant_id)
-- failed because the column was absent.
--
-- This migration:
--   1. Adds tenant_id (nullable) if missing
--   2. Backfills via JOIN cameras (counting_sessions) / counting_sessions (counting_events)
--   3. RAISES EXCEPTION if any row remains NULL after backfill (orphan)
--   4. Promotes column to NOT NULL with FK to tenants(id) ON DELETE CASCADE
--   5. Creates the indexes that 015 failed to create
--
-- All table references are qualified with public. to be search_path-independent.
-- All information_schema lookups filter by table_schema = 'public' to avoid
-- false positives from tenant schemas that may also have these tables.
--
-- Idempotent: ALTER ADD COLUMN IF NOT EXISTS, CREATE INDEX IF NOT EXISTS,
-- ALTER COLUMN SET NOT NULL only when not already NOT NULL.

-- ============================================================
-- counting_sessions: backfill via camera_id → cameras.tenant_id
-- ============================================================

ALTER TABLE public.counting_sessions
    ADD COLUMN IF NOT EXISTS tenant_id UUID;

UPDATE public.counting_sessions cs
SET tenant_id = c.tenant_id
FROM public.cameras c
WHERE cs.camera_id = c.id
  AND cs.tenant_id IS NULL;

DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO orphan_count
    FROM public.counting_sessions
    WHERE tenant_id IS NULL;

    IF orphan_count > 0 THEN
        RAISE EXCEPTION
            'counting_sessions: % rows could not be backfilled (camera_id orphan or NULL cameras.tenant_id). Manual cleanup required before this migration can complete.',
            orphan_count;
    END IF;
END $$;

-- Promote NOT NULL + FK only if not already constrained
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'counting_sessions'
          AND column_name = 'tenant_id'
          AND is_nullable = 'YES'
    ) THEN
        ALTER TABLE public.counting_sessions
            ALTER COLUMN tenant_id SET NOT NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'counting_sessions'
          AND constraint_type = 'FOREIGN KEY'
          AND constraint_name = 'counting_sessions_tenant_id_fkey'
    ) THEN
        ALTER TABLE public.counting_sessions
            ADD CONSTRAINT counting_sessions_tenant_id_fkey
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_counting_sessions_tenant_id
    ON public.counting_sessions (tenant_id);

-- ============================================================
-- counting_events: backfill via session_id → counting_sessions.tenant_id
-- ============================================================

ALTER TABLE public.counting_events
    ADD COLUMN IF NOT EXISTS tenant_id UUID;

UPDATE public.counting_events ce
SET tenant_id = cs.tenant_id
FROM public.counting_sessions cs
WHERE ce.session_id = cs.id
  AND ce.tenant_id IS NULL;

DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO orphan_count
    FROM public.counting_events
    WHERE tenant_id IS NULL;

    IF orphan_count > 0 THEN
        RAISE EXCEPTION
            'counting_events: % rows could not be backfilled (session_id orphan). Manual cleanup required before this migration can complete.',
            orphan_count;
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'counting_events'
          AND column_name = 'tenant_id'
          AND is_nullable = 'YES'
    ) THEN
        ALTER TABLE public.counting_events
            ALTER COLUMN tenant_id SET NOT NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'counting_events'
          AND constraint_type = 'FOREIGN KEY'
          AND constraint_name = 'counting_events_tenant_id_fkey'
    ) THEN
        ALTER TABLE public.counting_events
            ADD CONSTRAINT counting_events_tenant_id_fkey
            FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_counting_events_tenant_id
    ON public.counting_events (tenant_id);
