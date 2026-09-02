-- 133_training_frames_dataset_role.sql
-- O EMPREGO do quadro — e a trava que impede o gabarito de virar treino.
--
-- O PROBLEMA (medido)
-- O A/B das três variantes de detector saiu NÃO CONCLUSIVO por falta de prova:
-- o holdout do RVB tem ZERO caixas de `Sem Luvas` e `Sem mascara` — as duas
-- classes de ausência que sustentam a régua de campo. A correção é humana
-- (440 quadros cheios colhidos do gravador, ~150 anotados à mão como
-- GABARITO), mas ela só vale enquanto o gabarito NUNCA entrar no treino: um
-- modelo treinado no próprio exame decora a prova, e toda medição posterior
-- passa a mentir para cima sem que nada acuse.
-- Hoje NADA impede esse vazamento. `_snapshot_labeled_frames`
-- (versioning_v2.py) varre `training_frames` por tenant+módulo+is_annotated e
-- leva TUDO que estiver anotado — o gabarito, assim que for anotado, entra no
-- próximo export automaticamente. A regra existia só como combinado verbal.
--
-- A REGRA (dono do produto): "um quadro só tem UM emprego para sempre —
-- gabarito mede, proposta alimenta". Trava no sistema, não em memória.
--
-- POR QUE UMA COLUNA DE PAPEL, E NÃO REAPROVEITAR curation_status
-- `curation_status` (migration 110) responde outra pergunta: "este quadro
-- presta?" (active/duvida/excluida). Um gabarito é 'active' — ele presta, e
-- muito; o que muda é o EMPREGO dele. Empilhar um valor 'gabarito' ali
-- tornaria os dois eixos mutuamente excludentes: um gabarito nunca mais
-- poderia ser marcado como dúvida na curadoria, e todo filtro de galeria
-- (frame_repository.list_images_filtered, que esconde 'excluida' por padrão)
-- passaria a decidir visibilidade a partir de um fato que não é de curadoria.
-- São dois eixos ortogonais; ficam em duas colunas.
--
-- POR QUE VARCHAR+CHECK E NÃO BOOLEAN `holdout_only`
-- Porque o domínio é MUTUAMENTE EXCLUDENTE por definição ("UM emprego"), e é
-- exatamente isso que uma coluna de estado expressa e dois booleanos não:
-- com `holdout_only` + um futuro `calibracao_only`, o estado (true, true)
-- existe no banco e não significa nada. Além disso o valor sai auto-explicado
-- em log e em `SELECT` ('holdout') em vez de `t`. Mesmo formato do vizinho
-- `curation_status` — VARCHAR(20) NOT NULL DEFAULT + CHECK em DO $$ —, não
-- inaugura convenção.
--
-- VALORES
--   'pool'    (DEFAULT) alimenta treino — é o emprego de TODO frame que já
--             existe hoje, então a coluna nasce sem mudar comportamento algum.
--   'holdout' mede modelo, NUNCA treina. É o gabarito.
-- A trava do export é ALLOWLIST (`dataset_role = 'pool'`), não denylist
-- (`<> 'holdout'`): se um papel novo aparecer amanhã, ele fica FORA do treino
-- até alguém decidir o contrário. Errar para o lado de treinar de menos custa
-- dado; errar para o lado de treinar de mais custa a régua inteira.
--
-- dataset_role_set_at: QUANDO o quadro virou gabarito. Não é enfeite de
-- auditoria — é o que separa "esta medição é limpa" de "este quadro já estava
-- no treino do v11 quando foi promovido a juiz". Sem a data, um gabarito
-- marcado tarde é indistinguível de um que nunca treinou.
--
-- Índice PARCIAL: o gabarito é ~150 linhas contra ~60 mil do tenant. O export
-- varre o pool inteiro de qualquer jeito (nenhum índice ajuda `= 'pool'` em
-- 99,7% da tabela); quem precisa de índice é o lado pequeno — listar/contar o
-- que foi retido. `WHERE dataset_role <> 'pool'` indexa só esse punhado.
--
-- Forward-only e idempotente (ADD COLUMN IF NOT EXISTS, CHECK em DO $$ com
-- duplicate_object, CREATE INDEX IF NOT EXISTS). Em produção o runner é
-- railway_start.py e ele RE-RODA toda migration a cada boot: rodar 2x é o caso
-- normal, não a exceção.

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS dataset_role VARCHAR(20) NOT NULL DEFAULT 'pool';

ALTER TABLE public.training_frames
    ADD COLUMN IF NOT EXISTS dataset_role_set_at TIMESTAMP;

DO $$
BEGIN
    ALTER TABLE public.training_frames
        ADD CONSTRAINT chk_training_frames_dataset_role
        CHECK (dataset_role IN ('pool', 'holdout'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_training_frames_dataset_role_holdout
    ON public.training_frames(tenant_id)
    WHERE dataset_role <> 'pool';

COMMENT ON COLUMN public.training_frames.dataset_role IS
    'Emprego permanente do quadro: pool = alimenta treino (padrão); holdout = '
    'gabarito, mede modelo e NUNCA entra em export de treino (trava em '
    'versioning_v2._snapshot_labeled_frames/_fetch_annotations). Ortogonal a '
    'curation_status.';

COMMENT ON COLUMN public.training_frames.dataset_role_set_at IS
    'Quando o quadro recebeu o papel atual. NULL = nunca saiu do padrão pool.';
