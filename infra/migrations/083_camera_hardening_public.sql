-- 083_camera_hardening_public.sql
--
-- Completa a 075: os campos de hardening (detection_stream_url, video_codec,
-- max_auth_failures) foram adicionados apenas aos schemas de tenants, mas o
-- camera_repository (CRUD principal, /api/cameras) consulta public.cameras e
-- inclui essas colunas no SELECT — em bancos onde public.cameras não as tem,
-- toda listagem de câmeras falha com 503 "column does not exist"
-- (observado no ambiente Desenvolvimento em 2026-07-01).
--
-- Idempotente: ADD COLUMN IF NOT EXISTS. Sem DROP. No-op onde já existem.

ALTER TABLE public.cameras ADD COLUMN IF NOT EXISTS detection_stream_url TEXT;
ALTER TABLE public.cameras ADD COLUMN IF NOT EXISTS video_codec TEXT;
ALTER TABLE public.cameras ADD COLUMN IF NOT EXISTS max_auth_failures INTEGER DEFAULT 5;
