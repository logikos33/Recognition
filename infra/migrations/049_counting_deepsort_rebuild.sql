-- 049_counting_deepsort_rebuild.sql
--
-- A counting_sessions legada (migrations/004_rules_engine.sql, diretório
-- antigo antes de infra/migrations/) era protótipo de fueling-validation,
-- zumbi (0 rows, 0 refs no código atual). Bloqueava 015 (CREATE TABLE IF
-- NOT EXISTS virou no-op porque tabela existia com schema fueling, depois
-- CREATE INDEX em tenant_id ausente fez rollback total) e 048 (ALTER em
-- tabela com schema errado + ref a counting_events que nunca existiu).
--
-- session_events (mesmo arquivo legado) também zumbi (0 rows, 0 refs).
--
-- O código atual (counting_repository, counting_bp, frontend CountingPage)
-- espera schema DeepSORT: tenant_id, module_code, track_id, class_name,
-- UNIQUE(session_id, track_id) para anti-duplicata.
--
-- Esta migration: DROP das duas zumbis + criação correta do schema DeepSORT.
-- Ver ADR-0018. Exceção consciente à regra no-DROP (0 dados, 0 refs).
--
-- Idempotente: DROP IF EXISTS, CREATE IF NOT EXISTS.

-- 1. Drop tabelas zumbi (confirmadas 0 rows, 0 referências externas)
DROP TABLE IF EXISTS public.session_events CASCADE;
DROP TABLE IF EXISTS public.counting_sessions CASCADE;

-- 2. counting_sessions (DeepSORT — schema que o counting_repository espera)
CREATE TABLE IF NOT EXISTS public.counting_sessions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    camera_id     UUID NOT NULL REFERENCES public.cameras(id) ON DELETE CASCADE,
    module_code   VARCHAR(40) NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'running'
                  CHECK (status IN ('running', 'stopped')),
    total_counts  JSONB NOT NULL DEFAULT '{}',
    started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_counting_sessions_tenant
    ON public.counting_sessions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_counting_sessions_camera
    ON public.counting_sessions (camera_id);
CREATE INDEX IF NOT EXISTS idx_counting_sessions_status
    ON public.counting_sessions (status);

-- 3. counting_events (DeepSORT — anti-duplicata via UNIQUE(session_id, track_id))
CREATE TABLE IF NOT EXISTS public.counting_events (
    id             BIGSERIAL PRIMARY KEY,
    session_id     UUID NOT NULL REFERENCES public.counting_sessions(id) ON DELETE CASCADE,
    tenant_id      UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    track_id       INTEGER NOT NULL,
    class_name     VARCHAR(80) NOT NULL,
    confidence     NUMERIC(5,4),
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (session_id, track_id)
);

CREATE INDEX IF NOT EXISTS idx_counting_events_session
    ON public.counting_events (session_id);
CREATE INDEX IF NOT EXISTS idx_counting_events_tenant
    ON public.counting_events (tenant_id);
