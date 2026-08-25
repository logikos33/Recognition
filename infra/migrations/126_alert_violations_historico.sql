-- 126 · Ledger de correção de caixa nos alertas. Append-only, nada some.
--
-- Por que coluna e não tabela: o valor anterior só é lido no contexto do
-- próprio alerta (a tela de detalhe). Uma tabela `alert_bbox_corrections`
-- traria FK, repository, índice e JOIN para responder a pergunta que um
-- `violations_historico[-1]` já responde.
--
-- Formato de cada entrada (append no fim, nunca sobrescrito):
--   {"em": "<ts>", "por": "<user_id>", "tipo": "bbox",
--    "violations_anteriores": [ <array violations INTEIRO de antes> ]}
--
-- `violations_anteriores` guarda o ARRAY todo, não só a caixa: reconstruir
-- qualquer estado passado é ler uma entrada, não replayar um diff.
-- O campo `tipo` existe para que um futuro registro de veredito caiba aqui
-- sem nova migration.
--
-- NUNCA DELETE (trava da casa). Descartar uma correção ruim = novo append
-- com o valor anterior, não remoção da entrada.
--
-- Sem índice: a coluna só é lida junto com a linha do alerta (por id).
-- ponytail: cresce sem teto por alerta. Com 334 alertas e correção manual é
-- ruído; se virar milhares de correções por alerta, migrar para tabela.
--
-- Idempotência: ADD COLUMN IF NOT EXISTS. Rodar 2× não produz erro nem muda
-- dado (railway_start.py re-roda toda migration a cada boot).

ALTER TABLE public.alerts
    ADD COLUMN IF NOT EXISTS violations_historico JSONB NOT NULL DEFAULT '[]'::jsonb;
