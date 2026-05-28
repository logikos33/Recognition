-- 038_operations.sql
-- Tabela de operações configuráveis por câmera/módulo
-- Segue padrão: CREATE TABLE IF NOT EXISTS, ALTER ADD COLUMN IF NOT EXISTS

CREATE TABLE IF NOT EXISTS operations (
    id          SERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    camera_id   INTEGER NOT NULL REFERENCES ip_cameras(id) ON DELETE CASCADE,
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
