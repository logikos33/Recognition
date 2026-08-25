-- Migration 129 — neutraliza as regras de alerta semeadas da 006
--
-- ═══ O QUE FOI MEDIDO ═══
--
-- `public.alert_rules` tem 3.270 linhas no DEV. Anatomia, em 2026-08-25:
--
--   violation_type   n      com min_occurrences   com camera_id   habilitadas
--   no_helmet        1635   0                     0               1635
--   no_vest          1635   0                     0               1635
--
-- **100% é a taxonomia de demonstração da era COCO.** Zero regras criadas por
-- usuário: nenhuma tem `camera_id`, nenhuma tem `min_occurrences`, e não existe
-- um único `violation_type` fora do enum COCO. Nenhuma casa com classe que
-- algum modelo real emita (no RVB as classes de ausência começam com "Sem ").
--
-- ═══ POR QUE SÃO 3.270 E NÃO 10 ═══
--
-- A 006 faz `INSERT ... SELECT id, 'no_helmet' FROM tenants ON CONFLICT DO
-- NOTHING`, mas **não existe constraint única** em (tenant_id,
-- violation_type) — então `ON CONFLICT` nunca dispara. Cada boot em modo
-- LEGADO reinsere 5 tenants × 2 classes = 10 linhas.
--
-- Os `created_at` confirmam: lotes de exatamente 10 por segundo, de 2026-07-01
-- a 2026-08-02. 3.270 / 10 = 327 boots.
--
-- E a data mais nova ser 02/08 diz o resto: **o crescimento já parou no DEV**,
-- quando `MIGRATIONS_LEDGER_CUTOVER=1` entrou e a 006 deixou de re-rodar. Em
-- PRODUÇÃO, que segue em modo legado, ele continua — 10 linhas por boot.
--
-- ═══ O QUE ESTA MIGRATION FAZ, E O QUE NÃO FAZ ═══
--
-- FAZ: desabilita as linhas semeadas. Elas somem das telas de regra e de
-- cenário, que hoje mostram 3.270 regras que não fazem nada.
--
-- NÃO FAZ: parar o crescimento. Isso exigiria uma constraint única, que não
-- pode ser criada sobre dados já duplicados sem DELETE — e DELETE é proibido.
-- Quem mata a classe inteira é o cutover do ledger, o mesmo item de promoção
-- que a 128 registrou.
--
-- ⛔ SEM DELETE. As linhas continuam existindo e auditáveis.
--
-- ═══ POR QUE É SEGURO ═══
--
-- Conferido consumidor por consumidor antes de escrever:
--
--   · `_regras_de_persistencia` (tasks/inference.py) — o único leitor no
--     caminho SERVIDO. Filtra `min_occurrences IS NOT NULL AND > 1`, e
--     NENHUMA das 3.270 tem `min_occurrences`. Lê zero delas hoje, lê zero
--     depois. Comportamento idêntico.
--   · `rules/routes.py` — CRUD de exibição/gestão. Passa a mostrar
--     desabilitadas, que é o ponto.
--   · `scenarios/routes.py` via `list_for_camera_scenario` — exibição.
--
-- Escopo cirúrgico: só o que casa com a assinatura EXATA da semente. Regra com
-- `camera_id`, com `min_occurrences`, ou com `violation_type` fora do enum de
-- demonstração fica INTACTA — se alguém criar uma de verdade amanhã, ela não é
-- tocada por uma re-execução desta migration.
--
-- Idempotente: a segunda passada não encontra linha habilitada que case.

UPDATE public.alert_rules
   SET enabled = FALSE,
       updated_at = NOW()
 WHERE enabled IS TRUE
   AND camera_id IS NULL
   AND min_occurrences IS NULL
   AND time_window_seconds IS NULL
   AND violation_type IN (
        'no_helmet', 'no_vest', 'no_gloves', 'no_glasses', 'no_safety_glasses',
        'helmet', 'vest', 'gloves', 'glasses', 'safety_glasses'
   );
