# D-069 · Correção do D-64 pela medição: os 679 TÊM `camera_id`

**Seção:** Rodada 06/08 — pipeline de treino (varredura R2, coleta, bloqueadores da anotação) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**06/08 · Claude**

O [[D-64]] afirmou `camera_id = NULL` nos 679. A consulta ao DEV mostra o
contrário: **679/679 com `camera_id` preenchido** — todos da `RVB Camera 1`
(canal 1), via `/edge/frames` (o coletor edge sempre persistiu). O corte por
câmera do lote atual é trivial (é UMA câmera) e o backfill one-off é
desnecessário. A ressalva do D-64 continua válida **só para o caminho cloud**
(`extract_nvr_frames`, `camera_id=None` por design) — corrigir lá quando/se a
colheita retroativa usar esse caminho.
