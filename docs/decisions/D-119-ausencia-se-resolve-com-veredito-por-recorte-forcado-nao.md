# D-119 · Ausência se resolve com veredito por-recorte FORÇADO, não com propagação mais esperta

**Seção:** Rodada RunPod 10/08 (PR #343 — renumerada de D-85..D-88 → D-106..D-109) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

> ⚠️ Renumerado **D-108→D-119** na consolidação dos PRs #385/#386/#388 (D-108 já em uso na develop).

**16/08 · Claude · 📄 análise**

**Medido.** 273/363 recortes anotados são **só-positivo** → não dá pra fabricar negativo; a propagação SAM+DINO deu
**1005 propostas, 100% rejeitadas** (ausência não tem aparência para similaridade). O repo torna `novest` uma **classe
cheia** e isso funciona **porque a UI exige um veredito por recorte** (arrasta pra vest OU novest; nada meio-rotulado
entra no treino). A cura da ausência é de **fluxo de anotação**, não de modelo.

**Veredito: 🟡 adotar adaptado.** Na anotação, exigir veredito por classe (present/absent/N-A) por recorte antes de
contar como rotulado; reusa o scaffold grade-de-recortes + seletor + promover de `SearchFindingsPanel.tsx:44`.
Preferível ao masked-BCE-sobre-parcial (dá negativo limpo); masked BCE fica de fallback.
