-- Migration 005: Add quality_status to training_frames
-- Uses DO $$ BEGIN ... EXCEPTION pattern (CLAUDE.md rule)

DO $$ BEGIN
    ALTER TABLE training_frames
        ADD COLUMN quality_status VARCHAR(20) NOT NULL DEFAULT 'pending';
    EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE training_frames
        ADD COLUMN quality_scores JSONB DEFAULT '{}';
    EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE training_frames
        ADD CONSTRAINT chk_quality_status
        CHECK (quality_status IN ('pending', 'approved', 'rejected'));
    EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_frames_quality ON training_frames(quality_status);
