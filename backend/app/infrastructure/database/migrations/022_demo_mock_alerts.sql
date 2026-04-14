-- EPI Monitor V2 — Migration 022
-- Demo data: mock alerts using EXISTING cameras.
-- Uses the first camera found in the DB for all alerts.
-- Safe: ON CONFLICT DO NOTHING.

-- Insert alerts using the first available camera
DO $$
DECLARE
    cam_id UUID;
    t_id UUID := '00000000-0000-0000-0000-000000000001';
    frame_prefix TEXT := 'frames/d97cb03e-d113-4fc1-9d9b-f32394968694/b49084e1-ae30-486f-b446-579dd281e555/frame_';
BEGIN
    -- Get first camera
    SELECT id INTO cam_id FROM cameras WHERE tenant_id = t_id LIMIT 1;
    IF cam_id IS NULL THEN
        SELECT id INTO cam_id FROM cameras LIMIT 1;
    END IF;
    IF cam_id IS NULL THEN
        RAISE NOTICE 'No cameras found — skipping demo alerts';
        RETURN;
    END IF;

    -- Insert 13 demo alerts
    INSERT INTO alerts (id, camera_id, timestamp, violations, confidence, evidence_key, acknowledged, tenant_id)
    VALUES
      ('b0000001-demo-alert-0001-000000000001', cam_id, NOW() - INTERVAL '6 days 16 hours', '[{"class":"no_helmet","confidence":0.92}]'::jsonb, 0.92, frame_prefix || '0000.jpg', false, t_id),
      ('b0000001-demo-alert-0002-000000000002', cam_id, NOW() - INTERVAL '5 days 14 hours', '[{"class":"no_helmet","confidence":0.87}]'::jsonb, 0.87, frame_prefix || '0001.jpg', true, t_id),
      ('b0000001-demo-alert-0003-000000000003', cam_id, NOW() - INTERVAL '3 days 9 hours', '[{"class":"no_helmet","confidence":0.94}]'::jsonb, 0.94, frame_prefix || '0002.jpg', false, t_id),
      ('b0000001-demo-alert-0004-000000000004', cam_id, NOW() - INTERVAL '1 day 13 hours', '[{"class":"no_helmet","confidence":0.89}]'::jsonb, 0.89, frame_prefix || '0003.jpg', false, t_id),
      ('b0000001-demo-alert-0005-000000000005', cam_id, NOW() - INTERVAL '5 days 10 hours', '[{"class":"no_vest","confidence":0.85}]'::jsonb, 0.85, frame_prefix || '0004.jpg', false, t_id),
      ('b0000001-demo-alert-0006-000000000006', cam_id, NOW() - INTERVAL '4 days 7 hours', '[{"class":"no_vest","confidence":0.91}]'::jsonb, 0.91, frame_prefix || '0005.jpg', true, t_id),
      ('b0000001-demo-alert-0007-000000000007', cam_id, NOW() - INTERVAL '2 days 15 hours', '[{"class":"no_vest","confidence":0.88}]'::jsonb, 0.88, frame_prefix || '0006.jpg', false, t_id),
      ('b0000001-demo-alert-0008-000000000008', cam_id, NOW() - INTERVAL '4 days 12 hours', '[{"class":"no_glasses","confidence":0.79}]'::jsonb, 0.79, frame_prefix || '0007.jpg', false, t_id),
      ('b0000001-demo-alert-0009-000000000009', cam_id, NOW() - INTERVAL '1 day 8 hours', '[{"class":"no_glasses","confidence":0.82}]'::jsonb, 0.82, frame_prefix || '0008.jpg', false, t_id),
      ('b0000001-demo-alert-0010-000000000010', cam_id, NOW() - INTERVAL '3 days 16 hours', '[{"class":"no_gloves","confidence":0.76}]'::jsonb, 0.76, frame_prefix || '0009.jpg', true, t_id),
      ('b0000001-demo-alert-0011-000000000011', cam_id, NOW() - INTERVAL '6 hours', '[{"class":"no_gloves","confidence":0.81}]'::jsonb, 0.81, frame_prefix || '0010.jpg', false, t_id),
      ('b0000001-demo-alert-0012-000000000012', cam_id, NOW() - INTERVAL '2 days 9 hours', '[{"class":"no_helmet","confidence":0.93},{"class":"no_vest","confidence":0.86}]'::jsonb, 0.90, frame_prefix || '0011.jpg', false, t_id),
      ('b0000001-demo-alert-0013-000000000013', cam_id, NOW() - INTERVAL '3 hours', '[{"class":"no_helmet","confidence":0.88},{"class":"no_gloves","confidence":0.77}]'::jsonb, 0.83, frame_prefix || '0012.jpg', false, t_id)
    ON CONFLICT (id) DO NOTHING;

    RAISE NOTICE 'Demo alerts inserted with camera %', cam_id;
END $$;
