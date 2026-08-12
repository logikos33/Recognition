-- 113_search_jobs.sql
--
-- Busca por conteúdo (terceira carga do runner genérico de GPU —
-- kind='search', app/infrastructure/gpu/runpod_runner.py). Busca
-- open-vocabulary por termos de texto (ex.: "safety helmet") em frames
-- SELECIONADOS diretamente na galeria (não um pool por câmera+data, como a
-- propagação semeada, migration 112) — um pod RunPod remoto (OWLv2 zero-shot,
-- training/search_content.py) roda cada termo contra cada frame e devolve
-- ACHADOS (inventário de onde o termo aparece), NÃO propostas de anotação.
-- Um achado pode ser PROMOVIDO manualmente a proposta pendente (endpoint
-- .../jobs/<id>/promote), pousando em training_frames.pre_annotations —
-- mas o job em si nunca grava nada em pre_annotations sozinho.
--
-- public.* com tenant_id (ADR-0016) — mesmo padrão de propagation_jobs
-- (migration 112) e training_jobs: infraestrutura de pipeline de GPU, não
-- um recurso operacional do tenant.
--
-- selected_frame_ids + frames_hash são o núcleo do guard fail-closed
-- (mesmo desenho de pool_frame_ids/pool_hash da 112): a lista de frames é
-- MATERIALIZADA na criação (frame_ids escolhidos manualmente na galeria,
-- não um critério câmera+data) e REVALIDADA no dispatch (refetch por id) —
-- qualquer frame que hoje não pertença mais ao tenant, não tenha r2_key,
-- ou cujo captured_at::date caia fora de SEARCH_CLOUD_ALLOWED_DATES aborta
-- o job inteiro (nunca prossegue parcialmente). Esse guard de datas é
-- ESPECÍFICO da busca (além do flag por-tenant
-- training_third_party_cloud_enabled, reusado da propagação): protege a
-- regra "frames de operação não vão para a nuvem" quando nem toda captura
-- do tenant pode ser mandada a um provedor de terceiro.
--
-- Nota de numeração (C-04): última migration real no momento desta
-- mudança é 112 (infra/migrations/112_propagation_jobs.sql) — validado
-- contra o diretório real. Esta é a 113.
--
-- Idempotência: CREATE TABLE IF NOT EXISTS com CHECK inline — tabela nova,
-- sem ALTER; se já existir, o statement inteiro (CHECK incluso) é no-op.
-- CREATE INDEX IF NOT EXISTS — idempotente. Seguro rodar 2× (harness
-- tests/harness/migrations/run.sh).

CREATE TABLE IF NOT EXISTS public.search_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),

    status VARCHAR(20) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'stopped')),

    -- Lista MATERIALIZADA de frame_ids escolhidos na galeria no momento da
    -- criação do job — a trava real (guard fail-closed revalida cada frame
    -- por id no dispatch, nunca reconsulta a galeria às cegas).
    selected_frame_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- sha256 da lista ordenada de selected_frame_ids — recomputado e
    -- reconferido no dispatch (detecta qualquer drift entre a criação do
    -- job e o envio pra GPU).
    frames_hash TEXT,

    -- [{label, query}, ...] — label = rótulo exibido/promovido na proposta;
    -- query = texto em inglês passado ao OWLv2 (open-vocabulary).
    terms JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Achados (inventário) — [{frame_id, term, label, bbox, confidence}].
    -- NÃO é pre_annotations: um achado só vira proposta pendente via
    -- POST .../jobs/<id>/promote (append_pre_annotations, merge no jsonb
    -- existente, nunca sobrescreve propostas pendentes de outro job).
    results JSONB NOT NULL DEFAULT '[]'::jsonb,
    findings_count INTEGER NOT NULL DEFAULT 0,

    -- Token por-job pro callback da GPU remota (mesmo padrão de
    -- propagation_jobs.callback_token — X-Callback-Token, hmac.compare_digest).
    callback_token TEXT,
    -- pod_id RunPod (mesmo padrão de propagation_jobs.gpu_instance_ref) —
    -- o reconciler (tasks/gpu_reconciler.py) passa a cobrir esta tabela
    -- também (união com training_jobs/propagation_jobs).
    gpu_instance_ref TEXT,

    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_reason TEXT,

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_search_jobs_tenant
    ON public.search_jobs(tenant_id);

CREATE INDEX IF NOT EXISTS idx_search_jobs_status
    ON public.search_jobs(status);

-- Espelha idx_propagation_jobs_gpu_instance_ref: consulta por
-- gpu_instance_ref (pod_id) pra reconciliar pods órfãos/expirados.
CREATE INDEX IF NOT EXISTS idx_search_jobs_gpu_instance_ref
    ON public.search_jobs(gpu_instance_ref)
    WHERE gpu_instance_ref IS NOT NULL;
