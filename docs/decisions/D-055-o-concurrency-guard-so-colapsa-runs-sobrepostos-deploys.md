# D-055 · O concurrency guard só colapsa runs SOBREPOSTOS — deploys escalonados exigem disciplina

**Seção:** 3ª rodada de 04/08 — "Live view fluido de verdade + causa do SIGTERM" (D-48..D-53) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**04/08 · Claude → aceito · ✅ vigente · refina [[D-50]]**

Refinamento importante medido em campo: o `concurrency: cancel-in-progress` ([[D-50]]) colapsa deploys
apenas quando os runs se **sobrepõem no tempo**. Mergear 4 PRs em ~13 min gerou 4 runs de CI que terminaram
**escalonados** (cada CI ~9 min), disparando 4 deploys separados minutos um do outro — que NÃO se
sobrepõem, então o guard não os cancelou, e a API reiniciou a cada um. Um soak iniciado cedo demais pegou 2
desses reinícios. **A defesa completa é operacional, não só o guard:** mergear **1 PR por vez esperando o
deploy anterior chegar a SUCCESS** (uptime estável), como manda [[D-51]]. O guard cobre o caso patológico
(3 merges em 17 s → 1 deploy); a disciplina cobre o caso escalonado.
