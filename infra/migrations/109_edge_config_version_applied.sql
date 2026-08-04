-- 109_edge_config_version_applied.sql
--
-- ADR-0058 (fatia mínima) — divergência de config observável.
--
-- O edge-sync-agent agora resolve RECORDER_CHANNEL_MAP (câmera→canal do
-- gravador) preferencialmente via GET /api/v1/edge/config/poll (cache local
-- alimentado pelo ConfigPoller), caindo para o .env só na transição. Para
-- tornar uma divergência entre "config que a nuvem manda" e "config que o
-- box tem efetivamente aplicada" visível (em vez de silenciosa — o caso que
-- motivou esta mudança: config/poll dizia cameras=2 e o box só monitorava 1),
-- o heartbeat passa a reportar o config_version (hash) aplicado no momento em
-- que o RecorderClient do device foi construído.
--
-- Coluna opcional: agentes antigos que não enviam o campo continuam válidos
-- (NULL — nada a comparar, sem alarme falso).
--
-- Forward-only e idempotente: apenas ADD COLUMN IF NOT EXISTS. Sem DROP.
-- Seguro rodar múltiplas vezes.

ALTER TABLE public.edge_heartbeats
    ADD COLUMN IF NOT EXISTS config_version_applied VARCHAR(32);

COMMENT ON COLUMN public.edge_heartbeats.config_version_applied IS
    'Hash config_version (GET /api/v1/edge/config/poll) do RECORDER_CHANNEL_MAP '
    'efetivamente em uso no device no momento em que o RecorderClient foi '
    'construído — "env" (fallback local) ou "" quando o agente é antigo demais '
    'para reportar. Comparado ao config_version corrente no ingest do heartbeat '
    '(edge/routes.py::ingest_heartbeat) para logar divergência.';
