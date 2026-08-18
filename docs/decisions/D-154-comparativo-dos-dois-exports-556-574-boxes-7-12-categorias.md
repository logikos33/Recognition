# D-154 · Comparativo dos dois exports: 556 → 574 boxes, 7 → 12 categorias

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **previsão registrada ANTES do TREINO 2**

Mesmo dado, única variável alterada = o export.

| Categoria | Antigo | Novo |
|---|---|---|
| Protetor auditivo | 198 | 193 |
| **mascara** | **188** | **111** |
| Sem protetor de ouvido | 66 | 41 |
| Botas · Sem mascara · Uso incorreto | 48 · 33 · 22 | iguais |
| `hardhat` (tenant e2e) | 1 | **0** — vazamento cross-tenant fechado |
| Óculos · Sem Óculos · Luvas · Sem Luvas · Capacete · Sem Capacete | — | 77 · 25 · 5 · 17 · 1 · 1 |
| **Total** | **556 · 7 cat.** | **574 · 12 cat.** |

O total antigo (556) bate exatamente com `provenance.humana: 556` gravado no `metrics` do TREINO 1 —
**a query antiga reproduz o export real daquele treino.**

**PREVISÃO, escrita antes de treinar:** *"mascara" cai de 188 para 111 boxes (−41%). **Se a precisão de
"mascara" SUBIR mesmo com 41% menos dado, é prova de rótulo.** Se cair, foi volume. Se ficar igual, os
dois se anularam.* Baseline TREINO 1: precisão **0,4375**, recall 0,1321, F1 0,2029 (tp 14, fp 18, fn 92),
avaliado no split **test** de **179 imagens** — ⛔ não no val de 6.

⚠️ ⛔ Não haverá comparação classe a classe: 12 categorias contra 7 não são comparáveis. **O sinal é a
precisão de "mascara".**
