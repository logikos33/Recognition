# Higiene de repositório — 2026-07-18

> **Fonte de verdade:** `git fetch` fresco (após reparo) + **GitHub API (`gh`)**. NÃO ref local — a ref local
> estava corrompida (ver §0). Regra registrada em `DIRETRIZ_OPERACAO_CLAUDE_CODE.md §6.1`.

## ⚠️ Pendências do Vitor (topo)
1. 🔴 **Senha `admin@rvb.com.br` commitada no git** — rotacionar **pela aplicação** (nunca shell/SQL/commit). **Bloqueante de go-live.**
2. ⚠️ **Fan `quiet→cool`** antes da carga 24/7 (sudo): `sudo sed -i 's/FAN_DEFAULT_PROFILE .*/FAN_DEFAULT_PROFILE cool/' /etc/nvfancontrol.conf && sudo systemctl restart nvfancontrol`. Confirmado na checklist da task-097.
3. **Head-to-head do shootout:** D-FINE-S **convergiu e bateu o RF-DETR** (AP_small 0.626 vs 0.565) mas com orçamento 3× maior — falta comparação justa + nível C. Fora do escopo desta higiene.
4. **PRs que precisam da sua decisão:** #189 (security, gate humano), #194 (rebase+drop docs stale), #78 (fechar ou extrair delta).
5. **Convergência develop→staging** (108 commits pendentes de promoção) — gate humano (ver `EQUALIZACAO_BRANCHES_2026-07-18.md`).

## 0. Causa-raiz do registro falso (o problema que originou esta tarefa)

Um relatório anterior afirmou "`docs/edge` não existe na develop" e "develop continua no PR #184 / soak #196 não mergeou". **Falso.** Causa: **refs locais corrompidas** — dezenas de `refs/heads/` quebradas (`worktree-wf_*`, `feat/task-055a`, `feat/tp1`, `mutirao/ws*`, `wip/save-before-pc-switch`, `docs/rescue-*.lock`) apontando para objetos ausentes. Elas **envenenavam a negociação de todo `git fetch`** (`fatal: bad object ... / did not send all necessary objects`), então **nenhuma ref remote-tracking atualizava** e a `origin/develop` local ficou **13 PRs stale** em `85440ae8`. A sessão anterior leu esse cache como se fosse o real.

**Reparo aplicado:** removidas todas as refs quebradas (`find refs/heads -type f | git cat-file --batch-check | awk '/missing/'` → delete) → `git fetch` voltou a funcionar → refs locais agora batem com o GitHub.

**Prevenção:** `DIRETRIZ §6.1` — estado de branch/PR = fetch fresco + `gh`, nunca ref em cache nem memória; se o fetch não completa, dizer "não verifiquei" e usar `gh api` (não cai pro cache).

## 1. VERDADE verificada (heads reais + estado)

