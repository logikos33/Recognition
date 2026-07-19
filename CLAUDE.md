# CLAUDE.md

> **Princípios inegociáveis:** ver [`/constitution.md`](./constitution.md) (C-01..C-08). Em caso de conflito entre este arquivo e a constitution, **a constitution prevalece**.
>
> **Como atuar (diretriz operacional):** ver [`docs/DIRETRIZ_OPERACAO_CLAUDE_CODE.md`](./docs/DIRETRIZ_OPERACAO_CLAUDE_CODE.md) — fluxo develop→staging→main, equalização de ambientes, higiene de branch pós-merge, ADRs, evidência de PR e histórico. Precedência: **constitution → diretriz → este arquivo**.
>
> **Regra C-04 (a mais importante deste arquivo):** valide o estado real no código/git/banco. **Nunca confie neste arquivo nem em memória.** Este documento já esteve gravemente desatualizado uma vez (descrevia `backend/`, `frontend/` e 13 microserviços que não existem mais).
>
> **Última reconciliação com o repo:** 2026-07-14.

This file provides guidance to Claude Code when working with code in this repository.

---

## Identidade do Projeto

**Recognition** (nome anterior: EPI Monitor V2 / EPI-CATH-V2) — SaaS multi-tenant de visão computacional sobre CFTV. Desenvolvido por Vitor Emanuel (Logikos).

**O produto não é um detector fixo: cada cliente treina o próprio modelo.** Essa é a proposta de valor central — não implemente nada que assuma um modelo único global.

- **Módulos:** EPI/Segurança, Qualidade, Carga-descarga/Contagem
- **Cliente âncora:** RVB Isolantes (Blumenau/SC) — módulo EPI, ~28 câmeras
- **White-label** por tenant (ADR-0035)

**Detector servido = ONNX Apache 2.0 (YOLOX / RF-DETR).**
**ZERO ultralytics/AGPL no caminho servido.** Há gate de licença no CI (task-055a). Ultralytics só é aceitável em scripts de treino offline, nunca no que é servido ao cliente.

---

## Deploy real (Railway)

`railway_start.py` roteia por `SERVICE_TYPE`. **Só existem 4 valores válidos:**

| `SERVICE_TYPE` | Serviço |
|---|---|
| `api` (padrão) | Flask + SocketIO, gunicorn/eventlet — o **monolito** |
| `worker` / `celery-worker` | Celery worker (todas as filas) |
| `pre-annotation` | DINO + SAM — **flag OFF**, plugável, não ativo |
| `landing-page` | Astro estático |

Mais `frontend` (React/Vite), `PostgreSQL` e `Redis` (plugins Railway).

**Os microserviços NÃO existem mais.** `auth-service`, `camera-gateway`, `ws-gateway`, `inference-service`, `scheduler-service`, `training-service` foram **absorvidos pelo monolito `api-v3` em mai/2026** (ADR-0014). Os diretórios remanescentes na raiz são histórico arquivado — não são deploy ativo. Não os referencie como se estivessem rodando.

**URLs produção**
- API: `https://api-v3-production-2b22.up.railway.app`
- Frontend: `https://frontend-production-bf96.up.railway.app`
- Landing: `https://landing-page-production-b659.up.railway.app`

---

## Branches

```
worktree (de origin/develop)  →  develop  →  staging  →  main
```

- **`staging` = PRODUÇÃO** (auto-deploy Railway). **NÃO é `main`.**
- `develop` = trabalho ativo. `main` = branch estável / gráfico de contribuições.
- `develop→staging→main` são **gates humanos**.
- Merge para `staging`/`main` = **merge commit, NUNCA squash** (runbook `docs/runbooks/GITHUB_CONTRIBUTIONS_MERGE_MAIN.md`).
- **Trabalho novo em worktree a partir de `origin/develop`** — nunca num checkout `wip/*`.

