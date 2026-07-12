-- 089_edge_heartbeats_thermal.sql
--
-- Telemetria térmica e de decode nos heartbeats edge (WS11 — Observability).
-- A tabela public.edge_heartbeats (068) não tinha temperatura de GPU/CPU nem
-- métricas de decodificação de vídeo — necessárias para a visão de frota.
--
-- Colunas NULLABLE (aditivo): agentes edge antigos que não enviam os campos
-- continuam funcionando sem mudança; o envio pelo agente é evolução futura.
--
-- Idempotente: ADD COLUMN IF NOT EXISTS — rodável 2x sem erro.

ALTER TABLE public.edge_heartbeats
    ADD COLUMN IF NOT EXISTS gpu_temp_c NUMERIC(5,2);

ALTER TABLE public.edge_heartbeats
    ADD COLUMN IF NOT EXISTS cpu_temp_c NUMERIC(5,2);

ALTER TABLE public.edge_heartbeats
    ADD COLUMN IF NOT EXISTS decode_fps NUMERIC(6,2);

ALTER TABLE public.edge_heartbeats
    ADD COLUMN IF NOT EXISTS dropped_frames INT;
