-- 106_edge_software_channels.sql
--
-- OTA bare-metal do agente edge (ADR-0057 item 10, Fase 4 OTA): "versão" é
-- git ref (commit/tag), não tag de imagem — não há Docker no box (ver
-- docs/edge/REGRAS_PLATAFORMA_JETSON.md §3.4). A nuvem publica um target_ref
-- por CANAL (ex. 'dev' pros boxes de desenvolvimento como a RVB); o agente
-- consulta GET /api/v1/edge/software/target e decide se atualiza. A nuvem só
-- INDICA — nunca dispara/empurra a atualização no device.
--
-- public.edge_software_channels: conceito de plataforma (canal de release),
-- não dado de tenant — sem tenant_id, análogo a uma config global (não é
-- schema-per-tenant nem coluna tenant_id em tudo; é o 3º caso: nem um nem
-- outro, porque não pertence a tenant nenhum). Só admin (superadmin) escreve.
--
-- device_tokens.channel: qual canal o device segue. Default 'dev' — todo
-- device criado hoje é pré-go-live/desenvolvimento; promoção pra 'stable'
-- é decisão manual do admin quando o site vira produção.
--
-- Idempotente: CREATE TABLE/ADD COLUMN IF NOT EXISTS. Forward-only: nenhum
-- DROP/ALTER TYPE/DELETE.

ALTER TABLE public.device_tokens
    ADD COLUMN IF NOT EXISTS channel TEXT NOT NULL DEFAULT 'dev';

CREATE TABLE IF NOT EXISTS public.edge_software_channels (
    channel     TEXT PRIMARY KEY,
    target_ref  TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by  UUID
);
