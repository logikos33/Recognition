-- 035_add_tenant_id_to_cameras.sql
-- Adiciona coluna tenant_id à tabela cameras com backfill a partir da tabela users.
-- A migration 013 consolidou ip_cameras → cameras mantendo user_id mas sem tenant_id.
-- O CameraRepository espera tenant_id — esta migration resolve o mismatch.

ALTER TABLE cameras
  ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id);

UPDATE cameras c
SET tenant_id = u.tenant_id
FROM users u
WHERE u.id = c.user_id
  AND c.tenant_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_cameras_tenant_id
  ON cameras(tenant_id);
