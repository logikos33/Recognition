-- 027_superadmin_vitor.sql
-- Cria/atualiza usuário superadmin Vitor Emanuel (Logikos).
-- Idempotente — seguro rodar múltiplas vezes.

DO $$
DECLARE
    v_admin_tenant_id UUID;
BEGIN
    -- Garantir que tenant admin existe e tem todos os módulos
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
        modules_enabled = '["epi","counting","quality","basic","analytics","admin"]',
        plan            = 'internal',
        is_active       = true;

    -- Buscar id do tenant admin
    SELECT id INTO v_admin_tenant_id FROM tenants WHERE slug = 'admin';

    IF v_admin_tenant_id IS NULL THEN
        RAISE EXCEPTION 'Tenant admin não encontrado após upsert';
    END IF;

    -- Criar/atualizar usuário superadmin Vitor
    INSERT INTO users (email, password_hash, name, role, tenant_id, is_active)
    VALUES (
        'vitor@logikos.com',
        '$2b$12$euCSteJxz4m7mjFsOtt4zOcKQSQquvmARgXEVwXfIgSIe47ZLXo/i',
        'Vitor Emanuel',
        'superadmin',
        v_admin_tenant_id,
        true
    )
    ON CONFLICT (email) DO UPDATE SET
        password_hash = EXCLUDED.password_hash,
        name          = EXCLUDED.name,
        role          = 'superadmin',
        tenant_id     = EXCLUDED.tenant_id,
        is_active     = true;

    RAISE NOTICE 'Superadmin vitor@logikos.com criado/atualizado com sucesso';
END $$;
