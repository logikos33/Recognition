# D-148 · Proposta: um arquivo por decisão — o `REGISTRO` virou mutex global

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ⏸ proposta — ⛔ NÃO implementada nesta rodada

**Três colisões em três rodadas**, agora com dano medido (D-147). A causa não é descuido: é que
`docs/REGISTRO_DE_DECISOES.md` é **um arquivo append-only tocado por todo PR**, então dois PRs
paralelos colidem por construção. Os ADRs (`docs/decisions/adr/`) nunca colidiram assim — **porque são
um arquivo por decisão.**

**Proposta:** `docs/decisions/d/D-NNN-slug.md`, um arquivo por decisão, e o `REGISTRO_DE_DECISOES.md`
vira índice gerado.

| Peça | Esforço |
|---|---|
| Script de split do arquivo atual (147 entradas) em arquivos | **P** — parsing por `^### D-` |
| Gerador do índice + check de CI (índice bate com os arquivos) | **P** |
| Guard de numeração no CI (recusa `D-` duplicado entre PRs abertos) | **P** — já existe precedente: `Migrations collision guard` |
| Reescrever links `[[D-NNN]]` existentes | **M** — há referências cruzadas em docs e ADRs |
| **Total** | **M** (1 rodada dedicada) |

**Ganho:** dois PRs só colidem se tocarem a MESMA decisão. Hoje colidem sempre.
**Condição para fazer:** próxima rodada que não tenha experimento em curso — ⛔ não misturar com dado.
