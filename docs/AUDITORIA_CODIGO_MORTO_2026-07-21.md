# Auditoria de Código Morto / Caminhos Fantasma — 2026-07-21

**Branch:** `claude/dead-code-audit-e1a168` (worktree de `origin/develop`) · **NÃO toca `staging`/`main`.**
**Método (C-04):** evidência via `grep`/leitura do código real após `git fetch --all --prune`. Nada removido por suposição.
**Escopo removido nesta rodada:** apenas veredito **MORTO inequívoco**. Todo o resto virou **issue** rastreável para o Vitor decidir.

---

## Resumo executivo

| Veredito | Qtd | Ação |
|---|---|---|
| **MORTO inequívoco** | 2 | Removido (1 commit cada), issue fechada via `Closes` |
| **PROVÁVEL — precisa Vitor** | 8 | Issue aberta e atribuída ao Vitor, **não** removido |
| **VIVO — não mexer** | vários | Documentado abaixo (inclui "backend à frente do frontend") |

Todos os 10 caminhos fantasma viraram **issue no GitHub** (`logikos33/Recognition`), label `tech-debt` + `cleanup`.

---

## Tabela de inventário

### 🔴 MORTO inequívoco — REMOVIDO

| Item | Tipo | Evidência (comando + resultado) | Risco | Issue / Commit |
|---|---|---|---|---|
| `infra/migrations/run_migrations.py` | Script runner duplicado | Prod usa `railway_start.py::run_migrations()` (inline, glob `infra/migrations/*.sql`, re-roda idempotente — não importa este arquivo). CI usa `tests/harness/migrations/runner.py` que diz *"NÃO chamar infra/migrations/run_migrations.py"*. `grep -rn "import run_migrations\|migrations.run_migrations" tests/ services/` → **0 imports**. Único uso vivo era `AUTORUN.md` (comando de idempotência), atualizado no commit para o harness de CI. | Baixo | [#204](https://github.com/logikos33/Recognition/issues/204) · `1d3a6e34` |
| `apps/frontend/src/components/AnnotationInterface.jsx.backup` | Arquivo backup órfão | `grep -rn "jsx.backup" apps/` → **0 imports**. Ativo é `AnnotationInterface.jsx` (importado via `AnnotationInterfaceWrapper.tsx`/`AnnotationPage.tsx`/`TrainingPage.tsx`). Extensão `.backup` não entra no build Vite nem no `tsc`. Única menção: task-078 dizendo *"(ignorar `AnnotationInterface.jsx.backup`)"*. | Nulo | [#205](https://github.com/logikos33/Recognition/issues/205) · `c9bb90f0` |

### 🟡 PROVÁVEL — precisa Vitor (NÃO removido)

| Item | Tipo | Evidência | Risco de remover | Issue |
|---|---|---|---|---|
| `edge-sync-agent/app/uploader.py:45` → `/api/v1/edge/detections` | Rota fantasma | Rota não existe (`grep -rn "edge/detections" services/api/app` → 0); canônico é `/api/v1/edge/events/ingest`. `Uploader` **não** está ligado ao daemon (`main.py`: *"intentionally does NOT start the uploader loops"*), só instanciado no teste. **Repoint ingênuo não basta:** payload (`detections` vs `events`) e auth (Bearer vs device-scope RS256) divergem → seria 422. É trabalho de integração F3, não troca de URL. | Médio (repoint ingênuo cria caminho quebrado) | [#206](https://github.com/logikos33/Recognition/issues/206) |
| `devices` blueprint (`/api/devices/claim-codes`, `/api/devices/claim`) | Rota sem cliente / duplicação | `grep -rn "/api/devices\|claim-code" apps/frontend/src services/edge-sync-agent` → **0**. Só testes. Duplica o fluxo `edge/enroll` (`POST /api/v1/edge/enroll`) que é o documentado no agente. Decisão D4 = backlog. | Médio (montado + testado) | [#207](https://github.com/logikos33/Recognition/issues/207) |
| `GET /api/streams/status` | Rota sem consumidor | `grep -rn "streams/status\|/api/streams" apps/frontend/src` → nada (o FE usa `/v1/admin/observability/streams`). Comentário do próprio arquivo: *"Não há consumidor no frontend"*. **Correção de premissa:** não é público nem stub — é admin-gated e retorna dados reais de Celery. | Baixo-médio (tem testes) | [#208](https://github.com/logikos33/Recognition/issues/208) |
| `queue/tasks/versioning.py` (v1) | Versão antiga substituída | Rota `datasets/routes.py:148` importa `versioning_v2`. `.claude-architect-critique.md` + migration 096 marcam v1 como buggy. Mas v1 ainda é registrado/autodescoberto no Celery e tem testes. | Médio (registro Celery + testes) | [#209](https://github.com/logikos33/Recognition/issues/209) |
| `migrations/` (diretório raiz, 5 `.sql`) | Fallback inalcançável | `railway_start.py:63-72` faz `break` no 1º dir não-vazio; `infra/migrations/` sempre tem ~98 arquivos → `migrations/*.sql` da raiz **nunca** é alcançado. | Médio (área de migration) | [#210](https://github.com/logikos33/Recognition/issues/210) |
| `services/inference/Dockerfile:20` | Resíduo AGPL inerte | `RUN python -c "from ultralytics import YOLO..." \|\| true` — `requirements.txt` diz ultralytics removido → sempre falha, engolido por `\|\| true`. Gate de licença do CI não varre Dockerfiles. | Baixo (linha inerte) | [#211](https://github.com/logikos33/Recognition/issues/211) |
| `agent/` (dir inteiro) | Serviço arquivado + AGPL | "EPI Monitor Edge Agent" (nome antigo do produto), não referenciado por deploy/CI/compose; provável substituto = `services/edge-sync-agent/`. Contém `from ultralytics import YOLO` (`src/inference_engine.py:20`). ⚠️ Regra: **diretório arquivado não sai sem ok do Vitor.** | ⚠️ Não removido (regra de dir arquivado) | [#212](https://github.com/logikos33/Recognition/issues/212) |
| Scripts órfãos manuais | Scripts sem entrypoint | `seed_dev.py`, `staging_e2e_proof.py`, `staging_epi_convergence.py`, `staging_scale_bench.py`, `edge/soak/soak_evaluate.py`, `tools/bench_trackers.py` — grep limpo (0 referências externas). Mas são utilitários manuais/seed **deliberadamente** fora do CI; remover é curadoria, não código morto óbvio. | Baixo-médio (ferramentas de operador) | [#213](https://github.com/logikos33/Recognition/issues/213) |

### 🟢 VIVO — não mexer (documentado para evitar re-auditoria)

| Item | Por que é vivo |
|---|---|
| **Diretórios de microserviços arquivados** (`auth-service`, `camera-gateway`, `ws-gateway`, `inference-service`, `scheduler-service`, `training-service`) | **Já não existem** no repo (`ls` confirma ausência). Nada a fazer. |
| `pre-annotation-service/` | `SERVICE_TYPE=pre-annotation` válido (`railway_start.py:325`). Plugável (flag OFF), não morto. |
| Rotas "backend à frente do frontend": `site_gateways`, `monofatura`, `recorders` | Sem consumidor no FE **ainda**, mas são features recentes deliberadas (migrations 055-059, task-108, task-099) **com testes passando**. Não é código morto — é integração pendente. |
| `scenarios`, `dashboard_edge` | Têm consumidor no frontend (`useScenario.ts`, `dashboardEdgeService.ts`). |
| `infrastructure/hub/ultralytics_hub.py` | Cliente HTTP REST para `hub.ultralytics.com` — **não** importa o pacote AGPL (task-080 greenlit). Permitido. |
| `constants.py` (`ULTRALYTICS` enum), `detectors/factory.py` (string `"ultralytics"`) | Guardrails de rejeição (fail-loud), não uso do pacote. |
| Seeds e treino offline com ultralytics (`training/`, `requirements/training.*`) | Explicitamente permitidos (só caminho servido é proibido). |

**Nota (docs desatualizados, fora de escopo de remoção):** `docs/HANDOFF_CONTINUIDADE.md` e `docs/CONSOLIDACAO_DEVELOP_2026-07-18.md` ainda descrevem violações AGPL em `quality_inference.py:272,552` e `ultralytics_compat.py` que **não existem mais nesta branch** (já removidas). `docs/DATABASE.md:729` diz que `run_migrations.py` é chamado por `railway_start.py` — falso (railway_start tem função inline própria). São imprecisões de doc pré-existentes; a issue #204 registra a verdade.

---

## O que foi removido + prova de health check

| Commit | Remoção | Health check |
|---|---|---|
| `1d3a6e34` | `infra/migrations/run_migrations.py` (+ fix de 2 refs em `AUTORUN.md`) | ver abaixo |
| `c9bb90f0` | `AnnotationInterface.jsx.backup` | ver abaixo |

**Health check (pós-remoções):**
- `ruff check .` em `services/api` → **All checks passed!**
- `ruff check infra tools/agent-driver` → **All checks passed!**
- `pytest tests/harness/migrations --collect-only` → **71 tests collected**, sem erro de import (prova que nada importava o runner removido).
- Grep de referências pendentes aos arquivos removidos → **0**.
- **Frontend `tsc` e suite `pytest` completa:** rodam no CI do PR. Localmente: `apps/frontend/node_modules` ausente e a suite de `services/api` exige DB/Redis. As remoções são estruturalmente ortogonais a esses alvos (um script CLI não-importado + um `.backup` que não é input de `tsc`/Vite), então o risco é nulo por construção; o CI confirma.

As remoções não tocaram nada em `services/api/app` runtime, então a suite de API é ortogonal.

---

## Pendências do Vitor (recomendação por item)

1. **#206 uploader `/edge/detections`** — não fazer troca ingênua de URL; dobrar em F3 (repoint + reshape de payload + device-scope auth + teste na rota real).
2. **#207 devices claim-code** — decidir: matar em favor de `edge/enroll` (D4) ou manter para caso futuro.
3. **#208 `/api/streams/status`** — propor remoção ou consolidar em `/v1/admin/observability/*`.
4. **#209 versioning v1** — deprecar (remover v1 + testes) ou manter como fallback.
5. **#210 `migrations/` raiz** — remover o diretório + a linha de fallback (deixar só `infra/migrations/`).
6. **#211 Dockerfile inference** — remover a linha `RUN ... ultralytics ...` (baixo risco, remove resíduo AGPL de build).
7. **#212 `agent/`** — confirmar se está arquivado (substituído por `edge-sync-agent`) e remover o dir inteiro (elimina o AGPL junto).
8. **#213 scripts órfãos** — triar cada um: manter utilitário útil vs. remover resíduo de campanha encerrada.

---

## Confirmação de escopo

- ✅ Trabalho em worktree de `origin/develop`, branch `claude/dead-code-audit-e1a168`.
- ✅ **Nada promovido para `staging` nem `main`.**
- ✅ Diretórios arquivados (`agent/`) **não removidos** — só propostos (issue #212).
- ✅ Cada remoção = 1 commit revertível, conventional commit `chore(cleanup): ...`.
- ✅ 10 caminhos fantasma = 10 issues rastreáveis (#204–#213).
