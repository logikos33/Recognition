-- 118_propagation_proposals.sql
--
-- Ledger POR-PROPOSTA das pré-anotações de propagação/busca — fecha o
-- buraco que a migration 111 deixou: o veredito de revisão era
-- por-FRAME (training_frames.pre_annotation_review_status ∈
-- accepted|rejected), all-or-nothing, e as propostas em si eram itens de
-- um array JSONB (training_frames.pre_annotations) sem id/status/job
-- próprios. Consequências reais medidas no DEV (job 9779305b, 2026-08-13,
-- 951 propostas): não dava para "rejeitar em lote por classe" (50% dos
-- frames têm 2+ classes — rejeitar o frame descarta o que era bom junto),
-- nem para guardar a proposta rejeitada como DADO DE AVALIAÇÃO (rejeitar
-- só marcava o frame; sem registro por-proposta não se mede se a próxima
-- rodada de propagação melhorou).
--
-- Modelo: esta tabela é a FONTE DA VERDADE por-proposta. training_frames.
-- pre_annotations passa a ser uma PROJEÇÃO DERIVADA — o app reconstrói o
-- JSONB (jsonb_agg das linhas ainda 'pending' do frame) a cada mutação
-- (aceitar/rejeitar/corrigir). Toda a maquinaria existente da fila
-- (list_images_filtered, _PENDING_PROPOSAL_CONDITION, provenance='proposta',
-- estúdio de anotação) continua lendo o JSONB e funciona sem alteração;
-- a granularidade por-proposta (rejeição por job/classe/confiança/seleção,
-- grade de triagem) vem das linhas.
--
-- SEGURANÇA DO TREINO (inalterada): aceitar uma proposta continua gravando
-- frame_annotations (source='pre_annotation', reviewed_by setado) — o gate
-- de procedência do export (versioning_v2.py:153-156) é ALLOWLIST
-- (source='manual' OR reviewed_by IS NOT NULL) e lê frame_annotations, NÃO
-- esta tabela. Proposta 'rejected'/'pending' nunca vira linha em
-- frame_annotations → estruturalmente fora do treino. Este novo estado NÃO
-- exige mudança no gate.
--
-- public.* com tenant_id (ADR-0016) — mesmo padrão de propagation_jobs
-- (112) e training_frames; não schema-per-tenant.
--
-- Nota de numeração (C-04): última migration real no diretório no momento
-- desta mudança é 117 (infra/migrations/117_edge_monitoring_thresholds.sql)
-- — validado contra o diretório real. Esta é a 118.
--
-- Idempotência:
--   CREATE TABLE IF NOT EXISTS (+ CHECK inline) — no-op se já existir.
--   CREATE INDEX IF NOT EXISTS — idempotente.
--   Backfill via INSERT ... SELECT com NOT EXISTS por frame — re-rodar não
--   duplica (frame que já tem linha é pulado). Seguro rodar 2× (harness
--   tests/harness/migrations/).

