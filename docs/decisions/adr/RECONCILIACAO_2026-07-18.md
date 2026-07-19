# Reconciliação de numeração de ADRs — 2026-07-18

> **Escopo:** resolver a **duplicata de número** na `develop`. **Regra aplicada:** só se mexe em
> **número / status / ponteiro** — **nenhuma decisão é reescrita** (mesma disciplina do ADR-0021).
>
> **Fonte de verdade (C-04 aplicado a git):** estado da `develop` verificado por **`gh api` fresco**, não por
> ref local (que estava desatualizada). `origin/develop` HEAD = `2a48daf3`. Comando de verificação:
> `gh api "repos/logikos33/Recognition/contents/docs/decisions/adr?ref=develop" --jq '.[].name'`.

## 1. Estado REAL da `develop` (verificado 2026-07-18)

| Situação | Detalhe |
|---|---|
| **Duplicata `0043`** (colisão real) | `0043-agpl-zero-todos-modulos.md` (Aceito, canônico) **E** `0043-migracao-design-v3-centro-de-comando.md` (Proposta) — **ambos na develop** |
| **Buraco `0029`** | numeração pula de `0028` para `0030` |
| **`0053` JÁ está na develop** | `0053-cenario-multimodulo-*.md` chegou via **#193 (MERGED)** — **não** é delta desta reconciliação (correção de uma afirmação anterior errada que dizia "0053 só em branch") |

**Causa-raiz da dup (cascata, padrão ADR-0021):** a decisão *"migração design v3 — Centro de Comando"* nasceu
como **0041** (é assim que `docs/design/recognition-v3/FONTE-DE-VERDADE.md` a referenciava), foi empurrada para
**0043** para não colidir com `0041-api-contract-convergence`, e caiu em cima do **0043-agpl-zero** (canônico,
Aceito, referenciado por `CLAUDE.md`, `constitution.md`, ADR-0044/0047/0053, `check_license_gate.py`).

## 2. Ação nesta PR (sobre a `develop` real)

| Decisão | ANTES | DEPOIS | Ação |
|---|---|---|---|
| AGPL-zero em todos os módulos (Aceito) | 0043 | **0043** | mantido — canônico, muito referenciado |
| Migração design v3 "Centro de Comando" (Proposta) | 0041→0043 (colidido) | **0029** | renomeado p/ o slot livre (resolve dup + buraco); H1 + nota; ref em `FONTE-DE-VERDADE.md` corrigida 0041→0029 |
| Cenário RVB multi-módulo (Proposta) | **0053 (já na develop)** | **0053** | **nada a fazer** — já reconciliado via #193 |

Resultado: `0000–0053` **sem duplicata e sem buraco** (0029 preenchido, 0043 único).

## 3. Colisões remanescentes em branches NÃO integradas (p/ o gate humano no merge)

Documentadas para não redescobrir; vivem só em branches de feature:

| Branch | Arquivo | Recomendação no merge |
|---|---|---|
| `fix/admin-users-null-tenant-id` | `0041-migracao-design-v3-*.md` | mesma decisão agora canônica em **0029** → renomear/dropar |
| `fix/admin-users-null-tenant-id` | `0039-training-compute-providers-edge-integrations.md` | mesma linhagem do `0039-abstraction` na develop; se aditivo → novo nº livre; se rename → dropar |
| `claude/pending-migrations-validation-ov3aw9` | `0043-migration-052-sixway-collision-renumber.md` | decisão distinta (Aceito) ocupando 0043 → renumerar p/ **0054** no merge. **Nota:** o `main` já tem #159 "renumerar colisão 052 (ADR-0043)" — checar se esta branch é redundante com o que já está no main |

**Próximos números livres:** `0054`, `0055`, depois `0056+`.

## 4. Verificação

```bash
# nenhum número com mais de um arquivo distinto:
ls docs/decisions/adr/[0-9]*.md | sed 's#.*/##;s/-.*//' | sort | uniq -d   # deve sair vazio
# sem buraco 0000..0053 (0029 preenchido):
ls docs/decisions/adr/[0-9]*.md | sed 's#.*/##;s/-.*//' | sort -u
```
