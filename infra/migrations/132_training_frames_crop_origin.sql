-- 132_training_frames_crop_origin.sql
-- Vínculo RECORTE → FRAME DE ORIGEM. Hoje não existe, e por isso todo recorte
-- do acervo é órfão.
--
-- O PROBLEMA (medido)
-- O modelo é SERVIDO em frame cheio de CFTV (inference_engine.py:73,128-131
-- chama predict(frame) com o quadro inteiro; detectors.py:274 redimensiona o
-- quadro inteiro para 560x560 — não há recorte de pessoa em lugar nenhum do
-- caminho servido). Mas 95,9% do dado de TREINO é recorte de pessoa, produzido
-- pelo coletor do edge (collector_loop.py:202 e replay_miner.py:764, ambos
-- chamando person_detector.crop_person).
-- Quando o coletor recorta, ele não grava de qual frame o recorte saiu nem em
-- que posição: `training_frames` não tem parent_frame_id, crop_box nem offset
-- (conferido em information_schema.columns no DEV), e a r2_key não desempata —
-- recorte e frame cheio moram no MESMO prefixo com nome UUID aleatório
-- (training-images/<tenant>/nvr/<recorder>/<uuid>.jpg).
-- Resultado: os 5.259 recortes anotados do RVB são irreprojetáveis. O passado
-- está perdido; esta migration existe para que a PRÓXIMA safra não nasça igual.
--
-- POR QUE UMA COLUNA jsonb E NÃO parent_frame_id + 6 colunas
-- Porque o frame cheio NÃO EXISTE, e uma FK para uma linha inexistente seria
-- uma coluna eternamente NULL fingindo ser um vínculo. Lendo o código:
--   * collector_loop._payload_para_upload devolve o recorte OU o frame inteiro,
--     nunca os dois (linhas 170-193): com pessoa detectada sobe só o recorte —
--     é o ganho inteiro do desfecho C (10 KB com cabeça de ~40px contra 157 KB
--     com ~17px). O frame cheio é transitório: não vira linha nem objeto no R2.
--   * replay_miner._gate_and_crop descarta o frame quando não há recorte —
--     o quadro cheio nunca chega a subir.
-- Logo não há parent_frame_id a apontar, nem r2_key do original a guardar.
-- O que EXISTE no instante do recorte, e hoje é jogado fora, é a GEOMETRIA:
-- a caixa recortada em pixels do frame original e o tamanho desse frame. Com
-- os dois, uma anotação feita no recorte volta para as coordenadas do original
-- (app/domain/services/crop_origin.py::reproject_annotation) — que é
-- exatamente o que faltava para treinar em frame cheio com dado de recorte.
--
-- FORMATO
--   {"box": [x, y, w, h], "source_size": [W, H]}
--   box .......... retângulo EFETIVAMENTE recortado (já com a margem de
--                  crop_person, já aparado na borda), em px do frame original
--   source_size .. dimensões do frame original de onde o recorte saiu
-- Espelha o padrão jsonb já usado nesta mesma tabela (quality_scores,
-- pre_annotations) e na 131 (split_membership) — não inaugura convenção.
--
-- NULL É O VALOR CERTO PARA:
--   * todo o acervo atual (o vínculo não existe mesmo — não se inventa backfill
--     para dado que ninguém gravou);
--   * frame cheio subido de propósito, que é o fallback do coletor quando o
--     detector está desligado/indeterminado ou o recorte falha
--     (collector_loop.py:170-193). Não tem recorte, não tem vínculo: NULL.
--   * upload manual, extração de vídeo, qualquer origem que não seja recorte.
-- Ou seja: `crop_origin IS NOT NULL` passa a ser a prova, por construção, de
-- que a linha é um recorte — ao contrário da heurística por repetição de
-- dimensão em frame_repository.list_images_filtered (only_crops), que
-- continua no lugar porque só ela cobre o acervo legado.
--
-- Forward-only e idempotente (ADD COLUMN IF NOT EXISTS). Em produção o runner é
-- railway_start.py e ele RE-RODA toda migration a cada boot: rodar 2x é o caso
-- normal, não a exceção.

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS crop_origin JSONB;

COMMENT ON COLUMN public.training_frames.crop_origin IS
    'Vínculo do recorte com o frame de origem: {"box":[x,y,w,h],"source_size":[W,H]} '
    'em pixels do frame ORIGINAL. NULL = não é recorte (frame cheio/upload/vídeo) '
    'ou é anterior à migration 132, quando o vínculo não era gravado.';
