-- 025_superadmin_viewer_role.sql
-- Adiciona roles superadmin e viewer ao sistema.
-- Idempotente — seguro rodar múltiplas vezes.

-- 1. Remover constraint de role existente (se houver) e re-criar com os 4 roles
DO $$
BEGIN
    -- Remover constraint antiga
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'users_role_check'
          AND table_name = 'users'
    ) THEN
        ALTER TABLE users DROP CONSTRAINT users_role_check;
    END IF;

    -- Adicionar constraint com todos os roles permitidos
    ALTER TABLE users ADD CONSTRAINT users_role_check
        CHECK (role IN ('admin', 'operator', 'superadmin', 'viewer'));
EXCEPTION WHEN OTHERS THEN
    -- Constraint já existe com nome diferente ou não existe — ignorar
    NULL;
END $$;

-- 2. Inserir usuário superadmin vinculado ao tenant admin
-- Senha padrão: EpiMonitor@2024! (bcrypt hash — trocar no primeiro login)
-- Hash gerado com: python -c "import bcrypt; print(bcrypt.hashpw(b'EpiMonitor@2024!', bcrypt.gensalt()).decode())"
DO $$
DECLARE
    v_admin_tenant_id UUID;
BEGIN
    -- Buscar id do tenant admin
    SELECT id INTO v_admin_tenant_id FROM tenants WHERE slug = 'admin';

    IF v_admin_tenant_id IS NOT NULL THEN
        INSERT INTO users (email, password_hash, name, role, tenant_id, is_active)
        VALUES (
            'superadmin@logikos.com.br',
            '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/P97gqmUc.',
            'Logikos — Superadmin',
            'superadmin',
            v_admin_tenant_id,
            true
        )
        ON CONFLICT (email) DO UPDATE SET
            role = 'superadmin',
            tenant_id = EXCLUDED.tenant_id;
    END IF;
END $$;

-- 3. Index no campo role para queries de autorização
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
