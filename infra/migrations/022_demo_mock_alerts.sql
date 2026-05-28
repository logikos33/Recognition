-- EPI Monitor V2 — Migration 022
-- Demo alerts using existing camera. PL/pgSQL for safety.

DO $$
DECLARE
    cam_id UUID;
    t_id UUID := '00000000-0000-0000-0000-000000000001';
    fp TEXT := 'frames/d97cb03e-d113-4fc1-9d9b-f32394968694/b49084e1-ae30-486f-b446-579dd281e555/frame_';
    cnt INT;
BEGIN
    -- Check if demo alerts already exist
    SELECT COUNT(*) INTO cnt FROM alerts WHERE evidence_key LIKE 'frames/d97cb03e%';
    IF cnt > 0 THEN
        RAISE NOTICE 'Demo alerts already exist (%), skipping', cnt;
        RETURN;
    END IF;

    -- Find first camera
    SELECT id INTO cam_id FROM cameras LIMIT 1;
    IF cam_id IS NULL THEN
        RAISE NOTICE 'No cameras — skipping demo alerts';
        RETURN;
    END IF;

    RAISE NOTICE 'Inserting demo alerts with camera %', cam_id;

    INSERT INTO alerts (camera_id, timestamp, violations, confidence, evidence_key, acknowledged, tenant_id)
    VALUES
      (cam_id, NOW()-INTERVAL '6d 16h', '[{"class":"no_helmet","confidence":0.92}]'::jsonb, 0.92, fp||'0000.jpg', false, t_id),
      (cam_id, NOW()-INTERVAL '5d 14h', '[{"class":"no_helmet","confidence":0.87}]'::jsonb, 0.87, fp||'0001.jpg', true, t_id),
      (cam_id, NOW()-INTERVAL '3d 9h',  '[{"class":"no_helmet","confidence":0.94}]'::jsonb, 0.94, fp||'0002.jpg', false, t_id),
      (cam_id, NOW()-INTERVAL '1d 13h', '[{"class":"no_helmet","confidence":0.89}]'::jsonb, 0.89, fp||'0003.jpg', false, t_id),
      (cam_id, NOW()-INTERVAL '5d 10h', '[{"class":"no_vest","confidence":0.85}]'::jsonb, 0.85, fp||'0004.jpg', false, t_id),
      (cam_id, NOW()-INTERVAL '4d 7h',  '[{"class":"no_vest","confidence":0.91}]'::jsonb, 0.91, fp||'0005.jpg', true, t_id),
      (cam_id, NOW()-INTERVAL '2d 15h', '[{"class":"no_vest","confidence":0.88}]'::jsonb, 0.88, fp||'0006.jpg', false, t_id),
      (cam_id, NOW()-INTERVAL '4d 12h', '[{"class":"no_glasses","confidence":0.79}]'::jsonb, 0.79, fp||'0007.jpg', false, t_id),
      (cam_id, NOW()-INTERVAL '1d 8h',  '[{"class":"no_glasses","confidence":0.82}]'::jsonb, 0.82, fp||'0008.jpg', false, t_id),
      (cam_id, NOW()-INTERVAL '3d 16h', '[{"class":"no_gloves","confidence":0.76}]'::jsonb, 0.76, fp||'0009.jpg', true, t_id),
      (cam_id, NOW()-INTERVAL '6h',     '[{"class":"no_gloves","confidence":0.81}]'::jsonb, 0.81, fp||'0010.jpg', false, t_id),
      (cam_id, NOW()-INTERVAL '2d 9h',  '[{"class":"no_helmet","confidence":0.93},{"class":"no_vest","confidence":0.86}]'::jsonb, 0.90, fp||'0011.jpg', false, t_id),
      (cam_id, NOW()-INTERVAL '3h',     '[{"class":"no_helmet","confidence":0.88},{"class":"no_gloves","confidence":0.77}]'::jsonb, 0.83, fp||'0012.jpg', false, t_id);

    RAISE NOTICE 'Demo alerts inserted successfully';
END $$;
