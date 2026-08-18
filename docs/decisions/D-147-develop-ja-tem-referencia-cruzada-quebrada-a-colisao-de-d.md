# D-147 · `develop` já tem referência cruzada QUEBRADA — a colisão de `D-` deixou de ser hipotética

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **corrige referências, não decisões**

D-129 diz *"↩ corrige D-121"* e D-131 diz *"↩ corrige D-123"*. Ambas foram escritas apontando para as
entradas do PR #391, que **nunca mergeou**. Em `develop`, D-121 é *"⛔ NÃO adotar AWS servida"* e D-123 é
*"a campanha real de mineração é passo humano no box"* — **nada a ver**.

**Referências corretas:** D-129 corrige a entrada agora portada como **D-138**; D-131 corrige a **D-140**.

Não é um erro de conteúdo — as duas decisões estão certas no que afirmam. É o **índice** que apodreceu,
e apodreceu porque dois PRs escreveram no mesmo arquivo append-only em janelas sobrepostas.