| Item | Valor verificado | Comando |
|---|---|---|
| `origin/develop` HEAD | `2a48daf3` ("docs(edge): REGRAS §3.4 soak") | `gh api repos/.../branches/develop` |
| `origin/staging` HEAD | `66a2faf6` | idem |
| `origin/main` HEAD | `65d51f24` | idem |
| `docs/edge/` na develop | **EXISTE** (SOAK_RVB_2026-07-18, REGRAS c/ §3.4-soak, EXPLORACAO_MODELOS, CAMPANHA, CENARIO, train_metrics, evidence, …) | `gh api .../contents/docs/edge?ref=develop` |
| Soak #196 | **MERGED na develop** | `gh pr view 196` |
| #193/#192/#191/#190 | **MERGED na develop** | `gh pr list --state all` |
| ADR dup 0043 | **AINDA na develop** (agpl + migracao-design-v3) | `gh api .../contents/docs/decisions/adr?ref=develop` |
| ADR 0053 | **JÁ na develop** (via #193) | idem |

## 2. Registro falso corrigido (onde)
- **Descrição do PR #197** — reescrita com a verdade + nota de que a branch precisa de rebase.
- **`RECONCILIACAO_2026-07-18.md`** — corrigido "0053 só em branch" → "0053 já na develop"; delta real = só a dup 0043.
- **`SHOOTOUT_QUALIDADE_2026-07-18.md`** — sem afirmações git-falsas; atualizado com o resultado convergido do D-FINE-S.
- **Memória `project_task113_soak_estado`** — retratação explícita do erro (era uma "correção" que também estava errada).
- **Memória `project_shootout_qualidade_estado`** — veredito atualizado (D-FINE-S convergiu).
- **`CLAUDE.md`** — número de divergência real (§ equalização).
- **`DIRETRIZ §6.1`** — a regra que teria evitado o alarme (fetch fresco + gh).

## 3. Decisão de cada PR aberto

| PR | Base | Decisão | Justificativa |
|---|---|---|---|
| **#197** shootout+housekeeping | develop | **ENTRA — após REBASE** (feito nesta sessão sobre a develop real) | duplicava SOAK/REGRAS/EXPLORACAO/train_metrics/0053 (já na develop) e colidia em REGRAS §3.4; reconstruído só com o delta genuíno |
| **#194** toolkit soak+hardening | develop | **MANTER (delta real) + rebase + drop docs stale** | traz a stack de provisionamento edge (`deployments/edge/*.sh`, systemd, `scripts/edge/soak/*`, `seed_rvb_edge.py`) **ausente na develop**; docs (SOAK_07-17, REGRAS, EMBARQUE) superados. Não é duplicata pura do #196. Toca sudo/systemd → revisão humana |
| **#189** 4 P1 security | develop | **MANTER — achados ativos (reverificado)** | #1 (config prod-validation morta) e #3 (IDOR cross-tenant câmera) **persistem** na develop hoje. `risk:security` → gate humano. Substitui #112 |
| **#112** 7 P1 security | develop | **FECHADO** (nesta sessão) | superseded por #189 (reverificou seus achados); 408 commits stale, toca auth reescrito (HS256→RS256). Nenhum achado perdido |
| **#78** cloud-first storage | develop | **PRECISA DO VITOR** | `CONFLICTING/DIRTY`, >2 semanas, +4181/-656, migrations 050/051; escopo provavelmente coberto por merges posteriores (#173–196). Fechar ou extrair delta = call do Vitor |

## 4. Branches deletadas (21 — PR MERGED, existentes, não protegidas/abertas)

`chore/recognition-v3-docs-and-hygiene`, `claude/jetson-experiments-sequence-a53d0f`, `claude/open-adrs-cd7vef`, `claude/pending-migrations-validation-ov3aw9`, `claude/task-078-transparent-containers-e9e7f7`, `feat/task-100-edge-telemetry-collector`, `fix/admin-users-null-tenant-id-clean`, `fix/celery-beat-curated-schedule`, `fix/ci-duplicate-license-gate-main`, `fix/ci-duplicate-license-gate-staging`, `fix/develop-onnxruntime-test-regression`, `fix/docs-envelope-and-stale-audit-findings`, `fix/login-contrast-remove-default-creds`, `fix/remove-orphan-preannotation-reqs`, `fix/sca-dependency-vulnerabilities`, `fix/storage-health-no-real-io`, `fix/tablet-rework-comment-and-d5`, `fix/task-067-default-substream-live-view`, `fix/task-068-stall-offline-backend`, `fix/task-077-annotation-class-name-persistence`, `fix/training-thumbnails-and-annotation-save`.

Método: `remote_branches ∩ merged_PR_heads − open_PR_heads − {develop,staging,main}`, via `gh api -X DELETE`. Preservadas todas com PR aberto (#197/#194/#189/#78 heads) e as protegidas. Refs quebradas locais também foram limpas (§0).

## 5. Por que a task-113 gerou 3 PRs (#194/#195/#196) — retrabalho

- **#195** (`rvb-edge-soak-memory-6f30aa`): CLOSED — tinha **secrets de teste no histórico** (gitleaks); recriado.
- **#196** (`rvb-edge-soak-clean`): MERGED — recriação limpa (docs + `soak113/`).
- **#194** (`rvb-edge-soak-memory-indnzg`): OPEN — outra branch da mesma task, com a **stack de provisionamento** que o #196 não levou (delta real) + docs stale.

**Causa:** a mesma task rodou em **múltiplas worktrees/branches paralelas** (a limpeza de secrets forçou recriação, e o harness de infra ficou numa branch separada dos docs). **Prevenção (registrada na DIRETRIZ):** **uma task = uma branch = um PR**; se precisar recriar por secret, **fechar a antiga e migrar TODO o conteúdo** para a nova (não deixar delta órfão numa terceira branch); nunca abrir branch nova sem antes checar as existentes da mesma task.

## 6. Equalização develop ↔ staging ↔ main
Ver **`EQUALIZACAO_BRANCHES_2026-07-18.md`** (medição via compare API + plano de convergência NÃO executado). Resumo: **develop +108/−2 vs staging** e **+114/−3 vs main** — o CLAUDE.md "staging 40 à frente" (2026-07-13) **se inverteu**; hoje a develop é que está à frente. Divergências reais staging/main→develop = hotfix de CI (`ci.yml` license-gate) + renumeração migration-052 (#159 no main), não back-portados. CLAUDE.md atualizado.
