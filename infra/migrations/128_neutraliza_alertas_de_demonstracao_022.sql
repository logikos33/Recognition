-- Migration 128 — neutraliza os alertas de demonstração da migration 022 (#545)
--
-- ═══ O PROBLEMA ═══
--
-- `022_demo_mock_alerts.sql` insere 13 alertas falsos (no_helmet, no_vest,
-- no_glasses, no_gloves) com:
--
--   · tenant_id fixo em '00000000-0000-0000-0000-000000000001' — o UUID zerado
--     que a constitution proíbe como default de tenant;
--   · camera_id vindo de `SELECT id FROM cameras LIMIT 1` — QUALQUER câmera,
--     de QUALQUER tenant.
--
-- Medido no DEV em 2026-08-25: o tenant "Default" existe (a FK passa) e há 29
-- câmeras, ~28 delas do RVB. Ou seja: alerta falso plantado numa câmera de
-- cliente. Junto com a leitura sem escopo de tenant que a #545 fechou
-- (`SELECT * FROM alerts WHERE camera_id = %s`), esses 13 apareceriam DENTRO da
-- visão do RVB.
--
-- E a 022 re-executa: em modo LEGADO (produção hoje) o runner re-roda todas as
-- migrations a cada boot. Ela só pula se já existirem alertas de demonstração,
-- ou se não houver câmera nenhuma.
--
-- ═══ POR QUE ESTE DESENHO, E NÃO UMA SENTINELA INSERIDA ═══
--
-- A saída óbvia seria INSERT de uma linha-sentinela com o mesmo prefixo de
-- `evidence_key`, para a guarda da própria 022 pular para sempre. Não dá, e a
-- razão é do schema: `alerts.camera_id` é NOT NULL **e tem FK para cameras.id**
-- (alerts_camera_id_fkey). Não existe UUID sintético que passe — qualquer
-- sentinela apontaria para uma câmera real, que é exatamente o que se quer
-- evitar. Criar uma câmera-lápide seria pior: câmera fantasma na lista do
-- cliente.
--
-- A saída é que as PRÓPRIAS linhas da 022, depois de neutralizadas, servem de
-- guarda. Zero INSERT, zero DELETE, zero câmera nova.
--
-- Ordem importa e joga a favor: as migrations rodam em ordem numérica no MESMO
-- passe. Se a 022 inserir neste boot, a 128 neutraliza logo em seguida, antes
-- de a API atender requisição. Se já tiver inserido em boot anterior, a 128
-- neutraliza agora. Nos dois casos as linhas passam a existir apenas para
-- fazer a 022 pular.
--
-- ═══ O QUE "NEUTRALIZAR" SIGNIFICA AQUI ═══
--
--   tenant_id = NULL   → invisível a TODA consulta de alerta. Conferido: as
--                        cláusulas `tenant_id IS NULL` do repositório existem
--                        só em annotation_repository; alert_repository nunca
--                        aceita NULL, então `WHERE tenant_id = %s` não casa.
--   violations = '[]'  → mesmo que alguma consulta futura esqueça o filtro de
--                        tenant (foi exatamente o que aconteceu na #545), não
--                        há violação nenhuma para renderizar.
--   acknowledged = TRUE→ não conta como pendência em lugar nenhum.
--   verification_*     → registra o que são, para quem for ler o banco depois.
--
-- `evidence_key` fica INTACTA de propósito: é ela que a guarda da 022 procura
-- (`LIKE 'frames/d97cb03e%'`) e é ela que identifica a procedência da linha.
--
-- ═══ ISTO NÃO SUBSTITUI O CUTOVER ═══
--
-- Esta migration trata UM caso. A classe inteira de re-execução no boot morre
-- ligando `MIGRATIONS_LEDGER_CUTOVER=1` em produção, o que está registrado como
-- item da promoção develop→staging. Enquanto o cutover não acontece, esta
-- migration é o cinto.
--
-- Forward-only: UPDATE apenas. Idempotente por construção — rodar duas vezes
-- produz exatamente o mesmo estado (a segunda passada não encontra linha com
-- tenant_id preenchido).

UPDATE public.alerts
   SET tenant_id           = NULL,
       violations          = '[]'::jsonb,
       acknowledged        = TRUE,
       verification_status = 'human_rejected',
       verification_verdict = 'reject',
       verification_reason = 'Alerta de demonstração da migration 022, '
                             || 'neutralizado pela 128 (#545): tenant_id fixo no '
                             || 'UUID zerado e camera_id de uma câmera arbitrária.'
 WHERE evidence_key LIKE 'frames/d97cb03e%'
   AND (tenant_id IS NOT NULL OR violations <> '[]'::jsonb);
