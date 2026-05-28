# painel-adm/ — Investigação da Estrutura de Branch

**Data:** 2026-05-27
**Branch:** feature/decisions-correction
**Motivação:** Checklist do PR #3 revelou que `git ls-files painel-adm/camera-gateway/` retorna vazio em develop. Investigação determina por quê e qual impacto isso tem na Fase 0.

---

## 1. Resultado da Investigação

### 1.1 O que é `painel-adm/` de verdade

`painel-adm/` é uma **combinação de duas coisas distintas**:

| Camada | O que é | Estado |
|--------|---------|--------|
| **Git tree (staging/develop)** | Gitlink `160000 commit a24fe5f` | Submodule incompleto — sem `.gitmodules` |
| **Filesystem** | Git linked worktree na branch `painel-adm` | Local only — não existe em origin |

**Gitlink** (modo `160000`) aparece em `git ls-tree staging` e `git ls-tree develop`:
```
160000 commit a24fe5f9e3325881e6808ce8b8e03659fa318a8e    painel-adm
```

Sem `.gitmodules` correspondente — o arquivo não existe em staging nem em develop. Isso é um estado de submodule incompleto: git sabe que existe um gitlink, mas não sabe de onde clonar.

### 1.2 Branch `painel-adm` (local only)

- **Existe:** apenas localmente — não foi pushed para origin
- **Último commit:** `a24fe5f chore(savepoint): pre-quality-module implementation checkpoint` (2026-04-16)
- **Conteúdo:** snapshot completo do projeto pré-módulo-quality
- **Merge base com staging:** `4190ec1` (divergiram em abril/2026)

Árvore da branch `painel-adm`:
```
auth-service/
backend/
camera-gateway/
docs/
frontend/
inference-service/
landing-page/
logs/
migrations/
pre-annotation-service/
scheduler-service/
storage/
training-service/
ws-gateway/
agent/
scripts/
requirements/
railway.toml
railway_start.py
nixpacks.toml
...
```

### 1.3 O que staging tem que painel-adm não tem

staging evoluiu com o módulo Quality enquanto painel-adm ficou frozen:
- `QUALITY_MODULE_CHANGELOG.md` — em staging, não em painel-adm
- `backend/` com 41 migrations — staging tem mais 15+ migrations que painel-adm
- Auth, SocketIO, rate limiting, multi-tenant — staging mais avançado

### 1.4 Serviços removidos de staging

Os serviços abaixo foram **explicitamente removidos de staging** com justificativa:

| Serviço | Commit de remoção | Justificativa |
|---------|-------------------|---------------|
| auth-service | `f547609` (2026-05-08) | "Funcionalidade 100% absorvida por api-v3 + celery-worker. Libera ~1GB RAM e ~20 conexões PostgreSQL/Redis no Railway." |
| camera-gateway | `f547609` (2026-05-08) | idem |
| ws-gateway | `f547609` (2026-05-08) | idem |
| training-service | `f547609` (2026-05-08) | idem |
| scheduler-service | `8dfeae9` (2026-05-08) | "deprecated, substituído pelo Celery Beat no worker" |
| pre-annotation-service | `e5582c9` | "DINO+SAM nunca usado em prod" |

**Conclusão crítica:** esses serviços não foram arquivados — foram **deletados intencionalmente** do branch principal porque suas responsabilidades foram absorvidas pelo monolito api-v3.

### 1.5 `inference-service` — caso especial

`inference-service` tem **SHA idêntico** em painel-adm e staging:
```
040000 tree 229b10a89a4a58d3d1cfe8b56b222c0dd4b43192    inference-service
```
Está em staging e nunca foi removido. É o único serviço dos originais que sobreviveu.

---

## 2. Impacto na Fase 0 do EDGE_DEPLOYMENT_PLAN

### 2.1 O plano assumia o que não existe

O plano original descrevia:
```bash
git mv painel-adm/camera-gateway/ services/camera-gateway/
git mv painel-adm/inference-service/ services/inference/
git mv painel-adm/ws-gateway/ services/ws-gateway/
# etc.
```

Isso é **impossível** por dois motivos:
1. Em `develop`, `painel-adm/` é um gitlink — `git mv` não funciona em gitlinks
2. `camera-gateway`, `ws-gateway`, `auth-service`, `scheduler-service`, `training-service` não existem em `staging`/`develop` — foram deletados intencionalmente

### 2.2 O que isso muda na Fase 0

**Os `git mv` dos serviços deletados NÃO acontecem.** Eles foram deliberadamente removidos.

Em vez disso, Fase 0 reorganiza o que EXISTE em staging/develop:
- `backend/` → `services/api/` (`git mv` — funciona, está em staging)
- `frontend/` → `apps/frontend/` (`git mv` — funciona)
- `landing-page/` → `apps/landing/` (`git mv` — funciona)
- `inference-service/` → `services/inference/` (`git mv` — funciona, está em staging)

