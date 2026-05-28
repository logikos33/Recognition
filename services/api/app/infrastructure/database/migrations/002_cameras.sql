-- 002_cameras.sql
-- Câmeras IP + eventos de câmera
-- Preservado do schema existente (migrations/002_cameras.sql)

CREATE TABLE IF NOT EXISTS ip_cameras (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    location VARCHAR(300),
    description TEXT,
    manufacturer VARCHAR(50) NOT NULL DEFAULT 'generic',
    host VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL DEFAULT 554,
    username VARCHAR(100) DEFAULT 'admin',
    password_encrypted TEXT,
    channel INTEGER NOT NULL DEFAULT 1,
    subtype INTEGER NOT NULL DEFAULT 0,
    rtsp_url_override TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_seen TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cameras_user ON ip_cameras(user_id);
CREATE INDEX IF NOT EXISTS idx_cameras_active ON ip_cameras(is_active);

CREATE TABLE IF NOT EXISTS camera_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id UUID NOT NULL REFERENCES ip_cameras(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cam_events_camera ON camera_events(camera_id);
CREATE INDEX IF NOT EXISTS idx_cam_events_created ON camera_events(created_at);
