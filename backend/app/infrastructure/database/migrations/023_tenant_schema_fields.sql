-- 023_tenant_schema_fields.sql
-- Adiciona campos de schema, plano e módulos habilitados à tabela tenants.
-- Idempotente — seguro rodar múltiplas vezes.

-- 1. Campos novos em tenants
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS schema_name VARCHAR(50);
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS plan VARCHAR(50) DEFAULT 'standard';
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS modules_enabled JSONB DEFAULT '["epi","counting","basic"]';

-- 2. Unique constraint em schema_name (idempotente)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'tenants_schema_name_key'
          AND table_name = 'tenants'
    ) THEN
        ALTER TABLE tenants ADD CONSTRAINT tenants_schema_name_key UNIQUE (schema_name);
    END IF;
END $$;

-- 3. Default tenant (id fixo) — aponta para schema public
UPDATE tenants
SET schema_name = 'public',
    plan = 'standard',
    modules_enabled = '["epi","counting","basic"]'
WHERE id = '00000000-0000-0000-0000-000000000001'
  AND schema_name IS NULL;

-- 4. Tenant admin (Logikos — acesso superadmin)
INSERT INTO tenants (slug, name, schema_name, plan, modules_enabled, is_active)
VALUES (
    'admin',
    'Logikos — Administração',
    'admin',
    'internal',
    '["epi","counting","quality","basic","analytics","admin"]',
    true
)
ON CONFLICT (slug) DO UPDATE SET
    schema_name     = EXCLUDED.schema_name,
    plan            = EXCLUDED.plan,
    modules_enabled = EXCLUDED.modules_enabled;

-- 5. Tenant RVB (primeiro cliente)
INSERT INTO tenants (slug, name, schema_name, plan, modules_enabled, is_active)
VALUES (
    'rvb',
    'RVB Isolantes para Transformadores',
    'rvb',
    'standard',
    '["epi","counting","quality","basic"]',
    true
)
ON CONFLICT (slug) DO UPDATE SET
    schema_name     = EXCLUDED.schema_name,
    modules_enabled = EXCLUDED.modules_enabled;

-- 6. Index em schema_name para lookup rápido no middleware
CREATE INDEX IF NOT EXISTS idx_tenants_schema_name ON tenants(schema_name);
