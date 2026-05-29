-- 048_counting_sessions_tenant_id.sql
--
-- SUPERSEDED by 049_counting_deepsort_rebuild.sql (ADR-0018).
--
-- This migration tried to ALTER counting_sessions ADD tenant_id +
-- backfill. It failed because the table in production was the zombie
-- fueling-schema table (from legacy 004_rules_engine.sql), and
-- counting_events didn't exist (015 always rolled back).
--
-- Migration 049 rebuilt both tables with tenant_id from the start.
-- This file is now an intentional no-op, kept to preserve migration
-- sequence integrity. Do not delete.

SELECT 1;  -- no-op
