-- ============================================================
-- Migration 030 — Adicionar feature_flags ao tenant
-- Idempotente: seguro rodar múltiplas vezes
-- ============================================================

ALTER TABLE public.tenants
  ADD COLUMN IF NOT EXISTS feature_flags JSONB DEFAULT '{}';
