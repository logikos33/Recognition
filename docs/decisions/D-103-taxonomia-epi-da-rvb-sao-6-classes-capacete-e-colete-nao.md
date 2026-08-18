# D-103 · Taxonomia EPI da RVB são 6 classes — capacete e colete NÃO são EPI exigido

**Seção:** Rodada de 11-12/08 — merges da triagem, prática do ledger e preparo da campanha · **Origem:** `docs/REGISTRO_DE_DECISOES.md`

**14/08 · Claude · ✅ decidido (Vitor)**

*(D-102 não localizado no registro em 14/08 — número deixado para o Vitor; esta entrada usa D-103
conforme a rodada de procedência.)*

**Decisão (Vitor):** a taxonomia de anotação vigente da RVB tem **6 classes** — `Protetor auditivo`,
`Sem protetor de ouvido`, `mascara`, `Sem mascara`, `Uso incorreto de mascara`, `Botas`. **`Capacete`,
`Sem Capacete`, `Colete`, `Sem Colete` e `hardhat` saem em DEFINITIVO**: capacete e colete não são EPI
exigido na RVB. ⛔ Não viram "backlog" nem "classe futura" — manter as duas versões vivas é exatamente o
mecanismo que envenenou o prompt do TREINO 1.

**Por quê registrar:** a classe fantasma `Sem Capacete` — que **nunca existiu no banco** — sobreviveu em
**três rodadas de planeamento** porque a lista divergia entre documentos (`docs/ROTEIRO_ANOTACAO_VITOR.md`
dizia uma coisa, o prompt herdava outra). Corrigido em `CLAUDE.md` e `ROTEIRO_ANOTACAO_VITOR.md`; ambos
carregam agora o bloco marcado `<!-- RVB-EPI-CLASSES -->`, e o **gate de docs**
(`scripts/ci/check_docs_gate.py`, regra 6) **falha o CI se a lista divergir entre documentos**. A lista de
demo genérica do produto (helmet/vest/gloves em `apps/frontend`, landing, `constants.py`) é **outra
taxonomia** (marketing/demo), fora do escopo do D-103 — não confundir.

**Como aplicar:** ao mexer na taxonomia da RVB, edite o bloco `RVB-EPI-CLASSES` em **todos** os docs que o
carregam (o gate lista quais divergem). Fonte da verdade = este registro. Ver
`docs/decisions/PROCEDENCIA_DE_RELATOS.md`.
