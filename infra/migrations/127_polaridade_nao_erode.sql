-- 127 · Devolve o NULL que a 125 apagava a cada boot no modo LEGADO.
--
-- O QUE ACONTECE. A 125 termina com um backfill sem recorte:
--
--     UPDATE public.yolo_classes SET is_violation = FALSE
--      WHERE is_violation IS NULL;
--
-- Em modo LEDGER (MIGRATIONS_LEDGER_CUTOVER=1, o DEV hoje) isso roda UMA vez e
-- é inofensivo. Em modo LEGADO — que o docstring de `runner_core.py` registra
-- como "padrão, produção continua aqui hoje" — TODA migration reexecuta a cada
-- boot da API. E nenhuma rota grava `is_violation`: `create_class` não inclui a
-- coluna, `update_class` só aceita name/color, `patch_class` tem whitelist fixa.
-- O único escritor é a migration.
--
-- Consequência em produção: classe criada pelo anotador nasce NULL e vira FALSE
-- no reinício seguinte. Uma classe de violação cujo nome não comece por "Sem "
-- ou "Uso incorreto" — "Fumando", "Área restrita", "Uso indevido de escada" —
-- passa a contar como CONFORMIDADE: some da tela de violações e entra no
-- numerador da taxa mostrada ao cliente. Sem correção possível pela UI.
--
-- Contradiz o cabeçalho da própria 125 ("NULL = ninguém decidiu ainda"; "o
-- prefixo é usado UMA VEZ, não é regra de runtime") e a ADR-0065 §2, que recusa
-- heurística de nome em runtime porque "erraria em silêncio na direção cara".
--
-- POR QUE UMA MIGRATION NOVA E NÃO EDITAR A 125. Eu tentei editar. O ledger
-- barrou o boot com checksum divergente e estava certo: forward-only aqui é
-- máquina, não convenção. E em modo legado esta 127 roda LOGO DEPOIS da 125 a
-- cada boot — ou seja, desfaz o excesso dela na mesma passagem, que é
-- exatamente o efeito desejado sem tocar num arquivo já aplicado.
--
-- O RECORTE. Classe criada a partir de 2026-08-25 nunca teve polaridade
-- decidida por ninguém (não há rota que grave). Devolver NULL a ela é restaurar
-- a verdade, e NULL na leitura conta como VIOLAÇÃO (fail-loud, ADR-0065 §4):
-- aparece onde alguém percebe, em vez de sumir onde ninguém olha. Classes
-- anteriores ficam como estão — lá o prefixo foi o valor inicial legítimo.
--
-- ⚠️ PRESSUPOSTO, e ele tem prazo: nenhuma rota grava `is_violation`. No dia em
-- que existir uma (é o que falta para o dono corrigir polaridade pela tela),
-- esta migration passa a apagar decisão humana e precisa ganhar a condição
-- "e ninguém decidiu explicitamente". Está registrado na issue de polaridade.
--
-- Idempotência: rodar 2× não muda nada — na segunda passagem já não há
-- `is_violation IS FALSE` com `created_at` no recorte que não seja NULL.

UPDATE public.yolo_classes
   SET is_violation = NULL
 WHERE is_violation IS FALSE
   AND created_at >= TIMESTAMP '2026-08-25 00:00:00';
