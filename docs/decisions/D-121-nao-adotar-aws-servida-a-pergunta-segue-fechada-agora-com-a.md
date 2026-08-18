# D-121 · ⛔ NÃO adotar AWS servida — a pergunta segue fechada, agora com a razão específica do repo

**Seção:** Rodada RunPod 10/08 (PR #343 — renumerada de D-85..D-88 → D-106..D-109) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

> ⚠️ Renumerado **D-110→D-121** na consolidação dos PRs #385/#386/#388 (D-110 já em uso na develop).

**16/08 · Claude · 📄 análise**

Reafirma decisão já fechada 2× (`AVALIACAO_REKOGNITION_PPE_NO_FLUXO.md`, `avaliacao-dois-estagios`). O repo, apesar de
"treine o seu classificador", usa **Custom Labels que não exporta o modelo** (colide com ADR-0043) e serve a
**US$4/h·endpoint**. O treino por-recorte fica **local** (RunPod/Vast). Nenhum frame foi ou vai à AWS (ADR-0048, D-72).

**Veredito: ⛔ não adotar.**
