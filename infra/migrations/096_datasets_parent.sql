-- 096_datasets_parent.sql
-- Cria tabela datasets (container lógico de dataset_versions) e
-- estende dataset_versions com linhagem completa: tenant_id,
-- module_code, dataset_id, split, augmentations, coco_r2_key,
-- export_format, status e created_by.
--
-- Por quê: dataset_versions não tinha pai, impedindo agrupamento
-- lógico de versões do mesmo conjunto de dados. A nova tabela
-- datasets é o container; dataset_versions ganha os campos necessários
-- para o build_dataset_version_v2 (split por grupo, COCO export,
-- upload para R2) — corrige bug do versioning.py atual (sem INSERT).
--
-- Idempotência:
--   CREATE TABLE IF NOT EXISTS — no-op se já existir.
--   ADD COLUMN IF NOT EXISTS — no-op se já existir.
--   Backfill WHERE IS NULL — idempotente.
--   CREATE INDEX IF NOT EXISTS — idempotente.
-- Rodar 2× não produz erros.

CREATE TABLE IF NOT EXISTS public.datasets (
    id          UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id   UUID         NOT NULL REFERENCES public.tenants(id),
    module_code VARCHAR(50)  NOT NULL DEFAULT 'epi',
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    created_by  UUID         REFERENCES public.users(id),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_datasets_tenant
    ON public.datasets(tenant_id, module_code);

-- Estender dataset_versions com campos multi-tenant e de linhagem
ALTER TABLE public.dataset_versions
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES public.tenants(id);

ALTER TABLE public.dataset_versions
    ADD COLUMN IF NOT EXISTS module_code VARCHAR(50) NOT NULL DEFAULT 'epi';

ALTER TABLE public.dataset_versions
    ADD COLUMN IF NOT EXISTS dataset_id UUID REFERENCES public.datasets(id);

-- split: {"train": 0.7, "val": 0.15, "test": 0.15}
ALTER TABLE public.dataset_versions
    ADD COLUMN IF NOT EXISTS split JSONB;

-- augmentations: config de data augmentation aplicada ao build
ALTER TABLE public.dataset_versions
    ADD COLUMN IF NOT EXISTS augmentations JSONB;

-- coco_r2_key: chave R2 do arquivo _annotations.coco.json (por split)
ALTER TABLE public.dataset_versions
    ADD COLUMN IF NOT EXISTS coco_r2_key TEXT;

-- export_format: 'coco', 'yolo', 'pascal_voc'
ALTER TABLE public.dataset_versions
    ADD COLUMN IF NOT EXISTS export_format VARCHAR(20);

-- status: 'building' | 'ready' | 'error'
ALTER TABLE public.dataset_versions
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ready';

ALTER TABLE public.dataset_versions
    ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES public.users(id);

-- Backfill tenant_id via users.tenant_id (idempotente: só linhas NULL)
UPDATE public.dataset_versions dv
   SET tenant_id = u.tenant_id
  FROM public.users u
 WHERE dv.user_id = u.id
   AND dv.tenant_id IS NULL;

-- Fallback para registros sem tenant resolvível
UPDATE public.dataset_versions
   SET tenant_id = '00000000-0000-0000-0000-000000000001'
 WHERE tenant_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_dataset_versions_tenant
    ON public.dataset_versions(tenant_id, module_code);

CREATE INDEX IF NOT EXISTS idx_dataset_versions_dataset
    ON public.dataset_versions(dataset_id);
