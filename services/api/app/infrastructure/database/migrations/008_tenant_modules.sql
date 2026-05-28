-- 008_tenant_modules.sql
-- Tabela de módulos por tenant

CREATE TABLE IF NOT EXISTS tenant_modules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    module_code VARCHAR(50) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    config JSONB DEFAULT '{}',
    activated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,

    UNIQUE(tenant_id, module_code)
);

CREATE INDEX IF NOT EXISTS idx_tenant_modules_tenant ON tenant_modules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_modules_code ON tenant_modules(module_code);

-- Ativar módulo EPI para todos os tenants existentes
INSERT INTO tenant_modules (tenant_id, module_code, enabled)
SELECT id, 'epi', true FROM tenants
ON CONFLICT (tenant_id, module_code) DO NOTHING;
