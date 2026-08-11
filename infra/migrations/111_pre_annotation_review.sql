-- 111_pre_annotation_review.sql
--
-- Fila de aprovação de propostas de IA: registra a REVISÃO de uma
-- pré-anotação pendente (aceita ou rejeitada), separado de
-- frame_annotations e de curation_status (migration 110) — nenhum dos
-- dois modela isso hoje.
--
-- Buraco de modelo que esta migration fecha: aceitar uma proposta já
-- grava frame_annotations (source='pre_annotation', reviewed_by setado —
-- ver annotation_repository.accept_pre_annotations, migration 095), mas
-- REJEITAR não tinha onde pousar. Uma proposta rejeitada não deve virar
-- caixa (frame_annotations não é o lugar — misturaria "não existe" com
-- "existe e foi recusada"), mas também não pode ficar invisível: sem
-- nenhum registro, a proposta permanece com provenance='proposta'
-- (frame_repository.py list_images_filtered) para sempre — a fila de
-- pendentes nunca esvazia.
--
-- pre_annotation_review_status ('accepted'/'rejected', validado na
-- aplicação — ver nota de CHECK abaixo) + reviewed_by/reviewed_at dão à
-- fila de pendentes um filtro estável: provenance='proposta' AND
-- pre_annotation_review_status IS NULL (frame_repository.
-- list_images_filtered, ?pending_review=true).
--
-- Nota de numeração (C-04): última migration real no momento desta
-- mudança é 110 (infra/migrations/110_annotation_curation.sql) —
-- validado contra o diretório real. Esta é a 111.
--
-- Nota de CHECK: a migration vizinha (110, curation_status) já usa o
-- padrão idempotente `DO $$ ... EXCEPTION WHEN duplicate_object` para
-- CHECK — reaproveitado aqui. IS NULL faz parte do CHECK porque o valor
-- inicial (proposta ainda não revisada) é NULL, não uma das duas opções.
--
-- Idempotência:
--   ADD COLUMN IF NOT EXISTS — no-op se já existir.
--   CHECK via DO $$ EXCEPTION WHEN duplicate_object — idempotente.
--   CREATE INDEX IF NOT EXISTS — idempotente.
-- Rodar 2× não produz erros (harness tests/harness/migrations/).

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS pre_annotation_review_status VARCHAR(16);

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS pre_annotation_reviewed_by UUID;

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS pre_annotation_reviewed_at TIMESTAMP;

-- CHECK de pre_annotation_review_status — guardado em DO $$ para idempotência
DO $$
BEGIN
    ALTER TABLE public.training_frames
        ADD CONSTRAINT chk_training_frames_pre_annotation_review_status
        CHECK (
            pre_annotation_review_status IS NULL
            OR pre_annotation_review_status IN ('accepted', 'rejected')
        );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_training_frames_tenant_pre_annotation_review
    ON public.training_frames(tenant_id, pre_annotation_review_status);
