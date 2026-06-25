-- 056_edge_commands.sql
--
-- Fila de comandos remotos pro edge (O3 / nível N2 / task-030).
-- O edge consome por polling; idempotência por command_id (X-Command-Id).
-- Depende de 050 (public.edge_sites).
--
-- Idempotente: CREATE TABLE/INDEX IF NOT EXISTS. Sem DROP.

CREATE TABLE IF NOT EXISTS public.edge_commands (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    site_id       UUID NOT NULL REFERENCES public.edge_sites(id) ON DELETE CASCADE,
    command_type  TEXT NOT NULL,
    payload       JSONB NOT NULL DEFAULT '{}',
    status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','dispatched','done','failed','expired')),
    command_id    TEXT NOT NULL,          -- idempotência (X-Command-Id)
    result        JSONB,
    created_by    UUID,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    dispatched_at TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_edge_commands_site_status ON public.edge_commands (site_id, status);

-- Reenvio do mesmo comando não duplica efeito (idempotente por tenant).
CREATE UNIQUE INDEX IF NOT EXISTS uniq_edge_commands_cmdid
    ON public.edge_commands (tenant_id, command_id);
