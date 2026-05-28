-- ============================================================
-- Migration 031 — Sistema de versionamento e changelog
--
-- Permite que o superadmin crie checkpoints de versão com
-- snapshot da configuração atual (módulos, planos, flags).
-- Rollback restaura apenas configurações — nunca schema.
--
-- Idempotente: seguro rodar múltiplas vezes (IF NOT EXISTS)
-- ============================================================

-- ============================================================
-- Versões do sistema (checkpoints manuais criados pelo admin)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.system_versions (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  version         VARCHAR(20) NOT NULL,                     -- ex: "1.2.3"
  version_type    VARCHAR(20) NOT NULL DEFAULT 'patch',     -- 'major' | 'minor' | 'patch'
  title           VARCHAR(200) NOT NULL,
  description     TEXT,
  created_by      UUID        REFERENCES public.users(id),
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  -- Snapshot JSON da configuração no momento da criação
  -- Formato: { "tenants": [{id, slug, plan, modules_enabled, feature_flags}], "plans": [...] }
  config_snapshot JSONB       DEFAULT '{}',
  -- Controle de rollback
  is_current      BOOLEAN     DEFAULT false,
  rolled_back_at  TIMESTAMPTZ,
  rolled_back_by  UUID        REFERENCES public.users(id)
);

CREATE INDEX IF NOT EXISTS idx_system_versions_created_at
  ON public.system_versions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_versions_is_current
  ON public.system_versions (is_current)
  WHERE is_current = true;

-- ============================================================
-- Changelog do sistema (entradas individuais de mudança)
-- Criadas automaticamente por ações admin ou manualmente
-- ============================================================
CREATE TABLE IF NOT EXISTS public.system_changelog (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  -- Versão à qual esta entrada pertence (pode ser NULL para entradas standalone)
  version_id    UUID        REFERENCES public.system_versions(id),
  -- Categoria semântica da mudança
  category      VARCHAR(50) NOT NULL DEFAULT 'config',
  -- 'feature' | 'fix' | 'config' | 'security' | 'breaking' | 'infra'
  importance    VARCHAR(20) NOT NULL DEFAULT 'normal',
  -- 'critical' | 'high' | 'normal' | 'low'
  title         VARCHAR(200) NOT NULL,
  description   TEXT,
  -- Área afetada: 'tenants' | 'users' | 'cameras' | 'training' | 'workers' | 'plans' | 'flags'
  affected_area VARCHAR(100),
  created_by    UUID        REFERENCES public.users(id),
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_changelog_version_id
  ON public.system_changelog (version_id);

CREATE INDEX IF NOT EXISTS idx_system_changelog_created_at
  ON public.system_changelog (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_changelog_importance
  ON public.system_changelog (importance, created_at DESC);
