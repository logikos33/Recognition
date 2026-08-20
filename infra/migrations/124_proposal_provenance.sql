-- 124 · Proveniência por LOTE nas propostas do modelo.
--
-- Por que: proposta de modelo é descartável por construção — um propositor
-- ruim, um pós-processamento errado, um limiar mal escolhido, e tudo que ele
-- escreveu precisa sair. Sem etiqueta, "sair" vira DELETE por data ou por
-- source='ai' inteiro, que leva junto o que era bom.
--
-- O precedente é caro: em 18/08 o produto servia o modelo com os tensores
-- trocados (#470). Toda proposta daquele período era lixo por construção — e
-- só não deu trabalho porque o banco tinha ZERO propostas. Da próxima vez terá.
--
-- Com `proposal_batch_id`, descartar é cirúrgico:
--   UPDATE frame_annotations SET source = 'ai_descartada'
--    WHERE proposal_batch_id = '<lote>';
-- (⛔ NUNCA DELETE — a trava da casa vale aqui também.)
--
-- `proposal_model_id` responde "qual modelo propôs isto?" sem depender de
-- juntar por janela de tempo, e `proposal_confidence` guarda o score que
-- passou pelo limiar — é o que permite, depois, medir aceitação POR FAIXA de
-- confiança e escolher o limiar da fase C com dado em vez de palpite.
--
-- Colunas anuláveis: toda anotação humana existente fica com NULL nas três,
-- que é exatamente a leitura correta — humano não tem lote de proposta.

ALTER TABLE public.frame_annotations
    ADD COLUMN IF NOT EXISTS proposal_batch_id uuid;

ALTER TABLE public.frame_annotations
    ADD COLUMN IF NOT EXISTS proposal_model_id uuid;

ALTER TABLE public.frame_annotations
    ADD COLUMN IF NOT EXISTS proposal_confidence double precision;

-- Índice parcial: só linhas de proposta. A tabela é dominada por anotação
-- humana (2.656 contra 0 propostas hoje), e indexar a coluna inteira gastaria
-- espaço com NULLs que ninguém consulta.
CREATE INDEX IF NOT EXISTS idx_frame_annotations_proposal_batch
    ON public.frame_annotations (proposal_batch_id)
    WHERE proposal_batch_id IS NOT NULL;
