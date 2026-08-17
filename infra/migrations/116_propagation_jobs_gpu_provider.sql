-- 116_propagation_jobs_gpu_provider.sql
--
-- Propagação semeada no EDGE (Jetson do site) além do RunPod (nuvem de
-- terceiro) — decisão do Vitor: nenhuma imagem sai do site quando o
-- provider é onsite, então o guard fail-closed de datas (propagation_pool.py
-- — existe porque imagem SAI da Logikos p/ nuvem de terceiro) deixa de se
-- aplicar e anotações de operação (não só de encenação) viram semente
-- válida. Ver docs/REGISTRO_DE_DECISOES.md.
--
-- gpu_provider grava o provider RESOLVIDO no momento da criação do job
-- (app/domain/services/propagation_provider.py::resolve_propagation_provider
-- — request explícito > env PROPAGATION_GPU_PROVIDER > default 'runpod')
-- e é o que o dispatch (tasks/propagation.py) RECHECA antes de decidir se o
-- guard de datas se aplica — mesmo padrão de training_jobs.gpu_provider
-- (migration 097), sem CHECK inline (aplicação valida contra
-- app/constants.py::GpuProvider, mesma decisão da 097).
--
-- Nota de numeração (C-04): última migration real no momento desta
-- mudança é 115 (infra/migrations/115_search_jobs.sql) — validado contra o
-- diretório real. Esta é a 116.
--
-- Idempotência: ADD COLUMN IF NOT EXISTS — seguro rodar 2×
-- (harness tests/harness/migrations/run.sh).

ALTER TABLE public.propagation_jobs
    ADD COLUMN IF NOT EXISTS gpu_provider VARCHAR(20) NOT NULL DEFAULT 'runpod';
