-- EPI Monitor V2 — Migration 022
-- Demo data: mock cameras + realistic alerts with evidence from existing R2 frames.
-- Safe: uses INSERT with ON CONFLICT DO NOTHING to avoid duplicates on re-run.

-- 1. Mock cameras for demo (tenant default)
-- user_id do admin (d97cb03e...) para FK de cameras
INSERT INTO cameras (id, user_id, name, location, description, host, port, is_active, tenant_id, created_at)
VALUES
  ('a0000001-demo-0001-0001-000000000001', 'd97cb03e-d113-4fc1-9d9b-f32394968694', 'CAM-01 Portaria Principal', 'Portaria', 'Câmera na entrada principal da fábrica', '192.168.1.101', 554, true, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '30 days'),
  ('a0000001-demo-0001-0002-000000000002', 'd97cb03e-d113-4fc1-9d9b-f32394968694', 'CAM-02 Área de Produção', 'Produção', 'Câmera na linha de produção', '192.168.1.102', 554, true, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '30 days'),
  ('a0000001-demo-0001-0003-000000000003', 'd97cb03e-d113-4fc1-9d9b-f32394968694', 'CAM-03 Estoque', 'Estoque', 'Câmera no depósito de materiais', '192.168.1.103', 554, true, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '30 days'),
  ('a0000001-demo-0001-0004-000000000004', 'd97cb03e-d113-4fc1-9d9b-f32394968694', 'CAM-04 Carga e Descarga', 'Doca', 'Câmera na área de carga/descarga', '192.168.1.104', 554, true, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '30 days')
ON CONFLICT (id) DO NOTHING;

