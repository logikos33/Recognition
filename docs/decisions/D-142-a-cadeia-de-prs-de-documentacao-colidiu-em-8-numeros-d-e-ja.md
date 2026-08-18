# D-142 · A cadeia de PRs de documentação colidiu em 8 números `D-` e já nasceu desatualizada

**Seção:** Rodada 17/08 — consolidação + pôr o modelo para trabalhar (D-116..D-119) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**Status:** ✅ vigente · **exige ação humana do Vitor**

`develop` e a cadeia aberta #385 → #386 → #388 usam os **mesmos números para decisões diferentes**:
**D-107, D-108, D-109, D-113, D-114, D-115, D-116, D-117** — oito colisões.

Pior: **o D-117 da PR #388 afirma "#384 não mergeado"** — e #384 foi mergeada em `98056cf7`,
durante esta auditoria. A cadeia de docs descreve um estado que já não existe.

**Decisões desta auditoria numeradas a partir de D-137** para não agravar.

**Ação pendente (Vitor, gate humano):** decidir se as PRs #385/#386/#388 são renumeradas antes do merge
ou se o conteúdo é portado. **Merge como está reescreve 8 decisões vigentes da `develop`.**
