-- EPI Monitor V2 — Migration 021
-- Reset frames with empty pre_annotations to allow re-processing with fixed DINO pipeline.
-- Also backfill quality_status for frames stuck in NULL/pending (fix get_approved_by_video).

UPDATE training_frames
SET pre_annotated_at = NULL
WHERE pre_annotated_at IS NOT NULL
AND (pre_annotations IS NULL OR pre_annotations = '[]'::jsonb);

UPDATE training_frames
SET quality_status = 'approved'
WHERE quality_status IS NULL OR quality_status = 'pending';
