-- 092_camera_live_view_subtype.sql
--
-- Task-067: live view (visualização no browser) deve usar o substream por
-- padrão (segmentos ~1s, GOP curto, menor latência) SEM depender do `subtype`
-- já usado para construir a URL de detecção/inferência/gravação.
--
-- `subtype` continua existindo e intocado — é reaproveitado hoje só pelo
-- lazy-start/start_stream (não há consumidor de inferência conectado a ele
-- neste repositório), mas a task exige separação por design: quando o
-- pipeline de detecção for ligado (task-060), `subtype` não pode ter sido
-- silenciosamente redefinido para "sempre substream".
--
-- `live_view_subtype` é um campo NOVO e independente:
--   0 = stream principal (maior resolução, GOP mais longo)
--   1 = substream (H.264, GOP curto — alvo do live view, DEFAULT)
--
-- DEFAULT 1 aplica-se também a linhas já existentes (Postgres materializa o
-- default em ALTER TABLE ADD COLUMN para todas as linhas atuais).
--
-- Forward-only e idempotente: apenas ADD COLUMN IF NOT EXISTS. Sem DROP.
-- Seguro rodar múltiplas vezes.

ALTER TABLE public.cameras ADD COLUMN IF NOT EXISTS live_view_subtype INTEGER DEFAULT 1;

COMMENT ON COLUMN public.cameras.live_view_subtype IS
    'Subtype usado exclusivamente pelo live view (task-067) — independente do '
    'subtype de detecção/inferência/gravação. 1 = substream (default, baixa '
    'latência); 0 = principal. Fallback em runtime para 0 quando o substream '
    'falha no arranque (ver LocalStreamManager.start).';
