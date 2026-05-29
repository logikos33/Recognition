-- 047_operations_repair.sql
--
-- Repair migration: recreates operations + operation_results that failed
-- to apply in 038/039.
--
-- Migration 038 had two errors:
--   1. camera_id INTEGER -- should be UUID (project standard: confirmed by
--      6 other migrations -- 006, 015, 024, 028, 033, 037 all use UUID)
--   2. FK referenced the legacy table name that 013 had already renamed
--
-- Migration 039 (operation_results) only failed because it depended on
-- operations existing. Same structure preserved here.
--
-- Idempotent: CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS operations (
    id          SERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    camera_id   UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    module_id   VARCHAR(40) NOT NULL DEFAULT 'generic',
    type_id     VARCHAR(60) NOT NULL,
    name        VARCHAR(120) NOT NULL,
    config      JSONB NOT NULL DEFAULT '{}',
    status      VARCHAR(20) NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'warning', 'error', 'inactive')),
    version     INTEGER NOT NULL DEFAULT 1,
    last_value_json   JSONB,
    last_evaluated_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_operations_tenant_camera
    ON operations(tenant_id, camera_id);

CREATE INDEX IF NOT EXISTS idx_operations_status
    ON operations(status, module_id);

CREATE INDEX IF NOT EXISTS idx_operations_type
    ON operations(type_id, module_id);

CREATE TABLE IF NOT EXISTS operation_results (
    id           BIGSERIAL PRIMARY KEY,
    operation_id INTEGER NOT NULL REFERENCES operations(id) ON DELETE CASCADE,
    result_json  JSONB NOT NULL,
    evaluated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_results_operation
    ON operation_results(operation_id, evaluated_at DESC);

CREATE INDEX IF NOT EXISTS idx_results_evaluated_at
    ON operation_results(evaluated_at DESC);
