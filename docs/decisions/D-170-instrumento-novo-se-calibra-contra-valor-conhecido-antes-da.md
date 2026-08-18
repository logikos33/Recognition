# D-170 · Instrumento novo se calibra contra valor conhecido ANTES da medida que decide

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **Data:** 2026-08-18

O baseline 0,4375 veio de um harness offline **nunca commitado** — `per_class_eval_split` não existia
em lugar nenhum do repositório. Para comparar o TREINO 2 foi preciso **reconstruir o instrumento**.

Um instrumento reconstruído não vale nada até reproduzir um valor conhecido. Este reproduziu
`tp=14` e `fn=92` **exatos** do baseline em `thr=0.55`, com casamento guloso **cego à classe** — e
foi assim que a regra de casamento original ficou conhecida: nenhum limiar sobre casamento *dentro*
da classe podia dar `fp` maior **e** `tp` menor ao mesmo tempo, o que denunciou a regra cega.

⚠️ **A divergência que sobra está registrada, não escondida:** `fp` 13 contra 18. Um harness que
omite o que não fecha não é instrumento.

Versionado em `training/eval/per_class_eval.py` com 7 testes (PR #430, fecha #418).
