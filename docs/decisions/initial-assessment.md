# Initial Assessment — EDGE_DEPLOYMENT_PLAN
**Data:** 2026-05-27
**Branch:** staging → develop (criada nesta etapa)
**Preparado por:** Claude Code (diagnóstico pré-execução)

---

## A. Inventário Real do Código

### Estrutura geral do repositório

```
/ (raiz do repo)
├── backend/                    → services/api/ (Fase 0)
├── frontend/                   → apps/frontend/ (Fase 0)
├── landing-page/               → apps/landing/ (Fase 0)
├── pre-annotation-service/     → não mapeado no plano — destino a definir
├── painel-adm/                 → REPOSITÓRIO GIT ANINHADO (.git próprio)
│   ├── auth-service/           → services/auth/ [DEPRECATED]
│   ├── camera-gateway/         → services/camera-gateway/
│   ├── inference-service/      → services/inference/
│   ├── ws-gateway/             → services/ws-gateway/
│   ├── scheduler-service/      → services/scheduler/
│   ├── training-service/       → services/training/
│   ├── backend/                → DESCONHECIDO — Pre-4 investigation
│   ├── frontend/               → DESCONHECIDO — Pre-4 investigation
│   ├── migrations/             → DESCONHECIDO — Pre-4 investigation
│   ├── pre-annotation-service/ → DESCONHECIDO — Pre-4 investigation
│   └── agent/                  → DESCONHECIDO — Pre-4 investigation
├── docs/                       → 10 arquivos existentes (+ decisions/ criado agora)
├── EDGE_DEPLOYMENT_PLAN.md     → raiz (mover para docs/ ou manter)
└── CLAUDE.md                   → DESATUALIZADO (diz última migration é 012)
```

### Backend — api-v3 (backend/)

| Componente | Detalhes |
|---|---|
| Blueprints | 18 ativos: admin, alerts, auth, cameras, chat, counting, dashboard, frames, fueling, health, modules, operations, quality, reports, rules, storage, streams, training, verification, videos |
| Celery tasks | 21 tasks em 9 arquivos, 6 queues distintas |
| Socket bridge | `backend/app/core/socket_bridge.py` — Redis psubscribe(det:*, training:*, quality:*, operations:*) → SocketIO |
| Migrations | **41 migrations** (001–041). Última: `041_update_fueling_classes.sql` |
| Framework | Flask + psycopg2 (sem ORM) + RealDictCursor |
| Multi-tenant | tenant_id em todas as queries (exceto 2 débitos P3 em frame_repository.py) |

### Banco de dados — 52 tabelas

Tabelas relevantes para edge:
- `ip_cameras` — tem `location VARCHAR(300)`, sem `site_id`
- `worker_registry` — GPU workers on-premise (tailscale_ip, gpu_model, vram, last_heartbeat_at)
- `system_versions` — checkpoints de config da plataforma (config_snapshot JSONB)
- `models` — tabela canônica de modelos (multi-tenant, tem r2_key)
- `trained_models` — legacy V1 (user-scoped, sem r2_key)
- `quality_stations` — tem coluna location/node
- `operations` — tem coluna device

### Migrations a criar (numeração correta)

| Número correto | Nome | Plano original |
|---|---|---|
| 042 | edge_sites.sql | 013 (plano) |
| 043 | device_tokens.sql | 014 (plano) |
| 044 | site_id_columns.sql | 015 (plano) |
| 045 | deployment_mode.sql | 016 (plano) |
| 046 | event_origin.sql | **NOVO** (ADR-0013) |
| 047 | processing_mode.sql | **NOVO** (ADR-0013) |

### Microsserviços (painel-adm/)

| Serviço | LOC | Dockerfile | railway.toml | Status |
|---|---|---|---|---|
| auth-service | 245 | ✓ | ✓ | **DEPRECATED** (não integrado ao frontend) |
| camera-gateway | 457 | ✓ | ✓ | Real, 100% implementado |
| inference-service | 475 | ✓ | ✓ | Real, 100% implementado |
| ws-gateway | 218 | ✓ | ✓ | Real, 100% implementado |
| scheduler-service | 182 | ✓ | ✗ | Real, sem railway.toml |
| training-service | 443 | ✓ | ✓ | Real, 100% implementado |

### Frontend (frontend/)

- Auth: `useAuth.ts` → `api.ts` → API-V3 (backend/) — auth-service nunca chamado
- Módulo Quality: **48 componentes**, em produção com cliente real
- Chat: `ChatFAB.tsx` — feature experimental, usa `fetch()` raw (não api.ts wrapper)
- Módulo Fueling: placeholder (sem implementação real)

### Celery Tasks — 21 total

| Classificação | Count |
|---|---|
| **EDGE** (runtime real-time) | 6 |
| **CLOUD** (training, scheduling, maintenance) | 15 |
| **KILL** (obsoletas) | 0 |

