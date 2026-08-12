-- 114_camera_collection_subtype.sql
--
-- Eixo COLETA da qualidade por câmera (rodada 11/08, D-85/D-86). São dois
-- eixos independentes: OPERAÇÃO (fps_target/quality_preset/live_view_subtype,
-- migrations 052/092) custa Orin+egress+navegador; COLETA custa ~nada
-- (~17 fotos/dia/câmera) e decide a qualidade do dado de treino.
--
-- 0 = stream principal (1080p/1440p — o mais alto que o canal tem)
-- 1 = substream (704x480)
--
-- Default 0 de propósito: anotar em alta é melhor MESMO que o treino rode em
-- baixa — coordenada é normalizada; caixa precisa em 1080p continua precisa
-- depois do downscale, caixa imprecisa em 480p é imprecisa para sempre.
-- O edge aplica por câmera no capture_frame (fallback: RECORDER_STREAM_SUBTYPE).
--
-- Nota de numeração (C-04): última migration real é 113
-- (113_camera_position_confirmed.sql, PR #353). Esta é a 114. Validado também
-- contra as 102-109 não-rastreadas do checkout principal (ADR-0021/0043).
--
-- Idempotência: ADD COLUMN IF NOT EXISTS — aditiva, forward-only.

ALTER TABLE public.cameras
    ADD COLUMN IF NOT EXISTS collection_subtype INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN public.cameras.collection_subtype IS
    'Stream usado pela COLETA de frames de treino: 0=principal (alta), '
    '1=substream. Independente da qualidade de OPERACAO '
    '(fps_target/quality_preset/live_view_subtype).';
