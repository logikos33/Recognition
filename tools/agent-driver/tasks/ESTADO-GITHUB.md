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
→ ✅ **Resolvido em 05/09** (#681, D-191): é required nas três branches. Ver *Reconciliação* no fim.

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

## Resultado medido — as 5 falhas de CI dos últimos 60 runs, todas explicadas

| Run | Branch | Causa | Estado |
|---|---|---|---|
| 33407024422 | `develop` | `CropClassifierFiltro` (#618) | ✅ corrigida — PR #654 |
| 33403614910 | `develop` | `Modulos.test.tsx` | ✅ corrigida — PR #654 |
| 33501160346 | `ux2/periodo` | e2e `task-078-visual` | ❌ **veredito não entregue** |
| 33503612087 | `ux2/periodo` | e2e `task-078-visual` | ❌ **veredito não entregue** |
| 33459508504 | `ux2/a1` | **Docs gate** | ✅ não é flaky — portão funcionando |

**4 de 5 explicadas com certeza.** As duas de `develop` eram as MESMAS duas famílias mortas no PR #654 — não era coincidência de branch, era o mesmo defeito batendo em todo lugar.

## Bloco 1 — saúde do CI

| # | Item | Estado |
|---|---|---|
| 1.1a | #618 `CropClassifierFiltro` | ✅ PR #654 — causa medida, mutação, 3× shuffle verde, **CI verde** |
| 1.1b | `Modulos.test.tsx` | ✅ PR #654 — mesma causa |
| 1.1c | #627 `CameraModelAssignment` | ⚠️ **segue aberta — não reproduzida.** Hipótese registrada na issue. Sem reprodução não há causa medida, e sem causa não se mexe no teste. |
| 1.2 | e2e `task-078-visual` — flake ou regressão do #645? | ❌ **NÃO AUDITÁVEL nesta rodada.** A pista não entregou o veredito. **Ninguém sabe se o #645 tem regressão real.** Ver abaixo. |
| 1.3 | Padrão anti-flaky como regra | ✅ CLAUDE.md (PR #652) |

**A causa raiz, medida — e a hipótese das issues caiu.** #618 e #627 supunham *poluição de estado entre arquivos*. **Não se sustenta:** `vitest.config.ts` não tem `isolate:false` e o vitest isola cada arquivo por padrão. A causa real é **corrida entre `useEffect` e evento**: o teste espera a RENDERIZAÇÃO (`findBy*`) quando devia esperar o EFEITO assentar. Sob contenção de CPU o `fireEvent` cai entre um commit de efeito e outro.

⛔ **`waitFor` na asserção NÃO conserta isto** — foi tentado e reprovado. Em `Modulos.tsx:174`, com `cartoes` velho o handler **engole a tecla**: `navegar` nunca é chamado e nunca será. `waitFor` conserta chamada ATRASADA, não PERDIDA. Correção certa: `await act(async () => {})` ANTES do evento.

## Bloco 2 — pacote GitHub

| # | Item | Estado |
|---|---|---|
| 2.1 | Branch protection `staging`/`main` | ✅ **aplicada** (decisão do Vitor: checks verdes, sem aprovação, admin passa) |
| 2.2 | Template de PR curto | ✅ PR #652 — 27→19 linhas, ~20→8 caixas |
| 2.3 | Labels formais | ✅ 12 criadas; 0 issues sem label |
| 2.4 | Issue com dono/classificação/destino | ✅ PR #652 |
| 2.4b | Jardineiro | ⚠️ **parcial** — ~19 de 60 auditadas; 3 fechadas com prova (#530, #475, #536) |
| 2.5 | Fila E1…E10 vira issue | ⛔ bloqueado — lista não existe no repo |
| 2.6 | Cético como review | ✅ documentado + **exercido no PR #654** |
| 2.7 | Secret scanning · Dependabot | ✅ (1 resíduo: non-provider patterns, ação Vitor pela UI) |
| 2.8 | CODEOWNERS | ✅ PR #652 |
| 2.9 | Tag de deploy | ✅ PR #652 |
| 2.10 | Relatório semanal da fila | ✅ PR #652 — `scripts/ci/issues_report.py` |

## O que ficou ABERTO com dono

- **#655 🔴 `risk:security`** — advisory nova de `browserslist` (high) publicada HOJE deixa todo PR vermelho. Janela registrada: #652 às 05:36 passou, #654 às 06:04 falhou, **zero mudança de dependência**. ⛔ Não consertei (R7). **Decisão A/B no corpo da issue → Vitor.**
- **#627** — flaky não reproduzido; hipótese e receita de reprodução registradas na issue.
- **e2e `task-078-visual`** — **o buraco desta rodada.** Não se sabe se o PR #645 tem regressão real na tela de Eventos (o PR mexe justamente ali, e o teste que quebra navega Eventos→detalhe). **Não mergear o #645 sem alguém rodar esse e2e nas duas branches.**
- **41 issues não auditadas** pelo jardineiro.

## Único gate humano desta pista

~~**Ligar branch protection em `staging` e `main`.** Hoje as duas estão **sem proteção nenhuma**.~~
→ ✅ **Feito.** As três branches têm 5 required checks (medido 05/09). Ver *Reconciliação* no fim.
Proposta: exigir aprovação do Vitor + checks verdes, **merge commit** permitido e **squash bloqueado** (runbook `docs/runbooks/GITHUB_CONTRIBUTIONS_MERGE_MAIN.md` exige merge commit).
⛔ Na `develop` **nada de aprovação obrigatória** — só required checks, como já é.

## Retomada

1. `gh pr list` — #652 mergeado? Os PRs de flaky nasceram?
2. `gh run list --workflow CI --limit 30 --json conclusion,headBranch` — quantos vermelhos?
3. `gh issue list --state open | wc -l` — contagem e idade (métrica do jardineiro).
4. ~~Branch protection: `staging/protection` ainda dá 404?~~ → **não**: protegida, 5 required checks (05/09).

---

## Reconciliação — 2026-09-05 (onda 2, pista de governança)

⚠️ Este documento estava **contradizendo a si mesmo**: a linha 2.1 do Bloco 2 dizia branch
protection de `staging`/`main` "✅ aplicada", enquanto o *Único gate humano* e a *Retomada*
diziam "sem proteção nenhuma" e "ainda dá 404?". Medido hoje, quem estava certo era o 2.1 — e
já nem ele descrevia o estado atual.

**Estado real, medido em 05/09** (`gh api repos/logikos33/Recognition/branches/<b>/protection`):

| branch | protegida? | required checks |
|---|---|---|
| `develop` | ✅ | 5 |
| `staging` | ✅ | 5 |
| `main` | ✅ | 5 |

Os 5, idênticos nas três: `License gate (no AGPL/GPL in serving path)` · `Migrations harness (D1)` ·
`Tests (pytest)` · `Frontend tests (tsc + vitest + playwright)` · `TypeScript check`.
Os dois últimos entraram em 05/09 pela #681, depois de #654 matar as famílias de teste instável.
`gh api .../rulesets` devolve `[]` — não há ruleset competindo com a branch protection.

⚠️ **O que continua aberto e ⛔ não está escrito em lugar nenhum:** `enforce_admins: false` nas
três. Os required checks valem para agentes; quem tem admin passa por cima — de propósito, para
o dono não ficar trancado fora na véspera do go-live. Registrado em #741.

**Achado colateral:** o `default_branch` é `main`, que está **1308 commits atrás da `develop`**.
É por isso que todo push devolve "86 vulnerabilities on the default branch" enquanto o gate de
`npm audit` do CI fica verde: eles ⛔ não olham a mesma árvore. Registrado em #740.
