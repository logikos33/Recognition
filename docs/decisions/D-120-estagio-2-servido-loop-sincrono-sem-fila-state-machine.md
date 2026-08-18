# D-120 · Estágio 2 servido = loop síncrono; ⛔ sem fila / state-machine / tabela nova

**Seção:** Rodada RunPod 10/08 (PR #343 — renumerada de D-85..D-88 → D-106..D-109) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

> ⚠️ Renumerado **D-109→D-120** na consolidação dos PRs #385/#386/#388 (D-109 já em uso na develop).

**16/08 · Claude · 📄 análise (guardrail)**

**Medido/observado.** O repo faz os 2 estágios num Lambda **síncrono**, classificando pessoas em paralelo
(`Promise.all`, `source/api/lib/index.js:400-436`), **sem banco, sem fila, sem state-machine** — estado só em S3 + ARN.
O projeto já pagou caro por manter complexidade duplicada.

**Veredito: ✅ adotar como guardrail.** Quando o Estágio 2 for servido, manter loop recorta→classifica em paralelo; não
introduzir orquestração nova. A lição de infra do repo é a **minimalidade**.
