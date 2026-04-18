-- ============================================================
-- Migration 032 — Coluna git_sha em system_versions
--
-- Permite idempotência no auto-versioning por deploy Railway:
-- cada commit SHA só gera uma entrada, mesmo com múltiplos
-- workers gunicorn iniciando simultaneamente.
--
-- Idempotente: seguro rodar múltiplas vezes (IF NOT EXISTS)
-- ============================================================

ALTER TABLE public.system_versions
  ADD COLUMN IF NOT EXISTS git_sha VARCHAR(40);

CREATE UNIQUE INDEX IF NOT EXISTS idx_system_versions_git_sha
  ON public.system_versions (git_sha)
  WHERE git_sha IS NOT NULL;
