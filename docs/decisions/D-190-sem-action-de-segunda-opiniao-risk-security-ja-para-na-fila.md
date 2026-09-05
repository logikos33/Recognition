# D-190 · Sem Action de segunda opinião: `risk:security` já para na fila do humano

**Data:** 2026-09-02 · **Status:** ✅ vigente

Foi cogitada uma GitHub Action que, ao ver a label `P0` ou `risk:security` num PR,
chamasse um segundo modelo para dar parecer automático.

**Decisão:** não construir.

**Por quê:** `risk:security` **já para a fila** e vai ao Vitor antes de qualquer outra
coisa — o caminho mais sensível do repo já tem gate humano. Empilhar um parecer
automático em cima disso adiciona segredo de API, custo por PR e uma máquina a mais
para manter, e o que ela produz é um comentário que o humano lê depois de já ter
decidido olhar. É cerimônia sobre um portão que já existe.

O que fica no lugar, sem máquina nova: o **cético posta o veredito como review no PR**
(`gh pr review`), com prova reproduzida. Registro durável, custo zero, e não-bloqueante
na `develop`.

**Reabrir se:** o volume de PRs crescer a ponto de o cético humano/agente virar gargalo
medido — aí a Action passa a comprar tempo real, e não só a produzir texto.
