-- ============================================================
-- Migration 052 — Configuração de cenário por modelo treinado
--   Adiciona coluna scenario_config (JSONB) à tabela trained_models.
--   Armazena: classes, counting_line, roi, confidence_threshold, camera_id.
-- Idempotente: seguro rodar múltiplas vezes.
-- Nunca DROP — apenas ADD COLUMN IF NOT EXISTS.
-- ============================================================

ALTER TABLE public.trained_models
  ADD COLUMN IF NOT EXISTS scenario_config JSONB;

COMMENT ON COLUMN public.trained_models.scenario_config IS
  'Configuração de cenário do modelo: {classes, counting_line, roi, confidence_threshold, camera_id}';

CREATE INDEX IF NOT EXISTS idx_trained_models_scenario
  ON public.trained_models USING GIN (scenario_config);
