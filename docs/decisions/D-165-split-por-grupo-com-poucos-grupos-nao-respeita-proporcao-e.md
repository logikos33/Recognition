# D-165 · Split por grupo com poucos grupos não respeita proporção — e ninguém era avisado

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente

**17 grupos câmera+dia para 413 frames**, o maior com 91. O mesmo `{train:0.7, val:0.2, test:0.1}`
produziu **210/6/179** (53/1,5/45) no `v3-treino1` e **354/51/8** (86/12/2) no `v4`. **Nas duas vezes
seguiu calado.**

⛔ **O split por grupo NÃO muda** — é ele que impede vazamento de câmera+dia e é uma das coisas em que
batemos o benchmark (D-128). O que faltava era **o aviso**.

**PROPOSTO — ⛔ SEM CÓDIGO NESTA RODADA:** `_split_by_group` deve registrar aviso alto quando qualquer
split fica abaixo de um mínimo utilizável ou muito fora da proporção pedida. É "nunca degradar em
silêncio" aplicado ao split. ⚠️ **A redação anterior dizia "Consertado" e estava ERRADA** — a decisão
foi escrita, o código não. Corrigido aqui para não mentir no próprio registro.

**Causa que se resolve sozinha:** poucos grupos ⇒ proporção instável. Entra mais câmera e mais dia —
exatamente o que a mineração estratificada vai fazer — e o problema encolhe.
