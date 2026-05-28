-- 019_frame_validation.sql
-- Adiciona suporte a validação humana de frames para dataset de treinamento.
-- AI_NOTE: validated_by/validated_at permite distinguir frames apenas anotados
-- (is_annotated=TRUE) de frames revisados e confirmados por humano.

DO $$
BEGIN
    ALTER TABLE training_frames ADD COLUMN validated_by UUID REFERENCES users(id);
EXCEPTION
    WHEN duplicate_column THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE training_frames ADD COLUMN validated_at TIMESTAMP WITH TIME ZONE;
EXCEPTION
    WHEN duplicate_column THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_frames_validated
    ON training_frames(video_id, validated_at)
    WHERE validated_at IS NOT NULL;
