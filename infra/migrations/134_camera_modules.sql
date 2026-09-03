-- 134_camera_modules.sql
-- O VÍNCULO CÂMERA↔MÓDULO — que hoje NÃO EXISTE.
--
-- O QUE EXISTE HOJE (medido no DEV, 2026-09-02, tenant RVB
-- 63c219d8-fbef-4f3c-a7c9-058c742482e2)
--   public.cameras tem DUAS colunas de módulo, ambas VARCHAR única (1:1):
--     SELECT module_code, active_module, count(*) FROM public.cameras
--      WHERE tenant_id = '63c219d8-...' GROUP BY 1,2;
--       →  epi | epi | 29      (UMA linha: as 29 câmeras do tenant)
--   E as duas nascem com o mesmo padrão:
--     SELECT column_name, column_default FROM information_schema.columns
--      WHERE table_schema='public' AND table_name='cameras'
--        AND column_name IN ('active_module','module_code');
--       →  active_module | 'epi'::character varying
--       →  module_code   | 'epi'::character varying
-- Ou seja: as 29 câmeras da RVB estão em 'epi' porque 'epi' é o DEFAULT DA
-- COLUNA (migration 026 o instituiu), não porque alguém declarou que elas
-- servem ao EPI. "Qualidade 06", "Estacionamento Motos" e "Guarita" carregam
-- exatamente a mesma marca que a câmera de segurança do trabalho. O vínculo
-- nunca foi declarado por ninguém — é um valor padrão passando por decisão.
--
-- O QUE ISSO CUSTOU (medido, mesmo tenant, module_code='epi')
--   SELECT c.name, count(*) frames, count(*) FILTER (WHERE tf.is_annotated) anot
--     FROM public.training_frames tf JOIN public.cameras c ON c.id = tf.camera_id
--    WHERE tf.tenant_id='63c219d8-...' AND tf.module_code='epi' GROUP BY 1;
--     Qualidade 06 ......... 1035 / 579 anotados
--     Qualidade 05 ......... 1000 / 598
--     Qualidade 01 EPI .....   78 /  52
--     Qualidade 04 .........   79 /  55
--     Qualidade 02 .........   65 /  49
--     Qualidade 03 .........   50 /  41
--     Estacionamento/Guarita  300 /   0   (6 câmeras × 50)
--
-- ⚠️ NENHUMA dessas linhas é declarada erro por esta migration. Uma câmera PODE
-- legitimamente servir EPI e Qualidade ao mesmo tempo — uma delas se chama
-- literalmente "Qualidade 01 EPI", o caso de uso escrito no nome. É por isso
-- que o vínculo é N:N e não mais uma coluna: espremer isso em `active_module`
-- obrigaria a escolher UM módulo e perder o outro. Quem decide é o DONO, pela
-- UI. Esta migration cria só o ESTADO.
--
-- POR QUE NÃO REAPROVEITAR `active_module`
-- Ela responde outra pergunta: "qual módulo INFERE agora?" — eixo temporal,
-- resolvido em runtime junto com `schedule_rules`
-- (camera_module_service.resolve_active_module). Uma câmera infere um módulo
-- por vez; ela SERVE vários. Eixos ortogonais; `active_module` fica intocada.
--
-- ⚠️ ESTA MIGRATION NÃO FAZ BACKFILL — DE PROPÓSITO
-- Seria de uma linha copiar `active_module` para cá. Duas razões para não:
--   1. Copiar o default não cria dado: reescreveria "ninguém decidiu" como
--      "todas são EPI", e apagaria justamente a pergunta que o dono precisa
--      responder. Chutar por nome ("Qualidade 06" → quality) seria pior:
--      adivinharia errado exatamente na câmera que ele quer em DOIS módulos.
--   2. Em produção o runner é railway_start.py e ele RE-RODA toda migration a
--      cada boot. Um backfill com ON CONFLICT DO NOTHING não protegeria: o
--      dono desmarca a Guarita do EPI hoje, e o próximo deploy a marcaria de
--      novo. Migration que ressuscita escolha desfeita é pior que migration
--      nenhuma.
-- Por isso a tabela nasce VAZIA e as 29 câmeras nascem "SEM MÓDULO", que é a
-- verdade. Medido depois de aplicar esta migration no DEV:
--     SELECT count(*) FROM public.camera_modules;                      → 0
--     29 câmeras da RVB | 29 sem nenhum vínculo declarado
-- ⚠️ CONSEQUÊNCIA PARA QUEM CONSOME: tabela vazia significa que TODO tenant
-- fica com escopo não-declarado no segundo do deploy. Um filtro que leia isto
-- como "nenhuma câmera" zeraria galeria, dashboard e coleta de todos os
-- tenants sem uma linha mudar de valor. O predicado único
-- (camera_module_repository.escopo_sql) trata escopo não-declarado como "vale
-- tudo", e é ele que todo consumidor importa.
--
-- ONDE A TABELA VIVE (ADR-0004/0016) — ESCOLHA MEDIDA, NÃO DEDUZIDA
-- Esta casa tem os dois padrões coexistindo, e as duas tabelas de câmera
-- existem de fato. O que decide é o dado:
--     SELECT count(*) FROM rvb.cameras;     →      0
--     SELECT count(*) FROM public.cameras;  →     29   (todas com tenant_id RVB)
--     SELECT count(*) AS frames, count(pc.id) AS casam,
--            count(*) FILTER (WHERE pc.id IS NULL) AS orfaos
--       FROM public.training_frames tf
--       LEFT JOIN public.cameras pc ON pc.id = tf.camera_id
--      WHERE tf.tenant_id='63c219d8-...' AND tf.module_code='epi';
--       → 12854 frames | 12854 casam | 0 órfãos
-- `rvb.cameras` existe e está VAZIA. A câmera real do produto vive em
-- `public.cameras` com `tenant_id`, e é o id dela que os 12.854 quadros de EPI
-- referenciam. O outro lado do vínculo também é public: não existe tabela
-- `modules` — o módulo é um CÓDIGO, e as tabelas que o carregam
-- (`public.tenant_modules`, `public.module_classes`) são públicas. Pendurar o
-- vínculo em `{tenant_schema}` obrigaria a FK a cruzar schema ou a apontar
-- para a tabela vazia — a tela ficaria apontando para câmeras que não são as
-- do dado. Fica em public com `tenant_id NOT NULL`, do lado dos dois fatos que
-- ele liga.
--
-- TENANT PINADO NA FK, NÃO SÓ NA COLUNA
-- `tenant_id` aqui não é enfeite de filtro: a FK é COMPOSTA
-- (camera_id, tenant_id) → cameras(id, tenant_id). Com FKs separadas o banco
-- aceitaria uma linha dizendo que a câmera do tenant A serve um módulo do
-- tenant B, e o isolamento dependeria só de a aplicação nunca errar. O índice
-- único que a FK exige — cameras(id, tenant_id) — não pode falhar na criação:
-- `id` já é PRIMARY KEY de cameras, então o par é único por construção.
--
-- POR QUE NÃO HÁ FK (NEM CHECK) PARA O CÓDIGO DO MÓDULO
-- Seria a trava óbvia — só vincular a módulo habilitado — e ela travaria o
-- caso de uso. Medido: as duas fontes de habilitação DISCORDAM para o RVB —
--     public.tenant_modules          → ['epi']                       (1 linha)
--     public.tenants.modules_enabled → ['epi','counting','basic','analytics']
-- e NENHUMA das duas lista 'quality', embora o tenant tenha 6 câmeras
-- "Qualidade NN". Uma FK escolheria uma das duas fontes discordantes e
-- deixaria o dono sem conseguir tirar as câmeras de Qualidade do pool de EPI —
-- o pedido que originou esta migration. Um CHECK de lista fechada duplicaria a
-- regra em dois lugares e travaria módulo novo no BOOT em vez de no request. O
-- gate por tenant fica na API (_is_module_allowed, fail-closed); reconciliar
-- as duas fontes é decisão de produto, não de DDL.
--
-- POR QUE `enabled` EM VEZ DE APAGAR A LINHA
-- Desmarcar um módulo vira UPDATE enabled=false, nunca DELETE. Assim quem
-- marcou e quando sobrevive ao desmarque, e re-marcar é upsert — o mesmo
-- desenho de public.tenant_modules, que já vive nesta casa. Nenhum caminho
-- desta tabela apaga linha. Em troca, TODO leitor precisa de `enabled = true`:
-- linha desmarcada não é vínculo nem conta como escopo declarado.
--
-- Forward-only e idempotente: CREATE TABLE / CREATE INDEX IF NOT EXISTS,
-- constraint em DO $$ com duplicate_object/duplicate_table, zero DML. Em
-- produção o runner é railway_start.py e ele RE-RODA toda migration a cada
-- boot: rodar 2× é o caso normal, não a exceção.

