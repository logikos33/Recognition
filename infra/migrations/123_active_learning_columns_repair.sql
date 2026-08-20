-- 123_active_learning_columns_repair.sql
--
-- Completa as colunas que a 011 nunca chega a criar num banco NOVO.
--
-- A 011_active_learning.sql aborta no meio: `CREATE INDEX idx_frames_priority`
-- referencia `quality_status`, coluna que só nasce numa migration POSTERIOR.
-- Num banco que já tinha essa coluna (o caminho histórico) a 011 rodava
-- inteira; num banco criado do zero ela morre ali e tudo que vem DEPOIS dessa
-- linha é pulado.
--
-- Medido: banco novo, uma passagem só, fica sem exatamente
--   training_frames.pre_annotations
--   training_frames.pre_annotated_at
--   training_frames.uncertainty_score
--   training_frames.priority_rank
-- e com duas passagens fica completo.
--
-- Consequência num deploy fresco: GET /api/training/images devolve 500 —
-- `pre_annotations` está no CASE de `provenance`. Em produção isso se cura
-- sozinho no boot seguinte (o railway_start.py re-roda todas as migrations e
-- na segunda passada `quality_status` já existe), mas até lá a galeria e a
-- fila de anotação ficam fora do ar. No harness de CI, que roda uma passagem,
-- o banco de integração simplesmente não tem as colunas.
--
-- ⛔ A 011 NÃO é editada — forward-only (CLAUDE.md, Migrations item 4). Esta
-- migration é aditiva e idempotente: onde as colunas já existem (todos os
-- ambientes reais hoje) ela não faz nada.

ALTER TABLE training_frames ADD COLUMN IF NOT EXISTS pre_annotations JSONB;
ALTER TABLE training_frames ADD COLUMN IF NOT EXISTS pre_annotated_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE training_frames ADD COLUMN IF NOT EXISTS uncertainty_score FLOAT;
ALTER TABLE training_frames ADD COLUMN IF NOT EXISTS priority_rank INTEGER;

-- O índice que derrubou a 011, agora que as duas colunas existem. Mesmo nome e
-- mesma definição da 011 — não é índice novo, é o que ela queria criar.
CREATE INDEX IF NOT EXISTS idx_frames_priority
    ON training_frames(tenant_id, module_code, quality_status, priority_rank);