Ver detalhes em `docs/decisions/celery-tasks-migration.md`.

### Infraestrutura

- CI/CD: **não existe** `.github/workflows/` — deploy via Railway push
- CLAUDE.md: desatualizado (migration "012" vs real "041")
- Branch atual: `staging`

---

## B. Conflitos Identificados e Resoluções

| ID | Conflito | Resolução | Registro |
|----|---------|-----------|---------|
| A | site_id em tabelas | Sem conflito — nenhuma tabela tem site_id, migrations 042–045 são puramente aditivas | log.md |
| B | worker_registry vs edge_sites | Conceitos distintos, coexistem. Sem refatoração. | log.md |
| C | system_versions vs edge_version | Sem conflito. edge_version vai em edge_sites. | log.md |
| D | 21 tasks — classificação | 6 EDGE, 15 CLOUD, 0 KILL. Shadow mode para cutover. | celery-tasks-migration.md + ADR-0013 |
| E | Numeração de migrations | 013-016 → 042-045. Migrations 046-047 adicionadas. | log.md + ADR-0013 |
| G | Dual auth | API-V3 ativa, auth-service deprecated. | log.md |
| H | frames/routes.py vazio | Confirmado vazio. Dead code documentado. | log.md |
| I | Chat/assistant | Feature experimental preservada. Não bloqueia edge. | log.md + OQ-001 |
| J | models vs trained_models | `models` canônica. Bug fix em quality_inference.py:90. | ADR-0012 |
| K | painel-adm/.git aninhado | Pre-4 investigation → backup → rm -rf .git → git mv. | ADR-0011 |
| L | Arquitetura_*.md inexistentes | Removidos da Fase 0. Mover EDGE_AGENT_ARCHITECTURE.md. | log.md |
| M | .github/workflows/ inexistente | Criar do zero na Fase 0 (não "configurar"). | log.md |
| N | painel-adm/ conteúdo extra | Pre-4 investigation obrigatória. Aguarda decisão de Vitor. | OQ-002 |

---

## C. ADRs Criados Nesta Etapa

| ADR | Título | Status |
|---|---|---|
| ADR-0011 | Como tratar painel-adm/ como repositório git aninhado | Aceito |
| ADR-0012 | Tabela canônica de modelos — `models` vs `trained_models` | Aceito |
| ADR-0013 | Shadow Mode e Cutover Gradual Edge→Cloud | Aceito |

ADRs 0001–0010 (do plano original) serão escritos na Fase 0.

---

## D. Decisões no log.md

Ver `docs/decisions/log.md` — 16 decisões registradas em 2026-05-27.

---

## E. Resumo do plan-review.md

**Mudanças obrigatórias aplicadas:**
1. Migrations 013–016 → 042–045 (+ 046–047 novas)
2. painel-adm/.git: Pre-4 investigation + backup + rm -rf antes dos git mv
3. Arquitetura_*.md removidos da Fase 0 (não existem)
4. Pre-4 investigation obrigatória antes da Fase 0

**Sugestões incorporadas:**
- auth-service marcado deprecated desde o início
- Fase -1 / pre-flight adicionada (Pre-1 a Pre-4)
- Fase S1 deve incluir fixes de tenant_id documentados
- Fase 6.5 (Shadow Cutover) adicionada ao plano
- docker-compose.dev.yml com inference em modo ultralytics por padrão

**Ver detalhes completos:** `docs/decisions/plan-review.md`

---

## F. Itens Bloqueantes

| OQ | Status | Próxima ação |
|----|--------|-------------|
| OQ-001 Chat/assistant | ✅ Resolvida — manter experimental | Nenhuma |
| OQ-002 painel-adm/ internals | ⏳ Pendente | Claude executa Pre-4, documenta, PARA |
| OQ-003 Tasks EDGE | ✅ Resolvida — shadow mode (ADR-0013) | ADR criado |
| OQ-004 `models` canônica | ✅ Resolvida — `models` confirmada | ADR-0012 criado |
| OQ-005 Branch base | ✅ Resolvida — develop from staging | Branch criada |

---

## G. Plano de Execução Revisado

### Branch strategy (aprovada por Vitor)
```
main (produção, protegida)
  └── staging (auto-deploy Railway)
        └── develop (nova, criada agora)
              ├── feature/preflight-fixes  (Pre-1 a Pre-4)
              └── feature/phase-0-reorg   (Fase 0)
```

---

### PRÉ-FLIGHT — branch: feature/preflight-fixes

**Pre-1: Fix bug quality_inference.py:90** ✅ Aprovado para execução
- Arquivo: `backend/app/infrastructure/queue/tasks/quality_inference.py:90`
- Mudança: `training_models` → `models`
- Commit: `fix(quality): corrigir referência tabela training_models → models`
- Critério: `grep -r "training_models" backend/` retorna zero resultados

