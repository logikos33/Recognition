-- 113_camera_position_confirmed.sql
--
-- Rodada 11/08 (D-85): o inventário dos 32 canais do iNVD 3032 provou que o
-- pareamento canal ↔ posição física NUNCA foi feito — nem para as 8 câmeras
-- originais (docs/edge/INVENTARIO_INVD_3032_2026-08-11.md, "Pendências").
-- ONVIF não prova identidade da câmera: sem um marcador explícito, alguém
-- batiza "Portaria" o que é a expedição e o erro só aparece na frente do
-- cliente.
--
-- position_confirmed marca, POR CÂMERA, se alguém já conferiu na fábrica que
-- o canal N mostra mesmo o lugar que o nome diz. Nasce FALSE para TODAS
-- (inclusive as 8 originais — é o estado honesto medido em 11/08). A tela de
-- triagem exibe "posição não confirmada" enquanto for FALSE; vira TRUE só por
-- ação humana (walkthrough na fábrica), nunca por inferência.
--
-- public.cameras (ADR-0016: recurso com tenant_id em public.*, padrão da
-- própria tabela desde a 035).
--
-- Nota de numeração (C-04): última migration real no momento desta mudança é
-- 112 (infra/migrations/112_propagation_jobs.sql em origin/develop) — validado
-- contra o diretório real E contra as 102–109 não-rastreadas do checkout
-- principal (cicatriz ADR-0021/ADR-0043: colisão de numeração). Esta é a 113.
--
-- Idempotência: ADD COLUMN IF NOT EXISTS — aditiva, forward-only, sem DROP,
-- sem ALTER TYPE, sem DELETE. Harness 2x: passa limpa nas duas passadas.

ALTER TABLE public.cameras
    ADD COLUMN IF NOT EXISTS position_confirmed BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN public.cameras.position_confirmed IS
    'TRUE só depois de conferência humana na fábrica de que o canal mostra o '
    'lugar que o nome diz (D-85: pareamento canal-posição nunca foi feito). '
    'Default FALSE para todas — inclusive as 8 originais.';
