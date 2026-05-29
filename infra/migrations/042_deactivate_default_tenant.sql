-- Migration 042: Deactivate default tenant + delete test data
-- ADR-0017 (Decisão Complementar — Tenant Default Removal)
--
-- Tenant 00000000-0000-0000-0000-000000000001 (slug=default, schema=public)
-- é artefato de bootstrap sem dono ativo. Dados: 5 câmeras de teste, 13 alertas,
-- 1 usuário admin@epimonitor.com. Decisão B-clean: desativar + deletar.
--
-- IDEMPOTENTE: safe para re-executar.

DO $$
DECLARE
    default_tenant_id UUID := '00000000-0000-0000-0000-000000000001';
BEGIN
    -- Limpar alertas do tenant default
    DELETE FROM public.alerts
    WHERE tenant_id = default_tenant_id;

    -- Limpar câmeras do tenant default
    DELETE FROM public.cameras
    WHERE tenant_id = default_tenant_id;

    -- Desativar usuários do tenant default (soft delete)
    UPDATE public.users
    SET is_active = false
    WHERE tenant_id = default_tenant_id;

    -- Desativar o tenant
    UPDATE public.tenants
    SET is_active = false,
        updated_at = NOW()
    WHERE id = default_tenant_id;

    RAISE NOTICE 'Migration 042: default tenant desativado + dados de teste removidos.';
END $$;
