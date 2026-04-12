-- EPI Monitor V2 — Migration 017
-- Add quality_status and quality_scores columns to training_frames
-- These are referenced by FrameRepository.update_quality_status()
-- and FrameRepository.get_approved_by_video()

ALTER TABLE training_frames ADD COLUMN IF NOT EXISTS quality_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE training_frames ADD COLUMN IF NOT EXISTS quality_scores JSONB DEFAULT '{}';

-- Backfill existing frames as approved (safe: they were created before quality filtering existed)
UPDATE training_frames SET quality_status = 'approved' WHERE quality_status IS NULL OR quality_status = 'pending';

-- Index for get_approved_by_video query performance
CREATE INDEX IF NOT EXISTS idx_training_frames_video_quality
    ON training_frames(video_id, quality_status);
