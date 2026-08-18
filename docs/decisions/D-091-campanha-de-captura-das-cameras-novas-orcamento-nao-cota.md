# D-091 · Campanha de captura das câmeras novas: orçamento, não cota por câmera

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**12/08 · proposta Claude, número a confirmar com Vitor · 🔄**

Acervo real em 12/08: **8.757 frames, 345 anotados** (~4%). Acervo que ninguém anota não é
dado, é custo — a cota herdada (500-1000/câmera × 21 novas) geraria 10-21k frames, mais que
dobrando o acervo sem dobrar capacidade de anotação.

**Proposta: 150 frames/câmera nova, liberados em 3 janelas de 50** via
`COLLECTOR_TARGET_FRAMES_PER_CAMERA` (50 → 100 → 150, um restart barato entre janelas agora
que o contador persiste): manhã, meio-dia, fim de tarde. **Variedade de luz vale mais que
quantidade** — é exatamente o que o pool de 31/07 (uma câmera, uma janela) não tem. Teto se as
21 ficarem: **~3.150 frames** (+36% do acervo). As 8 antigas (988-1.679 cada) ficam paradas
pela cota semeada.

⛔ **Coleta só nas câmeras que o Vitor marcar na triagem** (`/epi/cameras/triagem`): draft
(`is_active=false`) não entra no channel_map do config poll — a trava é estrutural, não
convenção. Sequência: deploy → Vitor tria e nomeia → captura liga. Janela da campanha
combinada com o Vitor antes (⛔ não saturar o gravador — ele grava a fábrica).
