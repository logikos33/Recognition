-- 125 · Polaridade da classe do TENANT: presença × ausência (ADR-0063).
--
-- Por quê: `module_classes.is_violation` (migration 009) já responde isto para
-- o catálogo GLOBAL (helmet=false, no_helmet=true). As classes da RVB vivem em
-- `yolo_classes` (custom por tenant, migration 003 + 093), que não tem a
-- coluna — e `module_service.get_classes()` devolvia `is_violation: False`
-- HARDCODED para todas elas. Resultado: "Sem protetor de ouvido" e "Protetor
-- auditivo" chegavam ao frontend com a MESMA polaridade, e ela era a errada.
--
-- ANULÁVEL de propósito. `railway_start.py` re-roda TODA migration a cada boot
-- da API. Um backfill sem a guarda `WHERE is_violation IS NULL` desfaria a
-- correção manual de um admin a cada reinício. NULL = "ninguém decidiu ainda"
-- — e, na LEITURA, NULL nunca conta como presença (fail-loud, ADR-0017):
-- alerta com classe indecisa aparece em VIOLAÇÕES, onde alguém percebe.
--
-- O prefixo "Sem " é usado UMA VEZ, aqui, para dar valor inicial ao que já
-- existe. Não é regra de runtime: a partir daqui a verdade é a linha.
--
-- Idempotência: ADD COLUMN IF NOT EXISTS + UPDATE ... WHERE IS NULL +
-- CREATE INDEX IF NOT EXISTS. Rodar 2× não produz erro nem muda dado.

ALTER TABLE public.yolo_classes
    ADD COLUMN IF NOT EXISTS is_violation BOOLEAN;

-- Backfill só do que nunca foi decidido (idempotente e não-destrutivo).
UPDATE public.yolo_classes
   SET is_violation = TRUE
 WHERE is_violation IS NULL
   AND (name ILIKE 'Sem %' OR name ILIKE 'Uso incorreto%');

UPDATE public.yolo_classes
   SET is_violation = FALSE
 WHERE is_violation IS NULL;

-- As consultas de alerta só perguntam pelo conjunto de PRESENÇA de um tenant.
CREATE INDEX IF NOT EXISTS idx_yolo_classes_presence
    ON public.yolo_classes (tenant_id, module_code)
    WHERE is_violation IS FALSE;
