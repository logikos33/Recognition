-- ============================================================
-- Migration 029 — Admin Panel: audit, workers, plans, approvals
-- Idempotente: seguro rodar múltiplas vezes
-- Nunca DROP — apenas ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS
-- ============================================================

-- ============================================================
-- Estender tenants com campos de gestão comercial e suspensão
-- ============================================================
ALTER TABLE public.tenants
  ADD COLUMN IF NOT EXISTS requires_training_approval BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS mrr_per_camera JSONB DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS internal_notes TEXT,
  ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS suspended_by UUID,
  ADD COLUMN IF NOT EXISTS contract_cameras INT DEFAULT 10,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- ============================================================
-- Estender users com campos de gestão de acesso e auditoria
-- ============================================================
ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS invited_by UUID,
  ADD COLUMN IF NOT EXISTS invited_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS access_expires_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_login_ip INET,
  ADD COLUMN IF NOT EXISTS login_count INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS deactivated_by UUID,
  ADD COLUMN IF NOT EXISTS force_password_reset BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Atualizar constraint de roles para incluir analyst e trainer
DO $$ BEGIN
  ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_role_check;
  ALTER TABLE public.users ADD CONSTRAINT users_role_check
    CHECK (role IN ('superadmin','admin','operator','analyst','trainer','viewer'));
EXCEPTION WHEN others THEN NULL;
END $$;

