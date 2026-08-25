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

-- ⚠️ EDIÇÃO EXCEPCIONAL DE MIGRATION JÁ APLICADA (2026-08-25, mesmo dia da
-- criação). A regra da casa é append-only, e ela pressupõe que re-rodar uma
-- migration seja INÓCUO. Esta não era: a versão original terminava com
--
--     UPDATE public.yolo_classes SET is_violation = FALSE
--      WHERE is_violation IS NULL;
--
-- sem recorte. Como `railway_start.py` re-roda TODA migration a cada boot, e
-- nenhuma rota da API grava `is_violation` (o único writer era esta migration),
-- toda classe criada pelo anotador nascia NULL e virava FALSE no reinício
-- seguinte. Efeito: uma classe de violação cujo nome não comece por "Sem " ou
-- "Uso incorreto" — "Fumando", "Área restrita", "Uso indevido de escada" —
-- passava a contar como CONFORMIDADE, sumia da tela de violações e inflava a
-- taxa de conformidade mostrada ao cliente. Sem caminho de correção pela UI.
--
-- Isso contradiz o cabeçalho DESTA migration em dois pontos ("NULL = ninguém
-- decidiu ainda" e "o prefixo é usado UMA VEZ, não é regra de runtime") e a
-- ADR-0063 §2, que recusa explicitamente heurística de nome em runtime porque
-- "erraria em silêncio na direção cara". A doc estava certa; o SQL, errado.
--
-- Deixar a cláusula e "corrigir depois" não era opção: ela reescreve o dado a
-- cada boot. Manter o append-only aqui seria preservar a forma da regra
-- destruindo o que ela protege.
--
-- O recorte por `created_at` faz o que o cabeçalho sempre prometeu: dá valor
-- inicial ao que JÁ EXISTIA quando a polaridade nasceu, e nunca mais. Classe
-- criada depois fica NULL — e NULL, na leitura, conta como violação
-- (fail-loud): aparece onde alguém percebe, em vez de sumir onde ninguém olha.
UPDATE public.yolo_classes
   SET is_violation = FALSE
 WHERE is_violation IS NULL
   AND created_at < TIMESTAMP '2026-08-25 00:00:00';

-- As consultas de alerta só perguntam pelo conjunto de PRESENÇA de um tenant.
CREATE INDEX IF NOT EXISTS idx_yolo_classes_presence
    ON public.yolo_classes (tenant_id, module_code)
    WHERE is_violation IS FALSE;