-- 2. Mock alerts with evidence_key pointing to real R2 frames
-- Using frames from video b49084e1 which exist in R2
INSERT INTO alerts (id, camera_id, timestamp, violations, confidence, evidence_key, acknowledged, tenant_id, created_at)
VALUES
  -- Sem capacete (4 alertas)
  ('b0000001-demo-alert-0001-000000000001',
   'a0000001-demo-0001-0002-000000000002',
   NOW() - INTERVAL '6 days' + INTERVAL '7 hours 32 minutes',
   '[{"class": "no_helmet", "confidence": 0.92}]'::jsonb,
   0.92,
   'frames/d97cb03e-d113-4fc1-9d9b-f32394968694/b49084e1-ae30-486f-b446-579dd281e555/frame_0000.jpg',
   false, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '6 days'),

  ('b0000001-demo-alert-0002-000000000002',
   'a0000001-demo-0001-0001-000000000001',
   NOW() - INTERVAL '5 days' + INTERVAL '9 hours 15 minutes',
   '[{"class": "no_helmet", "confidence": 0.87}]'::jsonb,
   0.87,
   'frames/d97cb03e-d113-4fc1-9d9b-f32394968694/b49084e1-ae30-486f-b446-579dd281e555/frame_0001.jpg',
   true, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '5 days'),

  ('b0000001-demo-alert-0003-000000000003',
   'a0000001-demo-0001-0002-000000000002',
   NOW() - INTERVAL '3 days' + INTERVAL '14 hours 55 minutes',
   '[{"class": "no_helmet", "confidence": 0.94}]'::jsonb,
   0.94,
   'frames/d97cb03e-d113-4fc1-9d9b-f32394968694/b49084e1-ae30-486f-b446-579dd281e555/frame_0002.jpg',
   false, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '3 days'),

  ('b0000001-demo-alert-0004-000000000004',
   'a0000001-demo-0001-0004-000000000004',
   NOW() - INTERVAL '1 day' + INTERVAL '10 hours 42 minutes',
   '[{"class": "no_helmet", "confidence": 0.89}]'::jsonb,
   0.89,
   'frames/d97cb03e-d113-4fc1-9d9b-f32394968694/b49084e1-ae30-486f-b446-579dd281e555/frame_0003.jpg',
   false, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '1 day'),

  -- Sem colete (3 alertas)
  ('b0000001-demo-alert-0005-000000000005',
   'a0000001-demo-0001-0003-000000000003',
   NOW() - INTERVAL '5 days' + INTERVAL '13 hours 20 minutes',
   '[{"class": "no_vest", "confidence": 0.85}]'::jsonb,
   0.85,
   'frames/d97cb03e-d113-4fc1-9d9b-f32394968694/b49084e1-ae30-486f-b446-579dd281e555/frame_0004.jpg',
   false, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '5 days'),

  ('b0000001-demo-alert-0006-000000000006',
   'a0000001-demo-0001-0002-000000000002',
   NOW() - INTERVAL '4 days' + INTERVAL '16 hours 30 minutes',
   '[{"class": "no_vest", "confidence": 0.91}]'::jsonb,
   0.91,
   'frames/d97cb03e-d113-4fc1-9d9b-f32394968694/b49084e1-ae30-486f-b446-579dd281e555/frame_0005.jpg',
   true, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '4 days'),

  ('b0000001-demo-alert-0007-000000000007',
   'a0000001-demo-0001-0001-000000000001',
   NOW() - INTERVAL '2 days' + INTERVAL '8 hours 10 minutes',
   '[{"class": "no_vest", "confidence": 0.88}]'::jsonb,
   0.88,
   'frames/d97cb03e-d113-4fc1-9d9b-f32394968694/b49084e1-ae30-486f-b446-579dd281e555/frame_0006.jpg',
   false, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '2 days'),

  -- Sem óculos (2 alertas)
  ('b0000001-demo-alert-0008-000000000008',
   'a0000001-demo-0001-0002-000000000002',
   NOW() - INTERVAL '4 days' + INTERVAL '11 hours 5 minutes',
   '[{"class": "no_glasses", "confidence": 0.79}]'::jsonb,
   0.79,
   'frames/d97cb03e-d113-4fc1-9d9b-f32394968694/b49084e1-ae30-486f-b446-579dd281e555/frame_0007.jpg',
   false, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '4 days'),

  ('b0000001-demo-alert-0009-000000000009',
   'a0000001-demo-0001-0003-000000000003',
   NOW() - INTERVAL '1 day' + INTERVAL '15 hours 45 minutes',
   '[{"class": "no_glasses", "confidence": 0.82}]'::jsonb,
   0.82,
   'frames/d97cb03e-d113-4fc1-9d9b-f32394968694/b49084e1-ae30-486f-b446-579dd281e555/frame_0008.jpg',
   false, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '1 day'),

  -- Sem luvas (2 alertas)
  ('b0000001-demo-alert-0010-000000000010',
   'a0000001-demo-0001-0004-000000000004',
   NOW() - INTERVAL '3 days' + INTERVAL '7 hours 50 minutes',
   '[{"class": "no_gloves", "confidence": 0.76}]'::jsonb,
   0.76,
   'frames/d97cb03e-d113-4fc1-9d9b-f32394968694/b49084e1-ae30-486f-b446-579dd281e555/frame_0009.jpg',
   true, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '3 days'),

  ('b0000001-demo-alert-0011-000000000011',
   'a0000001-demo-0001-0002-000000000002',
   NOW() - INTERVAL '6 hours',
   '[{"class": "no_gloves", "confidence": 0.81}]'::jsonb,
   0.81,
   'frames/d97cb03e-d113-4fc1-9d9b-f32394968694/b49084e1-ae30-486f-b446-579dd281e555/frame_0010.jpg',
   false, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '6 hours'),

  -- Múltiplas violações (2 alertas)
  ('b0000001-demo-alert-0012-000000000012',
   'a0000001-demo-0001-0001-000000000001',
   NOW() - INTERVAL '2 days' + INTERVAL '14 hours 20 minutes',
   '[{"class": "no_helmet", "confidence": 0.93}, {"class": "no_vest", "confidence": 0.86}]'::jsonb,
   0.90,
   'frames/d97cb03e-d113-4fc1-9d9b-f32394968694/b49084e1-ae30-486f-b446-579dd281e555/frame_0011.jpg',
   false, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '2 days'),

  ('b0000001-demo-alert-0013-000000000013',
   'a0000001-demo-0001-0004-000000000004',
   NOW() - INTERVAL '3 hours',
   '[{"class": "no_helmet", "confidence": 0.88}, {"class": "no_gloves", "confidence": 0.77}]'::jsonb,
   0.83,
   'frames/d97cb03e-d113-4fc1-9d9b-f32394968694/b49084e1-ae30-486f-b446-579dd281e555/frame_0012.jpg',
   false, '00000000-0000-0000-0000-000000000001', NOW() - INTERVAL '3 hours')

ON CONFLICT (id) DO NOTHING;
