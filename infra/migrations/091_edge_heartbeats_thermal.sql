-- 091_edge_heartbeats_thermal.sql
--
-- WS10 — FPS por câmera na operação (health-aware).
-- Adiciona métricas de térmica e decode ao heartbeat do edge (spec VMS §3-4):
--   gpu_temp_c  — temperatura da GPU em °C reportada pelo agente edge
--   decode_pct  — utilização do decoder de vídeo (NVDEC/VAAPI) em %
--
-- Campos opcionais e progressivos: agentes antigos que não enviam os campos
-- continuam válidos (colunas NULL); a UI exibe '—' quando ausentes.
--
-- Forward-only e idempotente: apenas ADD COLUMN IF NOT EXISTS. Sem DROP.
-- Seguro rodar múltiplas vezes.

ALTER TABLE public.edge_heartbeats
    ADD COLUMN IF NOT EXISTS gpu_temp_c NUMERIC(5,2);

ALTER TABLE public.edge_heartbeats
    ADD COLUMN IF NOT EXISTS decode_pct NUMERIC(5,2);

COMMENT ON COLUMN public.edge_heartbeats.gpu_temp_c IS
    'Temperatura da GPU em graus Celsius (telemetria térmica — VMS §3-4).';

COMMENT ON COLUMN public.edge_heartbeats.decode_pct IS
    'Utilização do decoder de vídeo em % (NVDEC/VAAPI — VMS §3-4).';