**Pre-2:** (reservado)

**Pre-3: chat/assistant** — sem ação (OQ-001: preservar como está)

**Pre-4: Investigação painel-adm/** ⏳ BLOQUEIA FASE 0
- Executar diff de painel-adm/backend/ vs backend/, painel-adm/frontend/ vs frontend/, painel-adm/migrations/ vs infra/migrations/
- Inspecionar painel-adm/landing-page/, pre-annotation-service/, agent/
- Documentar em `docs/decisions/painel-adm-investigation.md` com recomendação por diretório (ARCHIVE/DELETE/MERGE)
- **PARA. Aguarda aprovação de Vitor.**

---

### FASE 0 — branch: feature/phase-0-reorg (após Pre-4 aprovada)

Subtarefas em ordem (commit atômico por subtarefa):

| # | Ação | Critério |
|---|------|---------|
| 0a | Backup painel-adm/.git + rm -rf painel-adm/.git + git add painel-adm/ | `git ls-files painel-adm/` mostra arquivos |
| 0b | Criar estrutura: services/, apps/, shared/, deployments/, docs/architecture/, docs/runbooks/, docs/security/, infra/, deepstream/, models/manifests/, tests/harness/ | Todos os dirs existem |
| 0c | `git mv backend/ services/api/` + atualizar railway.toml + Dockerfile | Build local do serviço funciona |
| 0d | `git mv painel-adm/camera-gateway/ services/camera-gateway/` etc. (um por serviço) | Cada serviço: Dockerfile builda |
| 0e | `git mv painel-adm/auth-service/ services/auth/` + SDD.md DEPRECATED | Sem erros de path |
| 0f | `git mv frontend/ apps/frontend/` + atualizar vite.config.ts, tsconfig.json | `npx tsc --noEmit` sem erros |
| 0g | `git mv landing-page/ apps/landing/` | Sem erros |
| 0h | Mover migrations para infra/migrations/ + atualizar railway_start.py | Migrations encontradas no novo path |
| 0i | Mover docs/EDGE_AGENT_ARCHITECTURE.md → docs/architecture/ | Arquivo no novo path |
| 0j | Atualizar todos os Dockerfiles (COPY/WORKDIR) | Todos buildam localmente |
| 0k | Atualizar todos os railway.toml (paths de serviços) | Sem referências a paths antigos |
| 0l | Atualizar CLAUDE.md: "última migration é 041" | CLAUDE.md correto |
| 0m | Escrever 10 ADRs em docs/decisions/adr/ (0001–0010 do plano) | 10 arquivos criados |
| 0n | Escrever GSD em docs/architecture/GSD.md | Arquivo criado |
| 0o | Criar AGENT.md raiz + AGENT.md em cada services/*/ | 7 arquivos |
| 0p | Criar SDD.md esqueleto em cada services/*/ | 7 arquivos |
| 0q | Criar docker-compose.dev.yml (inference com INFERENCE_ENGINE=ultralytics, sem profile gpu) | `docker compose up -d` sobe sem erro |
| 0r | Criar .github/workflows/ci.yml (ruff + pytest + tsc --noEmit) | CI verde |
| 0s | Criar .github/workflows/security-scan.yml (gitleaks) | Workflow criado |
| 0t | Atualizar .gitignore conforme plano S0 | .env, *.pem, secrets/, *.sqlite listados |

Critérios de aceitação da Fase 0:
- [ ] `git log --follow services/api/app/core/auth.py` mostra histórico
- [ ] `grep -r "painel-adm" */Dockerfile */railway.toml` retorna zero
- [ ] `docker compose up -d` sobe sem erro
- [ ] CI verde no primeiro push para feature/phase-0-reorg
- [ ] 10 ADRs + GSD + 7 SDDs + AGENT.md raiz + 7 AGENT.md escritos

---

### FASES 1–10
Conforme plano original atualizado, com:
- Migrations 042–047 (não 013–016)
- Fase 6.5 (Shadow Cutover) entre Fase 6 e Fase 7
- Tasks EDGE no cloud Celery durante Fases 0–5

---

## H. Artefatos Criados Nesta Etapa

```
docs/decisions/
├── log.md                             ✅ criado
├── open-questions.md                  ✅ criado
├── plan-review.md                     ✅ criado
├── celery-tasks-migration.md          ✅ criado
├── oq-responses.md                    ✅ criado
├── initial-assessment.md              ✅ (este arquivo)
└── adr/
    ├── 0011-painel-adm-nested-git.md  ✅ criado
    ├── 0012-models-vs-trained-models.md ✅ criado
    └── 0013-shadow-mode-cutover.md    ✅ criado
```

EDGE_DEPLOYMENT_PLAN.md: atualizado com migrations 042–047 e Fase 6.5.
