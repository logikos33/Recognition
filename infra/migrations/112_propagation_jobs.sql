-- 112_propagation_jobs.sql
--
-- Propagação semeada (pré-anotação em GPU RunPod, kind='propagate' do
-- runner genérico — infrastructure/gpu/runpod_runner.py, PR #341). Um
-- humano anota algumas caixas ("sementes") num pool de frames do mesmo
-- critério (câmera(s) + intervalo de data); a GPU remota (DINOv2+SAM,
-- training/propagate_seeded.py) propõe caixas para o restante do pool por
-- similaridade de embedding — as propostas pousam em
-- public.training_frames.pre_annotations (mesmo jsonb já consumido pela
-- fila de aprovação da migration 111).
--
-- public.* com tenant_id (ADR-0016) — mesmo padrão de training_jobs
-- (migration 003), não schema-per-tenant: um job de propagação não é um
-- recurso operacional do tenant (câmera/modelo/detecção), é infraestrutura
-- de pipeline de treino, como training_jobs.
--
-- pool_frame_ids + pool_hash são o núcleo do guard fail-closed (dispatch
-- task revalida frame a frame contra pool_criteria e recomputa pool_hash
-- ANTES de mandar qualquer imagem pra GPU de terceiro — ver
-- app/infrastructure/queue/tasks/propagation.py). Sem "sessão de coleta"
-- no domínio (recorder_id é o NVR físico, igual em todos os frames de
-- todos os dias — não identifica um lote), a única trava confiável é a
-- LISTA MATERIALIZADA gravada no próprio job, nunca um critério
-- reavaliado às cegas no momento do dispatch.
--
-- Nota de numeração (C-04): última migration real no momento desta
-- mudança é 111 (infra/migrations/111_pre_annotation_review.sql) —
-- validado contra o diretório real. Esta é a 112.
--
-- Idempotência: CREATE TABLE IF NOT EXISTS com CHECK inline — tabela nova,
-- sem ALTER; se já existir, o statement inteiro (CHECK incluso) é no-op.
-- CREATE INDEX IF NOT EXISTS — idempotente. Seguro rodar 2× (harness
-- tests/harness/migrations/run.sh).

CREATE TABLE IF NOT EXISTS public.propagation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),

    status VARCHAR(20) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'stopped')),

    -- Critério do pool tal como pedido (camera_ids, date_from/date_to,
    -- validation_only) — auditoria/replay do pedido original.
    pool_criteria JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Lista MATERIALIZADA de frame_ids no momento da criação do job — a
    -- trava real (guard fail-closed revalida cada frame contra
    -- pool_criteria no dispatch, nunca reavalia o critério às cegas).
    pool_frame_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- sha256 da lista ordenada de pool_frame_ids — recomputado e
    -- reconferido no dispatch (detecta qualquer drift entre a criação do
    -- job e o envio pra GPU).
    pool_hash VARCHAR(64),

    seed_frame_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    seed_count INTEGER NOT NULL DEFAULT 0,
    proposals_count INTEGER NOT NULL DEFAULT 0,

    -- Token por-job pro callback da GPU remota (mesmo padrão de
    -- training_jobs.callback_token — X-Callback-Token, hmac.compare_digest).
    callback_token VARCHAR(128),
    -- pod_id RunPod (mesmo padrão de training_jobs.gpu_instance_ref) — o
    -- reconciler (tasks/gpu_reconciler.py) passa a cobrir esta tabela
    -- também (união com training_jobs).
    gpu_instance_ref VARCHAR(128),

    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_reason TEXT,

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_propagation_jobs_tenant
    ON public.propagation_jobs(tenant_id);

CREATE INDEX IF NOT EXISTS idx_propagation_jobs_status
    ON public.propagation_jobs(status);

-- Espelha idx_training_jobs equivalente implícito do reconciler: consulta
-- por gpu_instance_ref (pod_id) pra reconciliar pods órfãos/expirados.
CREATE INDEX IF NOT EXISTS idx_propagation_jobs_gpu_instance_ref
    ON public.propagation_jobs(gpu_instance_ref)
    WHERE gpu_instance_ref IS NOT NULL;
