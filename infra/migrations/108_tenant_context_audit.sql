-- Migration 108: Auditoria de requisições sob contexto de tenant assumido
-- ("assumir contexto" — superadmin visualiza um tenant específico com a
-- própria identidade, distinto do WS6 impersonation_sessions que rastreia
-- "ver como um usuário-alvo").
--
-- Matéria de contrato com a RVB (acesso a dado pessoal sob impersonation) —
-- toda requisição feita com um token de contexto assumido é registrada aqui:
-- quem (impersonator_user_id) · quando (created_at) · qual tenant (tenant_id)
-- · qual endpoint/método (path/method) · resultado (status_code, quando
-- barato de capturar no after_request).
--
-- public.* com coluna tenant_id (ADR-0004/0016) — não é dado do schema do
-- tenant, é meta-dado de auditoria da plataforma.
--
-- Regras (forward-only, append-only):
--   - Apenas CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS
--   - NUNCA DROP / ALTER COLUMN TYPE / DELETE / TRUNCATE
--   - Idempotente: rodar 2x sem erro

CREATE TABLE IF NOT EXISTS public.tenant_context_audit (
    id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             UUID        NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    impersonator_user_id  UUID        NOT NULL REFERENCES public.users(id),
    method                TEXT        NOT NULL,
    path                  TEXT        NOT NULL,
    status_code           INTEGER,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Consulta mais comum: "o que o superadmin X fez no tenant Y, em ordem
-- cronológica" — cobre tenant_id isolado e tenant_id+created_at.
CREATE INDEX IF NOT EXISTS tenant_context_audit_tenant_created_idx
    ON public.tenant_context_audit (tenant_id, created_at);

CREATE INDEX IF NOT EXISTS tenant_context_audit_impersonator_idx
    ON public.tenant_context_audit (impersonator_user_id, created_at);
