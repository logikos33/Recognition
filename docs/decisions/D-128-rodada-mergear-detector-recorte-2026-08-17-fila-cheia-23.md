# D-128 · Rodada mergear+detector+recorte (2026-08-17): fila cheia, 23-postes refutado, blur recalibrado

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Contexto.** Prompt pedia (a) fechar fila de PRs, (b) "consertar detector antes de recortar" e medir vs 377 anotados, (c) recortar o acervo. Clone limpo de `origin/develop` (111 migrations, máx 122). Fase 1 (plano) aprovada pelo Vitor com 2 decisões: bloco 2 reformulado + consolidar docs num branch fresco.

**O que o repo/DB disseram (divergências medidas, segui o repo):**
- 🔴 Os **9.649 frames `nvr` JÁ SÃO RECORTES** de pessoa (avg 363×435, produzidos pelo coletor edge ao vivo — `person_detector.py` YOLOX-nano). Full-frame não é retido → **não dá pra rerodar o detector nem "recortar o acervo" (já é recorte)**.
- 🔴 Os "377 anotados" são **489** frames, e são **caixas de EPI SOBRE recortes** (+89 uploads 640²), **não** caixa-de-pessoa em full-frame → **recall/precisão/IoU vs ground-truth de detecção é IMPOSSÍVEL** (não existe verdade de pessoa). `model_confidence` é NULL nos 9.207 → confiança nem é medível no DB.
- 🔴 **"23/23 postes" REFUTADO por medição visual** (montagem de 144 recortes): precisão real ~**80-85%**; os falsos-positivos são **estruturas fixas em 2 câmeras** (775c = tambor metálico embrulhado; 7ad4 = poste listrado + carros), aparecendo como **rajadas de quase-duplicatas** — não "23/23 em todo lote".

**Bloco 2 reformulado (aprovado):** medir precisão por amostra + calibrar blur real + quarentena reversível.
- **Blur:** `_DEFAULT_BLUR_VARIANCE_MIN` 3000→150 (`replay_miner.py`, PR #389). Medido com a própria `blur_variance` sobre n=224 crops reais: mediana=693, p05=199; o 3000 rejeitava **98%**. Só afeta mineração futura (miner não deployado).
- **Dedup/quarentena (bloco 3.2):** dHash≤6 por câmera sobre 8.843 crops → **1.602 quase-duplicatas (18%)** marcadas `curation_status='excluida'` (reversível, mantém 1 representante/cluster). Pega as rajadas de estrutura fixa. Restam **7.241** crops limpos não-anotados.

**Fila + DEV (bloco 4, provado, não presumido):** #384 mergeado → aba Classificar no ar. E2E DEV: login (conta E2E) → assumir contexto RVB → `GET /api/training/images` devolve **7.623 recortes active** ranqueados por `missing_class`. API+Frontend 200; "Classificar" no bundle.

**Fila de PRs:** #387 mergeado (verificador R2). #384 mergeado (merge de develop→branch, sem force; `supercategory: module_code` preservado em `versioning_v2.py:402`; entradas D-105/106/107/112 do #384 renumeradas → **D-114/115/116/117**). npm-audit(landing) é vermelho pré-existente e **não-required** (develop não-protegida) → não bloqueia; fix real é upgrade Astro 4→7 (3 majors breaking) → **task isolada, não drive-by**. **Recomendo fechar** (ato do Vitor): **#375** (pode reverter #378), **#293**, **#259** — valor extraído; e **#385/#386/#388** — docs consolidados aqui.

**Pendências do Vitor (inalteradas):** rotacionar senha Postgres DEV (vazou); rebaixar `e2e-anotacao` de superadmin→anotador; token R2 read-only dedicado; provisionar o beat; deploy OTA do miner + 6 itens pra rodar o Lote 1 real. Ver docs consolidados nesta rodada.

**Nenhum segredo impresso.** Zero staging/main/interchange. Zero DELETE (só flag reversível).
