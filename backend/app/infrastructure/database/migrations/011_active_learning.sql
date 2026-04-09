-- 011_active_learning.sql
-- Adiciona suporte a Active Learning em training_frames

-- tenant_id (necessário para filtros por tenant no pre-annotation-service)
DO $$
BEGIN
    ALTER TABLE training_frames ADD COLUMN tenant_id UUID REFERENCES tenants(id);
EXCEPTION
    WHEN duplicate_column THEN NULL;
END $$;

-- Preencher tenant_id existente com tenant default
UPDATE training_frames
SET tenant_id = '00000000-0000-0000-0000-000000000001'
WHERE tenant_id IS NULL;

-- Colunas de pré-anotação
DO $$
BEGIN
    ALTER TABLE training_frames ADD COLUMN pre_annotations JSONB;
EXCEPTION
    WHEN duplicate_column THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE training_frames ADD COLUMN pre_annotated_at TIMESTAMP WITH TIME ZONE;
EXCEPTION
    WHEN duplicate_column THEN NULL;
END $$;

-- Active Learning: score de incerteza e rank de prioridade
DO $$
BEGIN
    ALTER TABLE training_frames ADD COLUMN uncertainty_score FLOAT;
EXCEPTION
    WHEN duplicate_column THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE training_frames ADD COLUMN priority_rank INTEGER;
EXCEPTION
    WHEN duplicate_column THEN NULL;
END $$;

-- Índice para busca ordenada por prioridade de anotação
CREATE INDEX IF NOT EXISTS idx_frames_priority
ON training_frames(tenant_id, module_code, quality_status, priority_rank);
