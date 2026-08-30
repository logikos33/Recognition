-- 129_trained_models_display_name.sql
--
-- Rebranding de modelo (F5-LEVE): o nome interno de `trained_models.name`
-- ("YOLO26 {model_size} - Job {id[:8]}", cravado em
-- infrastructure/queue/tasks/training.py) NUNCA pode chegar à tela do
-- cliente — política do dono (Vitor): cliente NUNCA vê stack interno
-- (motor/arquitetura de detecção). `display_name` é o nome voltado ao
-- cliente: aditivo, NULLable, atribuído manualmente depois (nunca inferido
-- do `name` interno nem da versão — não existe V<n> calculado). Front usa
-- `display_name?.trim() || 'Logikos'` como fallback quando ninguém atribuiu
-- ainda.
--
-- Idempotente: ADD COLUMN IF NOT EXISTS. Sem DROP. No-op onde já existe.

ALTER TABLE public.trained_models ADD COLUMN IF NOT EXISTS display_name TEXT;

COMMENT ON COLUMN public.trained_models.display_name IS
  'Nome voltado ao cliente (rebranding F5-LEVE). NULL = ninguém atribuiu ainda; front cai para "Logikos". Nome interno (name) e framework permanecem visíveis só para superadmin.';
