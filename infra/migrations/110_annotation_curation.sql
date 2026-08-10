-- 110_annotation_curation.sql
--
-- Estúdio de anotação: curadoria de frames (marcar frame como
-- ativo/dúvida/excluído sem apagar caixas) e ordenação/arquivamento de
-- classes (yolo_classes) para o painel de curação do frontend.
--
-- Por quê: o fluxo de curação em lote (aceitar/duvidar/excluir frames
-- antes do treino) precisa de um status por frame que não mexa em
-- frame_annotations nem em training_frames.is_annotated (campos já
-- usados por outros fluxos — ver ⛔ CONFLITO PROIBIDO em
-- annotation_repository/annotation_handlers/annotation_service, que
-- esta migration não toca). display_order/archived_at em yolo_classes
-- dão ao tenant controle de ordem no anotador e permitem "aposentar"
-- uma classe (ex.: renomeações RVB) sem apagar anotações existentes
-- (nunca apagar caixas — regra da casa).
--
-- Nota de numeração (C-04): o prompt original pedia "100_...", mas
-- infra/migrations/100_model_deployments.sql já existe neste repo
-- (última migration real no momento desta mudança: 109). Usando 110,
-- a próxima livre — validado contra o diretório real, não contra
-- memória/instrução.
--
-- Idempotência:
--   ADD COLUMN IF NOT EXISTS — no-op se já existir.
--   CHECK via DO $$ EXCEPTION WHEN duplicate_object — idempotente.
--   CREATE INDEX IF NOT EXISTS — idempotente.
-- Rodar 2× não produz erros (harness tests/harness/migrations/).

ALTER TABLE public.yolo_classes
    ADD COLUMN IF NOT EXISTS display_order INTEGER;

ALTER TABLE public.yolo_classes
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP;

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS curation_status VARCHAR(20) NOT NULL DEFAULT 'active';

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS curation_updated_at TIMESTAMP;

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS curation_updated_by UUID;

-- CHECK de curation_status — guardado em DO $$ para idempotência
DO $$
BEGIN
    ALTER TABLE public.training_frames
        ADD CONSTRAINT chk_training_frames_curation_status
        CHECK (curation_status IN ('active', 'duvida', 'excluida'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_training_frames_tenant_curation
    ON public.training_frames(tenant_id, curation_status);