Para os novos serviços de edge (`services/camera-gateway/`, `services/ws-gateway/`, `services/training/`):
- **Serão criados do zero** na Fase 3 (Refactor dos Microsserviços)
- O código da branch `painel-adm` serve como **referência de implementação** (leitura), não como fonte de `git mv`

### 2.3 Gitlink precisa ser removido da tree de develop

`develop` herdou o gitlink de staging. Antes da Fase 0, o gitlink precisa ser limpo:

```bash
git rm --cached painel-adm          # remove o gitlink do index
git worktree remove painel-adm      # remove o linked worktree
# painel-adm/ some do filesystem, branch painel-adm continua existindo
git commit -m "chore: remove painel-adm gitlink — branch preserved locally"
```

Após isso:
- `painel-adm/` não aparece mais em develop
- Branch `painel-adm` continua existindo localmente como referência
- O conteúdo fica acessível via `git show refs/heads/painel-adm:<arquivo>`

---

## 3. Recomendações por Diretório (painel-adm branch)

| Diretório | Recomendação | Justificativa |
|-----------|-------------|---------------|
| `camera-gateway/` | **REFERÊNCIA** — reescrever em Fase 3 | Foi deletado de staging em maio/2026 |
| `ws-gateway/` | **REFERÊNCIA** — reescrever em Fase 3 | Idem |
| `training-service/` | **REFERÊNCIA** — reescrever em Fase 3 | Idem |
| `scheduler-service/` | **ARCHIVE** — Celery Beat substituiu | Funcionalidade já em api-v3/worker |
| `auth-service/` | **ARCHIVE** — api-v3 substituiu | Sem multi-tenant, nunca integrado ao frontend |
| `pre-annotation-service/` | **ARCHIVE** — nunca usado em prod | DINO+SAM removido por Vitor |
| `inference-service/` | **IGNORAR** — cópia idêntica ao staging | Mesmo SHA em ambas as branches |
| `backend/` | **IGNORAR** — versão mais antiga | staging tem 15+ migrations a mais |
| `frontend/` | **IGNORAR** — versão mais antiga | staging tem módulo quality + mais |
| `migrations/` | **IGNORAR** — subconjunto das 41 migrations | staging tem mais |
| `agent/` | **VERIFICAR em Pre-4** — mesmo SHA que staging? | Não verificado ainda |

---

## 4. Impacto nos ADRs

### ADR-0011 precisa de atualização major

A versão atual de ADR-0011 (pós-correção desta branch) já diz `git worktree remove`, mas ainda menciona incorporar serviços via `git checkout painel-adm -- camera-gateway/`. Isso está **errado**: camera-gateway não deve ser incorporado via checkout, deve ser **reescrito** na Fase 3.

**Atualização necessária:**
- Remover procedimento de `git checkout painel-adm -- <dir>`
- Substituir por: remover gitlink + worktree, manter branch como referência local
- Explicar que os serviços REMOVED_FROM_STAGING são referência apenas

### EDGE_DEPLOYMENT_PLAN Fase 0 precisa de revisão

Fase 0 Subtarefa 0d atualmente diz:
```
git mv painel-adm/camera-gateway/ services/camera-gateway/ etc.
```

Isso não acontece. Os `git mv` da Fase 0 são apenas:
- `backend/` → `services/api/`
- `inference-service/` → `services/inference/`
- `frontend/` → `apps/frontend/`
- `landing-page/` → `apps/landing/`

Serviços de edge novos (`camera-gateway`, `ws-gateway`, `training`) são criados do zero na Fase 3.

---

## 5. Questões para Vitor (OQ-006)

**OQ-006:** Confirmação da estratégia para os serviços removidos de staging

- A) **Reescrever do zero** na Fase 3 (ignorar código da branch painel-adm)
- B) **Portar da branch painel-adm** como ponto de partida na Fase 3 (adaptar, não reescrever)
- C) **Outro** — especificar

**Impacto na decisão:**
- Opção A: Fase 0 apenas remove o gitlink. Fase 3 cria serviços novos.
- Opção B: Fase 0 remove o gitlink, Fase 3 usa `git show refs/heads/painel-adm:camera-gateway/` como base de cada serviço.

**Não bloqueia PR #3** — o PR só documenta. Bloqueia o início da Fase 0 real.

---

## 6. Artefatos desta Investigação

- Este arquivo: `docs/decisions/painel-adm-branch-investigation.md`
- ADR-0011 (atualizado): ainda precisa de revisão para refletir §4 acima
- EDGE_DEPLOYMENT_PLAN.md: Fase 0 subtarefa 0d precisa de revisão
