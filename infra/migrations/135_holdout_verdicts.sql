-- 135_holdout_verdicts.sql
-- O VEREDITO DO GABARITO — a resposta por IMAGEM que a régua do A/B consome.
--
-- O PROBLEMA
-- `scripts/ops/ab_ausencia.py` compara as três variantes de detector no nível
-- da DECISÃO: "por imagem e por classe de ausência, o modelo ACUSOU ou não, e
-- o gabarito diz se aquela ausência era real". O gabarito, portanto, é uma
-- resposta POR IMAGEM+CLASSE — não uma caixa. Hoje ele não tem onde morar: a
-- migration 133 criou a TRAVA (`dataset_role='holdout'`, o quadro nunca
-- treina) mas não o lugar da RESPOSTA.
--
-- POR QUE NÃO GRAVAR EM `frame_annotations`
-- Três motivos, e o terceiro é o que decide:
--
--   1. FORMA. `frame_annotations` é geometria (x, y, width, height, class_id).
--      Um veredito não tem geometria. Gravá-lo ali exige INVENTAR uma caixa —
--      e caixa inventada em quadro 1920x1080 é exatamente o dado falso que
--      este gabarito existe para não produzir.
--
--   2. DOMÍNIO. O gabarito precisa de TRÊS estados (sim / não / não sei). O
--      "não sei" é obrigatório: forçar binário faz o avaliador chutar, e um
--      gabarito com chute mede o chute, não o modelo. `frame_annotations` não
--      tem como dizer "não sei" — a ausência de linha já significa outra
--      coisa (não anotado).
--
--   3. DESTINO (o que decide). `frame_annotations` É o pool de treino.
--      `versioning_v2._fetch_annotations` e `auto_training` leem DELA. A trava
--      da 133 (`tf.dataset_role = 'pool'`) manteria o veredito fora do export
--      HOJE — mas por FILTRO, e um filtro protege enquanto o papel do quadro
--      estiver certo. `annotation_repository.get_coverage_matrix` também lê
--      `frame_annotations`, e a matriz de cobertura passaria a contar
--      vereditos como se fossem caixas anotadas.
--      Em tabela própria o veredito não é filtrado para fora do treino: ele é
--      INCAPAZ de entrar, porque nenhuma query de export conhece esta tabela.
--      Estrutura, não vigilância.
--
-- POR QUE `public.*` COM `tenant_id` (e não `{tenant_schema}`)
-- ADR-0016/CLAUDE.md: a tabela pendura em `public.training_frames`, que é
-- `public` com `tenant_id`. Vizinha da sua FK, mesmo padrão da vizinha.
-- O `tenant_id` nunca diverge do quadro porque o único caminho de escrita
-- (GabaritoRepository.upsert_verdicts) resolve o tenant a partir do PRÓPRIO
-- frame, já escopado pelo JWT — id de outro tenant não casa e vira 404 (C-01).
--
-- IDEMPOTÊNCIA DA RESPOSTA — `UNIQUE (frame_id, class_id)`
-- Reabrir a mesma imagem e mudar de ideia SOBRESCREVE. Sem a unique, duas
-- respostas contraditórias coexistiriam e o A/B leria a que o `ORDER BY`
-- sorteasse. `ON CONFLICT DO UPDATE` no repositório fecha o caminho.
--
-- `reason` — O ATALHO DE UM TOQUE, REGISTRADO
-- Muito quadro do gravador não tem ninguém enquadrado. Semanticamente isso já
-- é resposta completa: sem pessoa, NENHUMA ausência é real, logo 'nao' para
-- todas as classes — e é o negativo que o A/B mais precisa (modelo que acusa
-- "sem luvas" em corredor vazio está produzindo falso positivo, e o gabarito
-- tem de contar isso contra ele). Mas "respondi não porque a pessoa usava
-- luva" e "respondi não porque não havia pessoa" são fatos diferentes na hora
-- de auditar a prova: um gabarito de 138 corredores vazios não mede nada.
-- `reason='sem_pessoa'` guarda essa diferença numa coluna, sem inventar um
-- quarto valor de veredito que todo consumidor teria de traduzir.
--
-- `judged_by` / `judged_at`: quem julgou e quando. Não é enfeite — gabarito é
-- prova, e prova sem procedência não sustenta ranking de modelo.
--
-- Forward-only e idempotente (CREATE TABLE/INDEX IF NOT EXISTS). Em produção o
-- runner é railway_start.py e RE-RODA toda migration a cada boot: rodar 2x é o
-- caso normal, não a exceção.

CREATE TABLE IF NOT EXISTS public.holdout_verdicts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    frame_id    UUID NOT NULL REFERENCES public.training_frames(id) ON DELETE CASCADE,
    tenant_id   UUID NOT NULL,
    class_id    INTEGER NOT NULL,
    verdict     VARCHAR(8) NOT NULL,
    reason      VARCHAR(16),
    judged_by   UUID,
    judged_at   TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_holdout_verdicts_frame_class UNIQUE (frame_id, class_id)
);

DO $$
BEGIN
    ALTER TABLE public.holdout_verdicts
        ADD CONSTRAINT chk_holdout_verdicts_verdict
        CHECK (verdict IN ('sim', 'nao', 'nao_sei'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE public.holdout_verdicts
        ADD CONSTRAINT chk_holdout_verdicts_reason
        CHECK (reason IS NULL OR reason IN ('sem_pessoa'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- A leitura real é sempre "os vereditos deste tenant" (montar a fila) e
-- "os vereditos deste quadro" (reabrir a imagem). A unique já cobre o
-- segundo; este índice cobre o primeiro.
CREATE INDEX IF NOT EXISTS idx_holdout_verdicts_tenant
    ON public.holdout_verdicts(tenant_id);

COMMENT ON TABLE public.holdout_verdicts IS
    'Gabarito do A/B de ausência: a resposta POR IMAGEM+CLASSE ("esta ausência '
    'era real?") que ab_ausencia.py consome. NÃO é anotação de treino e NÃO '
    'tem geometria — vive fora de frame_annotations de propósito, para ser '
    'incapaz (não apenas filtrado) de entrar em export de treino. Ver 133.';

COMMENT ON COLUMN public.holdout_verdicts.verdict IS
    'sim | nao | nao_sei. O "nao_sei" é obrigatório no domínio: forçar binário '
    'faz o avaliador chutar, e gabarito com chute mede o chute.';

COMMENT ON COLUMN public.holdout_verdicts.reason IS
    'sem_pessoa = a resposta saiu do atalho "não há pessoa" (que responde '
    'nao para todas as classes de uma vez). NULL = julgada classe a classe.';
