# D-122 · ⛔ NÃO adotar o esquema binário 1-classe-por-recorte do repo (não-transferível)

**Seção:** Rodada RunPod 10/08 (PR #343 — renumerada de D-85..D-88 → D-106..D-109) · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

> ⚠️ Renumerado **D-111→D-122** na consolidação dos PRs #385/#386/#388 (D-111 já em uso na develop).

**16/08 · Claude · 📄 análise**

O repo classifica **vest/novest** (binário, 1 EPI). Nosso problema é **multilabel multi-parte**: 6 classes do tenant
RVB, até 3 estados por parte (`mascara` / `Sem mascara` / `Uso incorreto de mascara`). Copiar o fluxo binário de 2 zonas
quebraria o schema de rótulo.

**Veredito: ⛔ não adotar / não-transferível.** Registrado para evitar a terceira redescoberta.
