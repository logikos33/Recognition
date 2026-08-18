# D-007 · Guarda de CI contra colisão de numeração de migration

**Seção:** Processo e qualidade · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**03/08 · Claude → aceito · ✅ · PR #282**

Terceira aparição da família (ADR-0021 é sobre isso). E o risco **aumentou por decisão de processo**:
worktrees paralelas criando migrations independentes é a receita da colisão — a recomendação de
paralelismo foi do Claude, então a guarda também é responsabilidade dele.
Vigilância não escala; check de CI, sim.