> ⚠️ **Estado em 2026-07-18 (medido via `gh api .../compare`, NÃO por ref local — que estava stale/quebrada):** a
> situação do "2026-07-13" **se inverteu**. A troca ultralytics→ONNX, test console e harness de escala **já foram
> mergeados na `develop`** (PRs #168–#196). Números reais: **`develop` está 108 commits À FRENTE de `staging`**
> (staging só 2 à frente da develop) e **114 à frente de `main`**. As únicas divergências staging/main→develop são
> hotfixes de CI (`remover job license-gate duplicado no ci.yml`) e a renumeração de migration-052 (#159 no main),
> não back-portados. Plano: `docs/EQUALIZACAO_BRANCHES_2026-07-18.md`. **Regra:** estado de branch = `git fetch`
> fresco + `gh`, nunca ref local em cache (DIRETRIZ §6.1).

---

## Estrutura real do repositório (monorepo — ADR-0010)

```
services/
  api/app/                 # ← O BACKEND. Flask + SocketIO (NÃO é backend/)
    api/v1/                # blueprints: admin alerts auth branding cameras chat
                           # counting dashboard devices edge edge_commands
                           # edge_events events feedback frames fueling health
                           # models modules notifications operations quality
                           # reports retention roles rules scenarios
                           # site_gateways storage streams training verification videos
    core/                  # auth.py (get_tenant_schema/get_tenant_id), responses, exceptions
    domain/                # models/ + services/
    infrastructure/        # database/ (connection, repositories) + storage/ (R2)
  inference/               # engine de inferência (DeepStream / ONNX)
  edge-sync-agent/         # sincronização edge→cloud (buffer SQLite + backoff)

apps/
  frontend/src/            # ← O FRONTEND. React 18 + TS + Vite + vanilla-extract
  landing/                 # Astro

infra/migrations/          # ← AS MIGRATIONS. NNN_nome.sql (última: 083)
deepstream/                # pipelines epi/ quality/ fueling/ shared/
docs/decisions/adr/        # ADRs 0001–0041
requirements/              # base, api, worker, celery-worker, inference, training, pre-annotation
railway_start.py           # router por SERVICE_TYPE
```

**Os três erros que este arquivo já cometeu — não repita:**
- ❌ `backend/app/` → ✅ `services/api/app/`
- ❌ `frontend/` → ✅ `apps/frontend/`
- ❌ `backend/app/infrastructure/database/migrations/` → ✅ `infra/migrations/`

---

## Comandos de Desenvolvimento

```bash
# API local
cd services/api
export SERVICE_TYPE=api DATABASE_URL=... REDIS_URL=... JWT_SECRET_KEY=...
python3 ../../railway_start.py

# Frontend
cd apps/frontend && npm run dev

# Lint / types
cd services/api && python -m ruff check .
cd apps/frontend && npx tsc --noEmit

# Migrations (Railway roda automaticamente no startup do SERVICE_TYPE=api)
psql $DATABASE_URL -f infra/migrations/NNN_nome.sql

# Smoke test antes de merge
./scripts/smoke_test.sh https://api-v3-production-2b22.up.railway.app

# Deploy = push
git push origin staging
```

---

## Arquitetura ponta a ponta

**Usuário → Cloud.** Browser → React (`apps/frontend`) → Flask REST + SocketIO (`services/api`) no Railway. JWT com claims `tenant_id`, `tenant_schema`, `role`, `modules_enabled`.

**Cloud → Edge.** Mini PC **NVIDIA Jetson Orin NX Super 16GB** no site do cliente. Enrollment com token one-time → device recebe **JWT RS256 com escopos** (ADR-0019). Rede: **MikroTik + WireGuard hub-and-spoke, discagem outbound** (ADR-0020) — as câmeras Hikvision/Intelbras **travam por lockout anti-brute-force** se expostas; port-forward é proibido por design.

**Edge → inferência.** MediaMTX faz proxy RTSP (ADR-0009) → DeepStream consome nativo via `nvurisrcbin`. Backend selecionável por `INFERENCE_ENGINE` (ADR-0001/0015). ADR-0040 (*proposta*, não aceita) quer ancorar o edge em Jetson Platform Services.

**Edge → Cloud.** Detecções em Redis pub/sub `detections:{camera_id}` (ADR-0002) → `edge-sync-agent` (buffer SQLite + backoff) → API → SocketIO → browser.

**Evidência.** Clipes de ~20-30s ao redor do evento (ADR-0033) sobem para **Cloudflare R2, cloud-first** (ADR-0028). O Orin tem **128GB = SO + app, NÃO é destino de armazenamento**. Buffer local é transitório, com **reserva de disco intocável** — disco cheio = intertravamento do device.

**`DEPLOYMENT_MODE`:** `edge` (produção) | `cloud_only` (flag suportada, sem cliente).

---

## Padrões Críticos

### Multi-tenancy: SCHEMA-PER-TENANT (ADR-0004)

Não é "coluna `tenant_id` em tudo". São **dois padrões coexistindo** — saiba qual usar:

| Onde | Padrão | Exemplos |
|---|---|---|
| `public.*` | coluna `tenant_id NOT NULL` | `tenants`, `edge_sites`, `device_tokens`, `ip_cameras`, `modules`, `operations`, `alerts` |
| `{tenant_schema}.*` | **sem** `tenant_id` — o schema É o isolamento | `cameras`, `models`, `frames`, `detections`, `training_jobs`, `quality_inspections` |

`get_tenant_schema()` e `get_tenant_id()` em `services/api/app/core/auth.py`.

**ADR-0017: sem fallback silencioso.** Token sem claim de tenant → falha. Não reintroduza defaults como `"public"` ou o tenant UUID zerado — isso é vetor de vazamento cross-tenant. **Cross-tenant → 404** (C-01), nunca 403 (não vaze existência).

### Database
- `psycopg2` direto, `RealDictCursor`. **Sem SQLAlchemy, sem ORM.**
- `DatabasePool.get_instance()` — nunca conexão avulsa.
- Todo SQL nos repositories.
- **Zero f-string com input do usuário em SQL** — inclusive em `SET search_path` (já foi vetor de injection real).

### API Response
```python
from app.core.responses import success, error
return success({"cameras": items})     # {"success":true,"message":"OK","data":{...}}
return error("Câmera não encontrada", 404)  # {"success":false,"error":"..."}
```

### Frontend
- `api.ts` retorna o envelope completo `{success, message, data}` (confirmado em `app/core/responses.py`) — **não** `{status, data}`.
- TypeScript strict. Zero `any` implícito.
- Bounding boxes: `pointerEvents: 'none'`, zero `onClick`.

### Qualidade
- Zero `print()` no backend — `logging.getLogger(__name__)`.
- `CORS(app, origins=config.CORS_ORIGINS)` — nunca `CORS(app)` bare.
- `RTSPUrlValidator` antes de qualquer URL chegar ao FFmpeg.

---

## Migrations — forward-only

1. Última: `ls infra/migrations/*.sql | sort | tail -1` (atualmente **083**)
2. **Permitido:** `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`
3. **NUNCA:** `DROP`, `ALTER COLUMN TYPE`, `DELETE FROM`, `TRUNCATE`
4. Nunca edite uma migration já aplicada — crie uma nova para corrigir
5. Rodar o **harness 2x** (idempotência). Sem exceção — "é só uma coluna" já quebrou deploy antes (ADR-0021: colisão de numeração derrubou o startup da API)
6. Nova tabela: decida `public` (com `tenant_id`) vs `{tenant_schema}` conforme ADR-0016

**Checklist pós-migration:** model → repository → service → route → types do frontend → testes → `docs/DATABASE.md`.

**Separe atomicamente:** migration e mudança de lógica **nunca no mesmo commit**.

---

## Anti-padrões (NÃO fazer)

- Inferir schema de migrations antigas / logs / memória em vez de consultar o banco real ou rodar o harness
- Referenciar tabela/coluna que não existe no schema final
- Tratar os microserviços arquivados como se estivessem em produção
- Colocar ultralytics (AGPL) no caminho servido
- Reintroduzir fallback de tenant em `auth.py`
- Trabalhar direto num checkout `wip/*` em vez de worktree de `origin/develop`

---

## Classificação de Impacto

| Nível | Escopo | Verificação |
|---|---|---|
| P0-CRÍTICO | Multi-serviço, risco de dados | Manual + testes + e2e |
| P1-ALTO | Serviço único, user-facing | Testes obrigatórios |
| P2-MÉDIO | Refactor interno | Self-review |
| P3-BAIXO | Documentação | Nenhuma |

Classificar **antes** de mudar. Verificação é proporcional ao nível. `risk:security` **para a fila** para revisão humana.

---

## Commits

```
feat(scope): descrição
fix(scope): descrição
refactor(scope): sem mudança de comportamento
```

Scopes: `api, frontend, migration, railway, edge, inference, training, landing, cameras, alerts, modules, quality, counting`

---

## Session Protocol

### Iniciando Sessão
0. Ler [`docs/DIRETRIZ_OPERACAO_CLAUDE_CODE.md`](./docs/DIRETRIZ_OPERACAO_CLAUDE_CODE.md) — **como atuar** (fluxo, equalização, higiene de branch, ADRs, evidência, histórico)
1. Ler CLAUDE.md — **e verificar contra o repo real** (C-04)
2. `git branch --show-current` — está em worktree de `origin/develop`?
3. Health check: `cd services/api && python -m pytest tests/ -q`

**Antes de commitar:** testes da área afetada · `npx tsc --noEmit` (se front) · `ruff check .` (se back) · conventional commit.

**Definição de concluído:** compila · zero lint · commit no padrão · push · health check 200.

---

## Contexto vivo (leia se for retomar o projeto)

- `docs/HANDOFF_CONTINUIDADE.md` — estado, decisões pendentes, próximo passo
- `docs/PLANO_EXECUCAO_MIGRACAO_V3.md` — plano-mestre em 6 fases
- `docs/API_CONTRACT_MAP.md` — contrato FE↔BE canônico
- `docs/ROADMAP_GO_LIVE.md` — tasks até o go-live RVB
- `EDGE_DEPLOYMENT_PLAN.md` — as 10 fases do edge
- `docs/decisions/adr/` — ADRs 0001–0041

*Em caso de conflito entre este arquivo e o código real, **o código vence**. Corrija este arquivo.*
