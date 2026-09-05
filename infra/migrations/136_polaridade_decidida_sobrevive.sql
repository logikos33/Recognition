-- 136 · A polaridade decidida por GENTE sobrevive ao boot seguinte.
--
-- O QUE ESTÁ QUEBRADO, medido (não suposto):
--
-- Em modo LEGADO (`MIGRATIONS_LEDGER_CUTOVER` ausente — é o caso da produção
-- hoje, conferido nas variáveis do serviço) `runner_core.run_legacy` reexecuta
-- TODO `infra/migrations/*.sql` a cada boot da API. Duas migrations escrevem
-- `public.yolo_classes.is_violation` sem perguntar se alguém já decidiu:
--
--   125  UPDATE ... SET is_violation = TRUE  WHERE is_violation IS NULL
--                                              AND (name ILIKE 'Sem %'
--                                                   OR name ILIKE 'Uso incorreto%');
--        UPDATE ... SET is_violation = FALSE WHERE is_violation IS NULL;
--
--   127  UPDATE ... SET is_violation = NULL  WHERE is_violation IS FALSE
--                                              AND created_at >= '2026-08-25';
--
-- Quem paga a conta, em ordem de tamanho:
--
--  1) A CALIBRAÇÃO DA RVB (ADR-0067 + `scripts/ops/aplicar_calibracao_rvb.py`).
--     "Sem protetor de ouvido" (27,3% de precisão) e "Uso incorreto de mascara"
--     (20,0%) são rebaixadas para INDECISA (`is_violation = NULL`: registra,
--     não acusa). No boot seguinte o PRIMEIRO UPDATE da 125 casa o prefixo
--     "Sem "/"Uso incorreto" e devolve as duas para TRUE — voltam a ACUSAR
--     quem cumpre. Não é degradação silenciosa: é a reversão completa da
--     decisão, no sentido caro.
--
--  2) A DECISÃO PELA TELA. A 127 escreveu no cabeçalho dela: "no dia em que
--     existir uma rota que grave is_violation, esta migration passa a apagar
--     decisão humana". Esse dia chegou e passou: `TenantClassService.
--     create_class` EXIGE `is_violation`, e `patch_class` tem `is_violation`
--     na whitelist (`_PATCHABLE_CLASS_COLUMNS`) — PATCH /classes/<id> grava a
--     coluna. Classe criada a partir de 2026-08-25 marcada como CONFORMIDADE
--     (FALSE) pelo dono volta a INDECISA no próximo deploy.
--
-- POR QUE UMA MIGRATION NOVA. Forward-only é máquina aqui, não convenção: o
-- ledger aborta o boot com checksum divergente se a 125 ou a 127 forem
-- editadas. Como o loop legado aplica em ordem lexicográfica, uma migration
-- 136 roda DEPOIS das duas na MESMA passagem — desfaz o excesso delas antes de
-- a API atender a primeira requisição. É a condição "só aplica o padrão onde
-- ninguém decidiu" implementada onde dá para implementar.
--
-- A MARCA. `violation_decided_at IS NOT NULL` = gente decidiu; ninguém mais
-- decide por ela. `violation_decision` guarda O QUE foi decidido — inclusive
-- NULL (indecisa DELIBERADA, o estado que a calibração usa), que é
-- indistinguível de "ninguém decidiu" se olharmos só `is_violation`. Por isso
-- são duas colunas e não uma.
--
-- Quem escreve a marca: `AnnotationRepository.create_class`/`patch_class` (as
-- portas vivas do Estúdio) e `scripts/ops/aplicar_calibracao_rvb.py`. Linha
-- sem marca continua exatamente como está hoje — esta migration não inventa
-- decisão para ninguém, e não é backfill.
--
-- ⛔ Nada é apagado. Só ADD COLUMN IF NOT EXISTS + UPDATE condicional.
--
-- Idempotência: a 2ª passagem não acha linha com
-- `is_violation IS DISTINCT FROM violation_decision` — zero linha afetada.
-- Provado em `services/api/tests/integration/test_polaridade_decidida_sobrevive.py`
-- (duas passadas completas).

ALTER TABLE public.yolo_classes
    ADD COLUMN IF NOT EXISTS violation_decision BOOLEAN;

ALTER TABLE public.yolo_classes
    ADD COLUMN IF NOT EXISTS violation_decided_at TIMESTAMPTZ;

COMMENT ON COLUMN public.yolo_classes.violation_decided_at IS
    'Quando gente decidiu a polaridade. NOT NULL = decisão humana; a 136 '
    'restaura is_violation a partir de violation_decision a cada boot.';

COMMENT ON COLUMN public.yolo_classes.violation_decision IS
    'A polaridade que gente decidiu (NULL aqui = indecisa DELIBERADA, quando '
    'violation_decided_at está preenchido). Fonte de verdade sobre is_violation.';

-- Desfaz, na mesma passagem, o que 125/127 acabaram de reescrever por cima de
-- decisão humana. Onde ninguém decidiu (violation_decided_at IS NULL) o padrão
-- das migrations anteriores continua valendo, intocado.
UPDATE public.yolo_classes
   SET is_violation = violation_decision
 WHERE violation_decided_at IS NOT NULL
   AND is_violation IS DISTINCT FROM violation_decision;
