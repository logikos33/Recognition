# D-108 · Volta 1 será um modelo de UMA câmera — e isso é esperado, não defeito

**Seção:** Rodada RunPod 10/08 (PR #343 — renumerada de D-85..D-88 → D-106..D-109) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**10/08 · Vitor (decisão de produto) · 📌 para a próxima encenação**

O pool consentido de 31/07 são **662 frames de uma única câmera**. Consequência: a propagação
gera propostas de um só ponto de vista e o modelo da Volta 1 **não vai funcionar nas outras
sete** — o mesmo erro de leitura da resolução: ver o modelo falhar na câmera 3 e concluir que o
sistema não presta, quando ele nunca viu a câmera 3. **Decisão de produto registrada: a próxima
encenação (ou a autorização dos frames de operação) precisa cobrir várias câmeras**, senão a
volta 2 herda a limitação. Junto: ~15 caixas ÷ 4 classes ≈ 4/classe — Volta 0 prova a CORRENTE,
Volta 1 prova a PROPAGAÇÃO, modelo que serve ao cliente é a volta 2. Trava do pool: **lista
materializada de `frame_id` + critério gravados no job, revalidados no dispatch com hash**
(não existe entidade "sessão de coleta"; `recorder_id` é o NVR, igual em tudo — não identifica
sessão).
