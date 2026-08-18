# D-156 · Deploy por git ganha do `railway up` quando o commit está na branch — regra corrigida

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **↩ corrige orientação dada na própria rodada anterior**

A orientação era: `git archive` → diretório limpo → `railway up`. **Naquele contexto isso piorou.**
O que aconteceu no DEV em 18/08:

| Deploy | Proveniência |
|---|---|
| 00:03 — auto-deploy do merge do #392 | ✅ `commitHash b769ede5` |
| 00:12 — `railway up` de outra sessão | ⛔ sem `commitHash` — sobrescreveu o bom |
| 00:22 — `railway up` meu, seguindo a orientação | ⛔ sem `commitHash` |

**Um deploy com proveniência foi trocado por dois sem.**

**Regra:** se o auto-deploy por git está ligado e o commit já está na branch, **⛔ não use `railway up`** —
deixe o git deployar. `railway up` é para o que **não** é commit (árvore local, teste de algo não
comitado); aí sim vale a trava do `git archive` para não subir lixo do worktree.
