-- 131_dataset_versions_split_membership.sql
-- Persistência da MEMBRESIA do split — a régua do A/B das variantes de detector.
--
-- O PROBLEMA
-- `dataset_versions.split` guarda só a PROPORÇÃO ({"train":0.7,"val":0.2,"test":0.1}),
-- nunca quem caiu em cada lado. Não existe tabela de membresia, e
-- `model_evaluations.confusion_matrix` é classe×classe, sem id de imagem. Logo o
-- test set de todo build anterior é IRRECUPERÁVEL — nem re-executando o código:
-- o split do build 42023066 caiu no ramo com `random.shuffle` PURO, sem semente
-- (`random.Random(seed)` só entrou em 2026-08-24, versioning_v2.py:417).
-- Sem membresia gravada, "o holdout" é uma promessa, não um artefato.
--
-- POR QUE COLUNA jsonb E NÃO TABELA DE MEMBRESIA — pelo tamanho MEDIDO
--   maior test split do RVB hoje ...... 717 frames
--   maior versão inteira .............. 5.297 frames (v12-tudo)
--   pg_column_size(to_jsonb(705 uuids)) 28.208 bytes  (~28 KB)
--   pg_column_size(to_jsonb(5297 uuids)) 211.888 bytes (~207 KB)
--   23 versões `ready` do RVB, 63.067 frames somados → ~2,4 MB para TODO o
--   histórico do tenant.
-- Uma tabela de membresia custaria ~63 mil linhas, um repository novo, FK, índice
-- e uma leitura de 5 mil linhas por build — para comprar a única coisa que ela tem
-- de a mais: responder "em que versões o frame Y aparece". Nenhum caminho deste
-- sistema pergunta isso. E o padrão da casa nesta mesma tabela já é jsonb:
-- `split`, `augmentations` e `class_distribution` moram aqui do lado.
--
-- FORMATO
--   {"train": ["<frame_id>", ...], "val": [...], "test": [...]}
-- NULL = versão anterior a esta migration: membresia irrecuperável. O leitor
-- (DatasetRepository.get_holdout) marca `frozen=false` e a avaliação registra isso
-- em metrics — ausência de congelamento nunca é lida como congelamento.
--
-- Forward-only, idempotente (ADD COLUMN IF NOT EXISTS). Em produção o runner é
-- railway_start.py e re-roda toda migration a cada boot.

ALTER TABLE public.dataset_versions
    ADD COLUMN IF NOT EXISTS split_membership JSONB;

COMMENT ON COLUMN public.dataset_versions.split_membership IS
    'Membresia congelada do split: {"train":[frame_id...],"val":[...],"test":[...]}. '
    'NULL = build anterior à migration 131, membresia irrecuperável.';
