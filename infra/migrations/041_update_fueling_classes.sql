-- 041_update_fueling_classes.sql
-- Renomeia fuel_nozzle → forklift (empilhadeira), adequado para carga/descarga.
--
-- (O cabeçalho antigo dizia "Migration 013" — número errado, herdado de outro
-- arquivo. O nome do arquivo sempre foi 041.)
--
-- IDEMPOTÊNCIA (correção): railway_start.py re-roda TODAS as migrations em todo
-- boot — não há tabela de controle. Este UPDATE não era re-executável:
--
--   1. boot 1: renomeia fuel_nozzle → forklift. OK.
--   2. boot 2: a 009_module_classes.sql re-semeia `fuel_nozzle` — a chave única
--      (module_code, class_name) ficou livre com o rename, então o INSERT dela
--      passa de novo.
--   3. boot 2: este UPDATE tenta renomear esse fuel_nozzle novo para 'forklift',
--      que já existe, e viola module_classes_module_code_class_name_key.
--
-- O erro é não-fatal (o boot segue), mas suja todo startup e mascara falha real
-- de migration. O guard NOT EXISTS torna o UPDATE um no-op quando 'forklift' já
-- está lá — exatamente o estado final desejado.
--
-- A linha `fuel_nozzle` remanescente NÃO é removida de propósito: DELETE é
-- proibido em migration (CLAUDE.md §Migrations — forward-only). Limpeza de dado,
-- se desejada, é script à parte com env gate.
UPDATE module_classes
   SET class_name   = 'forklift',
       display_name = 'Empilhadeira',
       dino_prompt  = 'forklift industrial vehicle loading dock'
 WHERE module_code = 'fueling'
   AND class_name  = 'fuel_nozzle'
   AND NOT EXISTS (
       SELECT 1
         FROM module_classes existing
        WHERE existing.module_code = 'fueling'
          AND existing.class_name  = 'forklift'
   );
