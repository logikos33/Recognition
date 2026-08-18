# D-102 · Volta 0 do flywheel — primeiro modelo treinado do RVB (RF-DETR base), com métrica por classe legível

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**14/08 · Claude · ✅ concluído (modelo `8e8fedf7` no registry DEV, is_active=false)** · *(extraída do PR #375 — que será fechado; o D-102 preenche a lacuna que D-103/D-104 marcaram como "não localizado")*

🔴 **Aviso que acompanha este modelo:** com poucas centenas de caixas em poucas classes, vindas de poucas
câmeras, **o modelo detecta mal ou quase nada — é o resultado ESPERADO.** A Volta 0 prova que a corrente
conecta com procedência; qualidade é a próxima volta, com mais dado e variedade de ângulo.

**Contexto.** RF-DETR **base** Apache 2.0 (⛔ nunca XL/2XL, ADR-0044), RunPod RTX 3090 COMMUNITY, teto
US$2 / timeout 1h. Só anotação **humana** — 556 caixas, 100% `source='manual'` (gate D-39).

**3 bugs de export/executor achados e corrigidos (o disparo é que provou):**
1. **Categorias homônimas duplicadas** — a mesma classe chegava com dois `class_id` (catálogo <100000 e
   namespaced ≥100000). Canonicalizado em `versioning_v2._build_categories`.
2. **CUDA device-side assert** — RF-DETR descarta categoria com `supercategory=="none"`; o export marcava
   TODAS com "none". Corrigido (placeholder id 0 + reais 1..N com supercategory != "none") — **é o fix que
   entrou pelo #378** (`versioning_v2.py:402`).
3. **Executor sem pin** — `rfdetr` latest puxava transformers≥5.1 incompatível; pinado
   `rfdetr[onnxexport]==1.5.0`.

**Métricas por classe (migration 098, antes dormente) — populadas no worker:** suporte por classe/split
(determinístico, do COCO) + P/R/F1 no maior split held-out (best-effort, greedy IoU, nunca derruba o
artefato) + confusão + procedência. Split por câmera+dia (sem leakage): train 210 / val 6 / test 179.
⚠️ **A implementação de código dessas métricas segue no #375 (não extraída aqui) — ver recomendação.**
