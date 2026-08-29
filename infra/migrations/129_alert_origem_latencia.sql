-- 129_alert_origem_latencia.sql
-- Procedência do alerta: de qual fonte o evento nasceu e quanto tempo levou.
--
-- Por que: o dashboard vai passar a mostrar violação vinda do HLS AO VIVO que
-- o edge empurra, ao lado da que veio de coleta retroativa. Sem uma coluna, a
-- tela não tem como dizer a verdade sobre o que está olhando — e "badge com
-- verdade" foi requisito explícito, não enfeite.
--
-- ⛔ SEM DEFAULT e SEM BACKFILL, de propósito. Alerta antigo fica NULL, que
-- se lê como "não declarado". Carimbar retroativamente uma origem que ninguém
-- mediu é o mesmo erro do #544 (a polaridade vinha de env com nomes COCO e
-- `has_violation` era sempre falso, com cara de turno limpo).
--
-- `latencia_ms` é MEDIDA: idade do segmento (derivada do TTL da chave no
-- Redis, resolução ~1s) + o tempo gasto no laço até persistir. NULL quando
-- não foi medida — nunca estimada.

ALTER TABLE alerts ADD COLUMN IF NOT EXISTS origem TEXT;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS latencia_ms INTEGER;

COMMENT ON COLUMN alerts.origem IS
    'Fonte do frame que gerou o alerta: ao_vivo (HLS empurrado pelo edge) | '
    'rtsp (nuvem abriu a câmera) | NULL = não declarado. Sem default: ver 129.';
COMMENT ON COLUMN alerts.latencia_ms IS
    'Latência medida da cena até o alerta persistido, em ms. NULL = não medida.';

-- A tela filtra "só ao vivo"; sem índice isso vira varredura na tabela que
-- mais cresce. Parcial porque NULL é a maioria histórica e não se consulta.
CREATE INDEX IF NOT EXISTS idx_alerts_origem
    ON alerts (origem, timestamp DESC)
    WHERE origem IS NOT NULL;
