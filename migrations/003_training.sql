CREATE TABLE IF NOT EXISTS training_videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(500) NOT NULL,
    original_filename VARCHAR(500),
    file_size BIGINT,
    duration_seconds FLOAT,
    status VARCHAR(30) NOT NULL DEFAULT 'uploaded'
        CHECK (status IN ('uploaded','extracting','extracted','error')),
    frame_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_videos_user ON training_videos(user_id);
CREATE INDEX IF NOT EXISTS idx_videos_status ON training_videos(status);

CREATE TABLE IF NOT EXISTS training_frames (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES training_videos(id) ON DELETE CASCADE,
    frame_number INTEGER NOT NULL,
    filename VARCHAR(500) NOT NULL,
    timestamp_seconds FLOAT,
    is_annotated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_frames_video ON training_frames(video_id);
CREATE INDEX IF NOT EXISTS idx_frames_annotated ON training_frames(is_annotated);

CREATE TABLE IF NOT EXISTS yolo_classes (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    color VARCHAR(7) DEFAULT '#3b82f6',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS frame_annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    frame_id UUID NOT NULL REFERENCES training_frames(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES yolo_classes(id) ON DELETE CASCADE,
    x_center FLOAT NOT NULL CHECK (x_center BETWEEN 0 AND 1),
    y_center FLOAT NOT NULL CHECK (y_center BETWEEN 0 AND 1),
    width FLOAT NOT NULL CHECK (width > 0 AND width <= 1),
    height FLOAT NOT NULL CHECK (height > 0 AND height <= 1),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_annotations_frame ON frame_annotations(frame_id);

CREATE TABLE IF NOT EXISTS training_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    preset VARCHAR(20) NOT NULL DEFAULT 'balanced'
        CHECK (preset IN ('fast','balanced','quality')),
    model_size VARCHAR(20) NOT NULL DEFAULT 'yolov8n',
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','running','completed','failed','stopped')),
    progress INTEGER NOT NULL DEFAULT 0,
    current_epoch INTEGER DEFAULT 0,
    total_epochs INTEGER DEFAULT 100,
    metrics JSONB DEFAULT '{}',
    error_message TEXT,
    progress_file VARCHAR(500),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jobs_user ON training_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON training_jobs(status);

CREATE TABLE IF NOT EXISTS trained_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id UUID REFERENCES training_jobs(id),
    name VARCHAR(200) NOT NULL,
    model_path VARCHAR(500) NOT NULL,
    map50 FLOAT,
    precision FLOAT,
    recall FLOAT,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_models_user ON trained_models(user_id);
CREATE INDEX IF NOT EXISTS idx_models_active ON trained_models(is_active);
