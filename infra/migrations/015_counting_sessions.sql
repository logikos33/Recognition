-- 015_counting_sessions.sql
--
-- SUPERSEDED by 049_counting_deepsort_rebuild.sql (ADR-0018).
--
-- This migration originally tried to CREATE counting_sessions +
-- counting_events with DeepSORT schema. It always failed because a
-- zombie counting_sessions (fueling schema) from legacy
-- 004_rules_engine.sql already existed, turning CREATE TABLE IF NOT
-- EXISTS into a no-op, then CREATE INDEX on the absent tenant_id
-- column rolled back the whole transaction.
--
-- Migration 049 dropped the zombie and rebuilt correctly. This file
-- is now an intentional no-op, kept to preserve migration sequence
-- integrity. Do not delete.

SELECT 1;  -- no-op