CREATE TABLE IF NOT EXISTS public.camera_modules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id),
    camera_id UUID NOT NULL REFERENCES public.cameras(id) ON DELETE CASCADE,

    -- Mesmo vocabulário de public.tenant_modules e de cameras.active_module:
    -- 'epi' | 'quality' | 'counting' | 'basic' | 'analytics'.
    module_code VARCHAR(50) NOT NULL,

    -- false = o dono DESMARCOU. A linha fica, com o histórico de quem marcou.
    enabled BOOLEAN NOT NULL DEFAULT true,

    -- ON DELETE SET NULL, não a FK nua: `assigned_by` é PROVENIÊNCIA, e
    -- proveniência não pode virar tranca. Sem isso, apagar um usuário que
    -- um dia declarou um vínculo passa a falhar com ForeignKeyViolation —
    -- reproduzido no teste de integração deste PR, no teardown. O vínculo
    -- continua valendo mesmo quando quem o declarou saiu da empresa.
    assigned_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Um par câmera+módulo tem UMA linha — é o que faz o upsert (ON CONFLICT)
-- do desmarcar/re-marcar funcionar sem duplicar histórico.
CREATE UNIQUE INDEX IF NOT EXISTS ux_camera_modules_camera_module
    ON public.camera_modules(camera_id, module_code);