CREATE TABLE IF NOT EXISTS public.propagation_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),

    -- Frame que hospeda a proposta (o mesmo do array pre_annotations).
    -- CASCADE: apagar o frame apaga suas propostas (higiene; frame é o dono).
    frame_id UUID NOT NULL REFERENCES training_frames(id) ON DELETE CASCADE,

    -- Job de propagação que gerou a proposta (112). NULL para backfill sem
    -- atribuição confiável ou promoção de busca por conteúdo (115).
    -- SET NULL: apagar o job não apaga a proposta (é dado de avaliação).
    job_id UUID REFERENCES propagation_jobs(id) ON DELETE SET NULL,

    -- Origem da proposta — mesmo vocabulário do pipeline de pré-anotação.
    source VARCHAR(20) NOT NULL DEFAULT 'propagation'
        CHECK (source IN ('propagation', 'search', 'pre_annotation', 'backfill')),

    -- Rótulo LITERAL da paleta (ex.: "Sem Capacete") — mesmo string do item
    -- JSONB; a tradução label→class_id é feita na leitura (annotation_service).
    class_name VARCHAR(120) NOT NULL,
    confidence DOUBLE PRECISION,
    -- bbox normalizado [cx, cy, w, h] (0..1) — mesma forma do item JSONB.
    bbox JSONB NOT NULL,

    -- Índice original no array pre_annotations no momento do backfill/insert
    -- (rastreabilidade; NÃO é chave estável entre reescritas do JSONB).
    proposal_index INTEGER,

    status VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'rejected', 'corrected')),

    -- Por que foi rejeitada — METADADO DE AVALIAÇÃO (mede o padrão de erro
    -- da rodada de propagação): job | class | confidence | selection |
    -- manual. NULL quando não rejeitada.
    reject_reason VARCHAR(40),

    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_propagation_proposals_tenant_status
    ON public.propagation_proposals(tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_propagation_proposals_job
    ON public.propagation_proposals(job_id)
    WHERE job_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_propagation_proposals_frame
    ON public.propagation_proposals(frame_id);

-- Corte "por classe" da rejeição em lote / grade de triagem.
CREATE INDEX IF NOT EXISTS idx_propagation_proposals_tenant_class_status
    ON public.propagation_proposals(tenant_id, class_name, status);

-- ------------------------------------------------------------------
-- Backfill idempotente: uma linha 'pending' por item do array
-- pre_annotations dos frames AINDA pendentes (pre_annotation_review_status
-- IS NULL). Frames já revisados (accepted/rejected no nível de frame) e
-- frames com array vazio '[]' ficam de fora — nada a triar. NÃO altera o
-- JSONB (a projeção derivada só é reconstruída pelo app numa mutação).
-- Frame que já tem linha é pulado (NOT EXISTS) → re-rodar é no-op.
-- ------------------------------------------------------------------
INSERT INTO public.propagation_proposals
    (tenant_id, frame_id, job_id, source, class_name, confidence, bbox,
     proposal_index, status)
SELECT
    tf.tenant_id,
    tf.id,
    (
        SELECT pj.id FROM public.propagation_jobs pj
        WHERE pj.tenant_id = tf.tenant_id
          AND pj.status = 'completed'
          AND pj.pool_frame_ids @> to_jsonb(tf.id::text)
        ORDER BY pj.created_at DESC
        LIMIT 1
    ) AS job_id,
    'backfill',
    COALESCE(elem->>'class', elem->>'label'),
    CASE
        WHEN jsonb_typeof(elem->'confidence') = 'number'
            THEN (elem->>'confidence')::double precision
        ELSE NULL
    END,
    CASE
        WHEN jsonb_typeof(elem->'bbox') = 'array' THEN elem->'bbox'
        WHEN jsonb_typeof(elem->'bbox') = 'object'
            THEN jsonb_build_array(
                elem->'bbox'->'cx', elem->'bbox'->'cy',
                elem->'bbox'->'w',  elem->'bbox'->'h')
        ELSE NULL
    END,
    (ord - 1)::integer,
    'pending'
FROM public.training_frames tf,
     LATERAL jsonb_array_elements(tf.pre_annotations) WITH ORDINALITY AS e(elem, ord)
WHERE tf.pre_annotation_review_status IS NULL
  AND tf.pre_annotations IS NOT NULL
  AND jsonb_typeof(tf.pre_annotations) = 'array'
  AND jsonb_array_length(tf.pre_annotations) > 0
  AND COALESCE(elem->>'class', elem->>'label') IS NOT NULL
  AND (
        jsonb_typeof(elem->'bbox') = 'array'
        OR jsonb_typeof(elem->'bbox') = 'object'
      )
  AND NOT EXISTS (
        SELECT 1 FROM public.propagation_proposals pp
        WHERE pp.frame_id = tf.id
      );
