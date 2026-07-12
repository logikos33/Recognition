-- Migration 085: Overrides granulares de permissão por usuário (WS7)
-- "Usuário customizado": grant/deny de permissões individuais além da role base
-- e da custom_role. Tabela (e não JSONB em users) para auditar quem concedeu
-- e por quê (granted_by / reason).
--
-- Regras:
--   - Apenas CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS (append-only)
--   - Toda tabela com tenant_id (multi-tenant, C-01)
--   - Idempotente: rodar 2x sem erro
--   - permission_key usa vocabulário canônico 'dominio:acao' (app/core/permissions.py)

CREATE TABLE IF NOT EXISTS public.user_permission_overrides (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      UUID        NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    user_id        UUID        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    permission_key TEXT        NOT NULL,
    allow          BOOLEAN     NOT NULL DEFAULT true,
    granted_by     UUID        REFERENCES public.users(id),
    reason         TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Um override por (usuário, permissão) — upserts via ON CONFLICT
CREATE UNIQUE INDEX IF NOT EXISTS user_perm_override_user_key
    ON public.user_permission_overrides (user_id, permission_key);

CREATE INDEX IF NOT EXISTS user_perm_override_tenant_idx
    ON public.user_permission_overrides (tenant_id);