-- Índice único que a FK composta abaixo exige. Não pode falhar na criação:
-- `id` já é PRIMARY KEY de cameras, então (id, tenant_id) é único por construção.
CREATE UNIQUE INDEX IF NOT EXISTS uq_cameras_id_tenant
    ON public.cameras (id, tenant_id);

-- A tranca de tenant no BANCO, abaixo da aplicação: impede uma linha que diga
-- que a câmera do tenant A pertence ao tenant B.
DO $$ BEGIN
    ALTER TABLE public.camera_modules
        ADD CONSTRAINT camera_modules_camera_tenant_fkey
        FOREIGN KEY (camera_id, tenant_id)
        REFERENCES public.cameras (id, tenant_id)
        ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object OR duplicate_table THEN NULL;
END $$;

-- "quais câmeras servem ao módulo X neste tenant" — a pergunta que a coleta
-- e o dashboard fazem quando passam a respeitar o vínculo.
CREATE INDEX IF NOT EXISTS idx_camera_modules_tenant_module
    ON public.camera_modules(tenant_id, module_code)
    WHERE enabled;

COMMENT ON TABLE public.camera_modules IS
    'Vínculo N:N câmera↔módulo, declarado pelo dono na tela de atribuição. '
    'Nasce vazia: ausência de linha = módulo nunca declarado para a câmera '
    '(NÃO é o mesmo que cameras.active_module, que é default de coluna). '
    'enabled=false = desmarcado pelo dono — a linha nunca é apagada.';
COMMENT ON COLUMN public.camera_modules.assigned_by IS
    'Usuário que declarou o vínculo. Toda linha aqui é decisão humana — a '
    'migration não backfilla nenhuma.';
