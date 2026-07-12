-- 093_classes_tenant_module.sql
-- Adiciona tenant_id e module_code a yolo_classes, habilitando
-- isolamento multi-tenant (C-01) e namespacing por módulo.
--
-- Por quê: yolo_classes era filtrada por user_id; o pipeline MLOps
-- exige escopo por tenant_id. module_code permite que o mesmo tenant
-- tenha paletas de classes separadas por módulo (epi, fueling).
--
-- Idempotência: ADD COLUMN IF NOT EXISTS é no-op se já existir;
-- backfill WHERE IS NULL; CREATE INDEX IF NOT EXISTS.
-- Rodar 2× não produz erros.

ALTER TABLE public.yolo_classes
    ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES public.tenants(id);

ALTER TABLE public.yolo_classes
    ADD COLUMN IF NOT EXISTS module_code VARCHAR(50) NOT NULL DEFAULT 'epi';

-- Backfill tenant_id via users.tenant_id (idempotente: só linhas NULL)
UPDATE public.yolo_classes yc
   SET tenant_id = u.tenant_id
  FROM public.users u
 WHERE yc.user_id = u.id
   AND yc.tenant_id IS NULL;

-- Fallback para registros cujo user_id não tem tenant_id (orphaned)
UPDATE public.yolo_classes
   SET tenant_id = '00000000-0000-0000-0000-000000000001'
 WHERE tenant_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_yolo_classes_tenant_module
    ON public.yolo_classes(tenant_id, module_code);
