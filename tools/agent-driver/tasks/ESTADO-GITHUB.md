# ESTADO — Pista GOVERNANÇA GITHUB & SAÚDE DO CI

> Reentrante. **Valide contra o repo antes de agir (C-04).** Este arquivo descreve
> o que foi medido em 2026-09-02 — não é fonte de verdade sobre o estado de hoje.

**Aberta:** 2026-09-02 · **Worktrees:** `wt-gh-pkg` (pacote), `wt-github` (flaky vitest), `wt-gh-e2e` (flaky e2e), todos de `origin/develop` @`75bfcc0f`.

---

## Coordenação com as outras pistas

- Esta pista **assumiu o E11** da lista de espera da pista do modelo.
- ⚠️ **NÃO AUDITÁVEL:** a lista de espera `E1…E11` **não existe no repositório**. Procurei em `tools/agent-driver/tasks/ESTADO-*.md`, `docs/*.md` e nos worktrees `wt-ux2*` — zero ocorrência de `E11`. Deve viver no Notion ou num worktree não mergeado. **Não consegui registrar "E11 → em execução na pista GITHUB" onde a pista do modelo veria.** Quem tiver a lista, marque lá.
- ⛔ Não toquei em `training/`, `services/inference/`, `deepstream/` (faixa do modelo).

---

## Estado medido do GitHub (2026-09-02, via `gh api`)

| Item | Estado medido |
|---|---|
| Visibilidade do repo | **público** |
| Branch default | `main` |
| Proteção da `develop` | ✅ 3 required checks: License gate · Migrations harness (D1) · Tests (pytest) |
| Proteção da `staging` | ❌ **nenhuma** (`404 Branch not protected`) |
| Proteção da `main` | ❌ **nenhuma** (`404 Branch not protected`) |
| Secret scanning | ✅ já estava ligado |
| Push protection | ✅ já estava ligado |
| Dependabot alertas | ❌→✅ **ligado nesta sessão** |
| Dependabot security updates | ❌→✅ **ligado nesta sessão** |
| Secret scanning non-provider patterns | ❌ não liga por API (PATCH aceito, valor não muda — provável limite de plano). **Ação do Vitor pela UI.** |

**Nota:** `Frontend tests (tsc + vitest + playwright)` **não é required check** na `develop` — por isso um frontend vermelho não bloqueia merge. Decisão consciente? Registrar.

---

## Achado: Dependabot pedia 4 labels inexistentes

`.github/dependabot.yml` referenciava `dependencies`, `github-actions`, `python`, `javascript`. **Nenhuma das quatro existia** — Dependabot falha em silêncio ao aplicar label inexistente. Criadas nesta sessão.

**Labels criadas (12):** `P0` `P1` `P2` `P3` · `faixa:github` `faixa:infra` `faixa:ux` · `flaky` · `dependencies` `github-actions` `python` `javascript`.
Já existiam e foram mantidas: `risk:security`, `faixa:modelo`, `faixa:migracao`, `humano-gated` (= o "espera-EN" pedido; não dupliquei).

---

## Correção de premissa: o "#645 verde local × vermelho CI no MESMO SHA"

**A premissa não se sustenta como foi descrita.** Medido no run `33503612087`:

1. **Não é vitest.** A falha é **Playwright/e2e**:
   `task-078-visual.spec.ts:95` → `locator.waitFor: Test timeout of 30000ms exceeded` esperando `getByRole('heading', {name: /^Evento #/})`. Falhou **também no retry #1**. Placar: 1 failed, 2 skipped, 114 passed.
2. **Não é o mesmo SHA.** O CI faz checkout de `refs/remotes/pull/645/merge` = `9008ee69` (merge de `adc7c668` dentro de `af436dbf`). O SHA rodado localmente é `adc7c668`. **São árvores diferentes** — "mesmo SHA" nunca foi verdade. Essa é uma explicação estrutural de divergência local×CI que vale para qualquer PR, não só o #645.
3. **Suspeita aberta:** o PR #645 mexe justamente na tela de Eventos, e o teste que quebrou navega Eventos → detalhe. Pode ser **regressão real**, não instabilidade. Delegado para medição.

**CI falhou 5 vezes nos últimos 60 runs:** `ux2/periodo` (2×), `ux2/a1` (1×), **`develop` (2×: 33407024422, 33403614910)**.

---

## Fila de trabalho

### Bloco 1 — saúde do CI
| # | Item | Estado |
|---|---|---|
| 1.1 | Flaky vitest: #618 CropClassifierFiltro · #627 CameraModelAssignment · Modulos.test.tsx | em execução (`wt-github`) |
| 1.2 | Flaky/regressão e2e `task-078-visual` + 2 falhas na própria `develop` | em execução (`wt-gh-e2e`) |
| 1.3 | Padrão anti-flaky escrito como regra | ✅ CLAUDE.md § Processo no GitHub |

**Hipóteses concorrentes do 1.1 (a medir, não assumir):**
- (H1) vazamento de estado entre arquivos — **improvável**: `vitest.config.ts` não tem `isolate:false`, e o vitest isola cada arquivo por padrão.
- (H2) **timing sob contenção de CPU** — `src/test/setup.ts` tem só `afterEach(cleanup)`; "passa isolado, falha em paralelo" é a assinatura clássica de `waitFor` estourando com N workers disputando CPU.

### Bloco 2 — pacote GitHub
| # | Item | Estado |
|---|---|---|
| 2.2 | Template de PR curto (27→19 linhas, ~20→8 caixas) | ✅ PR #652 |
| 2.3 | Labels formais | ✅ 12 criadas |
| 2.4 | Issue com dono/classificação/destino | ✅ PR #652 |
| 2.4b | **Jardineiro** — triagem das 64 issues abertas | em execução (triagem com prova) |
| 2.5 | Fila operacional E1…E10 vira issue | ⛔ **bloqueado** — lista não existe no repo (ver acima) |
| 2.6 | Cético como review, documentado | ✅ PR #652 (CLAUDE.md) |
| 2.7 | Secret scanning · push protection · Dependabot | ✅ (1 resíduo: non-provider patterns, ação Vitor) |
| 2.8 | CODEOWNERS mapeia zonas quentes | ✅ PR #652 |
| 2.9 | Tag de deploy datada no merge para staging | ✅ PR #652 |
| 2.1 | **Branch protection em `staging`/`main`** | 🛑 **AGUARDA VITOR** (R9 — muda o fluxo de merge dele) |

---

## Único gate humano desta pista

**Ligar branch protection em `staging` e `main`.** Hoje as duas estão **sem proteção nenhuma**.
Proposta: exigir aprovação do Vitor + checks verdes, **merge commit** permitido e **squash bloqueado** (runbook `docs/runbooks/GITHUB_CONTRIBUTIONS_MERGE_MAIN.md` exige merge commit).
⛔ Na `develop` **nada de aprovação obrigatória** — só required checks, como já é.

## Retomada

1. `gh pr list` — #652 mergeado? Os PRs de flaky nasceram?
2. `gh run list --workflow CI --limit 30 --json conclusion,headBranch` — quantos vermelhos?
3. `gh issue list --state open | wc -l` — contagem e idade (métrica do jardineiro).
4. Branch protection: `gh api repos/logikos33/Recognition/branches/staging/protection` ainda dá 404?
