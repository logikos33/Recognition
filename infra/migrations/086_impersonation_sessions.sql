-- Migration 086: Sessões de impersonation ("ver como") — WS6
-- Superadmin pode visualizar a plataforma como um usuário de qualquer tenant.
-- Esta tabela rastreia entrada/saída de cada visualização (além do audit_log)
-- para correlação e investigação forense.
--
-- Regras:
--   - Apenas CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS (append-only)
--   - tenant_id = tenant do usuário ALVO (multi-tenant, C-01)
--   - NUNCA armazena credencial/senha/token do alvo — apenas o jti do token
--     emitido, para correlação com revogação/expiração
--   - Idempotente: rodar 2x sem erro

CREATE TABLE IF NOT EXISTS public.impersonation_sessions (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      UUID        NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    superadmin_id  UUID        NOT NULL REFERENCES public.users(id),
    target_user_id UUID        NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    jti            TEXT,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at       TIMESTAMPTZ,
    ip_address     TEXT,
    user_agent     TEXT
);

CREATE INDEX IF NOT EXISTS impersonation_sessions_superadmin_idx
    ON public.impersonation_sessions (superadmin_id);

CREATE INDEX IF NOT EXISTS impersonation_sessions_target_idx
    ON public.impersonation_sessions (target_user_id);

CREATE INDEX IF NOT EXISTS impersonation_sessions_jti_idx
    ON public.impersonation_sessions (jti);