-- ============================================================
-- Planos disponíveis
-- ============================================================
CREATE TABLE IF NOT EXISTS public.plans (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug         VARCHAR(50) UNIQUE NOT NULL,
  name         VARCHAR(100) NOT NULL,
  modules_allowed JSONB DEFAULT '["epi","basic"]',
  max_cameras  INT DEFAULT 10,
  video_retention_days INT DEFAULT 7,
  requires_training_approval BOOLEAN DEFAULT false,
  price_per_camera JSONB DEFAULT '{}',
  active       BOOLEAN DEFAULT true,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO public.plans (slug, name, modules_allowed, max_cameras, video_retention_days, price_per_camera)
VALUES
  ('basic',      'Básico',      '["basic"]',                              5,   7,  '{"basic": 180}'),
  ('standard',   'Standard',    '["epi","counting","basic"]',             20,  15, '{"epi": 280, "counting": 200, "basic": 180}'),
  ('premium',    'Premium',     '["epi","counting","quality","basic"]',   50,  30, '{"epi": 280, "counting": 200, "quality": 720, "basic": 180}'),
  ('enterprise', 'Enterprise',  '["epi","counting","quality","basic"]',   999, 90, '{"epi": 280, "counting": 200, "quality": 720, "basic": 180}')
ON CONFLICT (slug) DO NOTHING;

-- ============================================================
-- Histórico de mudanças de plano
-- ============================================================
CREATE TABLE IF NOT EXISTS public.tenant_plan_history (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id  UUID REFERENCES public.tenants(id),
  old_plan   VARCHAR(50),
  new_plan   VARCHAR(50),
  changed_by UUID REFERENCES public.users(id),
  notes      TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tph_tenant ON public.tenant_plan_history (tenant_id, created_at DESC);

-- ============================================================
-- Feature flags globais da plataforma
-- ============================================================
CREATE TABLE IF NOT EXISTS public.platform_feature_flags (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  flag_key    VARCHAR(100) UNIQUE NOT NULL,
  flag_value  BOOLEAN DEFAULT false,
  description TEXT,
  updated_by  UUID REFERENCES public.users(id),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Registro persistente de workers on-premise
-- ============================================================
CREATE TABLE IF NOT EXISTS public.worker_registry (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        UUID REFERENCES public.tenants(id),
  tenant_schema    VARCHAR(50) NOT NULL,
  hostname         VARCHAR(255),
  tailscale_ip     INET,
  software_version VARCHAR(50),
  gpu_model        VARCHAR(100),
  gpu_vram_gb      INT,
  registered_at    TIMESTAMPTZ DEFAULT NOW(),
  last_heartbeat_at TIMESTAMPTZ,
  status           VARCHAR(30) DEFAULT 'offline',
  active           BOOLEAN DEFAULT true
);
CREATE INDEX IF NOT EXISTS idx_wr_tenant ON public.worker_registry (tenant_id);
CREATE INDEX IF NOT EXISTS idx_wr_schema ON public.worker_registry (tenant_schema);

-- Métricas de worker — série temporal
CREATE TABLE IF NOT EXISTS public.worker_metrics (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  worker_id      UUID REFERENCES public.worker_registry(id),
  gpu_pct        FLOAT,
  vram_used_gb   FLOAT,
  fps_avg        FLOAT,
  cameras_active INT,
  recorded_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wm_worker_time ON public.worker_metrics (worker_id, recorded_at DESC);

-- ============================================================
-- Aprovações de treinamento
-- ============================================================
CREATE TABLE IF NOT EXISTS public.training_approvals (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id              UUID REFERENCES public.tenants(id),
  tenant_schema          VARCHAR(50) NOT NULL,
  training_job_id        UUID NOT NULL,
  module                 VARCHAR(50) NOT NULL,
  job_name               VARCHAR(255),
  metrics                JSONB DEFAULT '{}',
  dataset_sample_keys    JSONB DEFAULT '[]',
  status                 VARCHAR(30) DEFAULT 'pending',
  reviewed_by            UUID REFERENCES public.users(id),
  reviewed_at            TIMESTAMPTZ,
  reviewer_notes         TEXT,
  rejection_reason       TEXT,
  auto_approved          BOOLEAN DEFAULT false,
  auto_approve_threshold FLOAT,
  created_at             TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ta_status ON public.training_approvals (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ta_tenant ON public.training_approvals (tenant_id);

-- ============================================================
-- Comunicados da plataforma
-- ============================================================
CREATE TABLE IF NOT EXISTS public.platform_announcements (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title            VARCHAR(255) NOT NULL,
  content          TEXT NOT NULL,
  type             VARCHAR(30) DEFAULT 'info',
  target           VARCHAR(30) DEFAULT 'all',
  target_tenant_id UUID REFERENCES public.tenants(id),
  scheduled_at     TIMESTAMPTZ,
  published_at     TIMESTAMPTZ,
  expires_at       TIMESTAMPTZ,
  created_by       UUID REFERENCES public.users(id),
  created_at       TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pa_published ON public.platform_announcements (published_at, expires_at);

CREATE TABLE IF NOT EXISTS public.announcement_reads (
  announcement_id UUID REFERENCES public.platform_announcements(id),
  tenant_id       UUID REFERENCES public.tenants(id),
  read_at         TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (announcement_id, tenant_id)
);

-- ============================================================
-- Audit log — ações administrativas
-- ============================================================
CREATE TABLE IF NOT EXISTS public.audit_log (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id    UUID REFERENCES public.users(id),
  actor_role  VARCHAR(50),
  tenant_id   UUID,
  target_type VARCHAR(50) NOT NULL,
  target_id   TEXT,
  action      VARCHAR(100) NOT NULL,
  old_value   JSONB,
  new_value   JSONB,
  ip_address  INET,
  user_agent  TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_al_actor  ON public.audit_log (actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_al_tenant ON public.audit_log (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_al_action ON public.audit_log (action, created_at DESC);

-- ============================================================
-- Tickets de suporte — schema público (acesso cross-tenant pelo superadmin)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.support_tickets (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         UUID REFERENCES public.tenants(id),
  created_by        UUID REFERENCES public.users(id),
  assigned_to       UUID REFERENCES public.users(id),
  subject           VARCHAR(255) NOT NULL,
  category          VARCHAR(50) DEFAULT 'other',
  priority          VARCHAR(20) DEFAULT 'normal',
  status            VARCHAR(30) DEFAULT 'open',
  first_responded_at TIMESTAMPTZ,
  resolved_at       TIMESTAMPTZ,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_st_tenant  ON public.support_tickets (tenant_id);
CREATE INDEX IF NOT EXISTS idx_st_status  ON public.support_tickets (status, created_at DESC);

CREATE TABLE IF NOT EXISTS public.ticket_messages (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id  UUID REFERENCES public.support_tickets(id),
  author_id  UUID REFERENCES public.users(id),
  content    TEXT NOT NULL,
  is_internal BOOLEAN DEFAULT false,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tm_ticket ON public.ticket_messages (ticket_id, created_at);

-- ============================================================
-- Sessões ativas — para encerramento remoto pelo superadmin
-- ============================================================
CREATE TABLE IF NOT EXISTS public.active_sessions (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID REFERENCES public.users(id),
  tenant_id  UUID REFERENCES public.tenants(id),
  jti        VARCHAR(255) UNIQUE NOT NULL,
  ip_address INET,
  user_agent TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  revoked_by UUID REFERENCES public.users(id)
);
CREATE INDEX IF NOT EXISTS idx_as_user ON public.active_sessions (user_id, expires_at DESC);
CREATE INDEX IF NOT EXISTS idx_as_jti  ON public.active_sessions (jti);
