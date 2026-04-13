-- 018_video_progress.sql
-- Adiciona coluna de total de frames esperados para rastrear progresso de extração.
ALTER TABLE training_videos ADD COLUMN IF NOT EXISTS frames_expected INTEGER DEFAULT 0;
