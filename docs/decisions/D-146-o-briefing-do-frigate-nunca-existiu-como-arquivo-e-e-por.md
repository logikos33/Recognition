# D-146 · ⛔ O briefing do Frigate nunca existiu como arquivo — e é por isso que ele "sumiu"

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente

O briefing desta rodada afirma que `docs/decisions/BRIEFING_PADROES_FRIGATE_AWS.md` está no repositório.
**Não está — em nenhuma das 172 branches remotas, em nenhum ponto do histórico, em nenhum disco local.**

Verificado por `git grep -il "frigate"` sobre todas as branches remotas (só acha
`docs/research/PESQUISA_CV_30_CAMERAS.md` e `Roccatextil/arquitetura-plataforma-multitenant.md`),
por `git log --all --diff-filter=AD -- '*FRIGATE*'` (vazio) e por `find` no disco.

O briefing diz que o documento do Frigate *"virou documento e sumiu do conjunto de trabalho"*.
**Ele não chegou a virar documento.** Nunca foi commitado.

**A decisão:** avaliação que não vira arquivo commitado **não existe** na rodada seguinte.
Toda rodada de avaliação/benchmark termina com **arquivo commitado + entrada neste registro** —
inclusive quando a conclusão é "não vamos fazer". Foi exatamente esse o buraco que custou o Frigate.
