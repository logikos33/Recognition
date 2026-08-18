# D-064 · O "corte por câmera" é impossível com os dados atuais — é o resultado que mais falta

**Seção:** Rodada 5 — Triagem dos 679 frames RVB (05/08 · Claude) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**05/08 · Claude**

O corte por câmera é o resultado **mais valioso** da triagem (responde "quais
posições de câmera conseguem, fisicamente, servir para EPI?"). Mas **não é
recuperável do banco**: os 679 frames NVR em `training_frames` têm
`camera_id = NULL` (a coleta NVR omite), **não há coluna `channel`** (o
`channel` é só parâmetro de `extract_nvr_frames`, nunca persistido), o filename
é `uuid4` e `width`/`height` não são gravados no caminho NVR. Único
discriminador por frame: `captured_at`.

**Ação (habilita a análise por posição):** persistir `camera_id`/`channel` (e
`width`/`height`) por frame na coleta NVR (`nvr_extraction`) — migration aditiva
+ backfill onde der. Sem isso, "distribuição por câmera" só dá para **aproximar**
por resolução (615 × 704×480 substream vs ~64 de fonte maior) ou por cluster de
`captured_at` × histórico do job — registrado como aproximação, não verdade.
