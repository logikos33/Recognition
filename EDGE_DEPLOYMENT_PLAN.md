# Edge Deployment Plan · Recognition Platform

**Versão:** 1.0
**Data:** 2026-05-27
**Cliente âncora:** RVB Isolantes (Blumenau/SC)
**Status:** Plano executável · ordem por fases · gates de aceitação obrigatórios
**Repositório destino:** `github.com/logikos33/recognition` (privado, renomeado de `EPI-CATH-V2`)

---

## Como ler este documento

Este plano organiza a entrega Recognition em **dez fases sequenciais** com **uma trilha paralela de segurança**. Cada fase tem:

- **Objetivo** — o que essa fase entrega
- **Mudanças no código** — o que muda em arquivos concretos
- **Migrations** — schema do banco
- **Endpoints** — APIs criadas/alteradas
- **Critérios de aceitação** — como saber que terminou
- **Prompt pronto pro Claude Code** — execução autônoma

A trilha de segurança tem gates específicos. **Nenhuma fase técnica fecha sem o gate de segurança correspondente verde.**

Toda decisão arquitetural significativa vira ADR em `docs/decisions/adr/`. O plano referencia os ADRs por número.

---

## Índice

1. [Visão Arquitetural](#1-visão-arquitetural)
2. [ADRs — Decisões Já Tomadas](#2-adrs--decisões-já-tomadas)
3. [Estrutura Final do Monorepo](#3-estrutura-final-do-monorepo)
4. [Trilha S — Segurança (Paralela)](#4-trilha-s--segurança-paralela)
5. [Fase 0 — Reorganização e Renomeação](#5-fase-0--reorganização-e-renomeação)
6. [Fase 1 — Schema e Models de Edge](#6-fase-1--schema-e-models-de-edge)
7. [Fase 2 — Blueprint `/api/v1/edge/`](#7-fase-2--blueprint-apiv1edge)
8. [Fase 3 — Refactor dos Microsserviços](#8-fase-3--refactor-dos-microsserviços)
9. [Fase 4 — Novo `edge-sync-agent`](#9-fase-4--novo-edge-sync-agent)
10. [Fase 5 — DeepStream Pipelines](#10-fase-5--deepstream-pipelines)
11. [Fase 6 — Edge Stack e Plug-and-Play](#11-fase-6--edge-stack-e-plug-and-play)
12. [Fase 7 — Frontend Dual Mode](#12-fase-7--frontend-dual-mode)
13. [Fase 8 — Provisionamento RVB](#13-fase-8--provisionamento-rvb)
14. [Fase 9 — Test Harness](#14-fase-9--test-harness)
15. [Fase 10 — Plug-and-Play Day](#15-fase-10--plug-and-play-day)
16. [Critérios Globais de Aceitação](#16-critérios-globais-de-aceitação)
17. [Apêndice A — Templates de Documentação](#17-apêndice-a--templates-de-documentação)
18. [Apêndice B — Prompts Prontos pro Claude Code](#18-apêndice-b--prompts-prontos-pro-claude-code)

---

## 1. Visão Arquitetural

### Dois modos de deployment

A plataforma suporta dois cenários por design, mas **só o modo EDGE é implementado pra produção neste plano**. Cloud-only fica como flag suportada, sem cliente em produção.

**Modo EDGE (RVB, Net-bar, clientes industriais):**

```
┌─────────────────────────────────────────────────────────────┐
│ CLIENTE (fábrica RVB)                                       │
│ ┌─────────────┐    ┌──────────────────────────────────────┐ │
│ │ DVR         │    │ Mini PC (Ubuntu 22.04 + RTX 5060 Ti) │ │
│ │ Intelbras   │───►│                                      │ │
│ │ (28 câm)    │RTSP│ MediaMTX → DeepStream (3 pipelines)  │ │
│ └─────────────┘    │  ↓                                   │ │
│                    │ Redis local (frame:* det:*)          │ │
│                    │  ↓                                   │ │
│                    │ MQTT Mosquitto (events critical)     │ │
│                    │  ↓                                   │ │
│                    │ edge-sync-agent (SQLite buffer)      │ │
│                    │  ↓ HTTPS via Cloudflare Tunnel       │ │
│                    │ ws-gateway-local (live view LAN)     │ │
│                    └──────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS polling + batch POST
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ CLOUD (Railway)                                             │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│ │ api      │ │ auth     │ │ training │ │ scheduler│         │
│ │ /api/v1/ │ │          │ │          │ │          │         │
│ │ /api/v1/ │ │          │ │          │ │          │         │
│ │   edge/* │ │          │ │          │ │          │         │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                      │
│ │ws-gateway│ │ frontend │ │ landing  │                      │
│ │ (remote) │ │          │ │          │                      │
│ └──────────┘ └──────────┘ └──────────┘                      │
│ Postgres  ·  Redis  ·  R2 Storage                           │
└─────────────────────────────────────────────────────────────┘
```

### Princípios arquiteturais

1. **Mesmo codebase, perfis distintos de deploy.** Os serviços de runtime rodam tanto no edge quanto no cloud, dependendo do `DEPLOYMENT_MODE` e `INFERENCE_ENGINE`.

2. **Edge é autônomo.** Internet caiu, edge continua: inferência roda, alertas locais disparam, eventos vão pra SQLite, live view LAN funciona. Quando volta, sincroniza.

3. **Comunicação edge↔cloud é HTTP polling + batch.** Sem WebSocket persistente edge↔cloud. Atravessa qualquer firewall industrial, idempotente, debugável com `curl`.

4. **Eventos críticos passam por MQTT no edge.** Detecções vão pra Redis (alta frequência, fire-and-forget). Alertas e Smart Record triggers vão pra MQTT (QoS 1, persistente, sobrevive a queda de subscriber).

5. **Multi-backend de inferência.** DeepStream (edge) e Ultralytics (cloud-only fallback) vivem no mesmo serviço, selecionado por env var.

6. **Spec-driven.** Contratos OpenAPI/AsyncAPI em `shared/proto/` são fonte de verdade. Cliente e servidor derivam do contrato, não o contrário.

7. **Versionamento de protocolo.** Toda mensagem (Redis, MQTT, HTTP) tem `version` no payload. Cloud N aceita edge N e N-1.

8. **Plug-and-play real.** O dia que o PC chega na RVB, leva 30 minutos pra estar processando 42 câmeras. Tudo pré-provisionado, scripts idempotentes, configs prontas.

---

## 2. ADRs — Decisões Já Tomadas

Estes ADRs serão criados na Fase 0. Cada um é um arquivo curto em `docs/decisions/adr/`.

| ADR | Título | Decisão |
|-----|--------|---------|
| 0001 | DeepStream vs Ultralytics no Edge | DeepStream + TensorRT INT8 no edge; Ultralytics fica como backend pra cloud-only |
| 0002 | Roboflow como Licenciamento Comercial YOLO | Sub-licença Roboflow cobre uso comercial; treino sempre passa por Roboflow workspace |
| 0003 | Redis vs MQTT — Híbrido no Edge | Redis pub/sub pra fluxo interno (frame→inference); MQTT Mosquitto pra eventos críticos (alertas, sync queue) |
| 0004 | HTTP Polling para Comunicação Edge↔Cloud | Edge faz POST batch + GET poll periódicos; sem WebSocket persistente edge↔cloud |
| 0005 | Estrutura de Monorepo | `services/` + `apps/` + `shared/` + `deployments/` + `docs/`; renomeado pra `recognition` |
| 0006 | Frontend Dual Mode (LAN Fallback) | Frontend detecta queda do cloud e faz fallback automático pra `edge.{site}.local` |
| 0007 | Deployment Modes por Tenant | Coluna `deployment_mode` em tenants: `edge` (produção) ou `cloud_only` (suportado, sem cliente) |
| 0008 | Device Tokens com RS256 e Escopos | Edge usa JWT RS256 com escopos limitados, separado do JWT de usuários |
| 0009 | Spec-driven com OpenAPI e AsyncAPI | Contratos formais em `shared/proto/` precedem implementação |
| 0010 | Test Harness Local pra Simular RVB | `tests/harness/` simula edge+cloud localmente; cenários antes de produção |

---

## 3. Estrutura Final do Monorepo

```
recognition/
├── AGENT.md                              # Mapa raiz pro Claude Code
├── README.md                             # Visão geral pro humano
├── .gitignore
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                        # Lint + test + build matrix
│   │   ├── publish-images.yml            # Build + push pra GHCR
│   │   └── security-scan.yml             # gitleaks + dependabot config
│   └── dependabot.yml
├── docker-compose.dev.yml                # Stack local de desenvolvimento
│
├── services/                             # Serviços de runtime
│   ├── api/                              # Antigo backend/ (monolito controlador)
│   │   ├── app/
│   │   │   ├── api/v1/
│   │   │   │   ├── edge/                 # NOVO blueprint
│   │   │   │   ├── admin/
│   │   │   │   ├── auth/
│   │   │   │   └── ...
│   │   │   ├── core/
│   │   │   ├── domain/
│   │   │   └── infrastructure/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   ├── railway.toml
│   │   ├── AGENT.md
│   │   └── SDD.md
│   │
│   ├── auth/                             # Antigo painel-adm/auth-service
│   │   └── ...
│   ├── camera-gateway/                   # Roda no edge
│   │   └── ...
│   ├── inference/                        # Multi-backend (DeepStream/Ultralytics)
│   │   ├── app/
│   │   │   ├── backends/
│   │   │   │   ├── deepstream/
│   │   │   │   └── ultralytics/
│   │   │   └── ...
│   │   └── ...
│   ├── ws-gateway/                       # Roda em cloud E edge
│   │   └── ...
│   ├── scheduler/                        # Só cloud
│   │   └── ...
│   ├── training/                         # Só cloud
│   │   └── ...
│   └── edge-sync-agent/                  # NOVO - só edge
│       ├── app/
│       │   ├── mqtt_consumer.py
│       │   ├── sqlite_buffer.py
│       │   ├── uploader.py
│       │   ├── config_poller.py
│       │   ├── model_manager.py
│       │   ├── mirror_api.py             # API espelho LAN
│       │   └── main.py
│       ├── tests/
│       ├── Dockerfile
│       ├── AGENT.md
│       └── SDD.md
│
├── apps/                                 # Interfaces de usuário
│   ├── frontend/                         # Antigo frontend/ (SPA React)
│   │   ├── src/
│   │   │   ├── hooks/
│   │   │   │   └── useDualMode.ts        # NOVO
│   │   │   └── services/
│   │   │       └── apiClient.ts          # Refator pra dual mode
│   │   └── ...
│   └── landing/                          # Antigo landing-page/ (Astro)
│       └── ...
│
├── shared/                               # Código compartilhado
│   ├── python/
│   │   └── recognition_shared/
│   │       ├── auth/
│   │       │   ├── jwt_user.py
│   │       │   ├── jwt_device.py         # NOVO
│   │       │   └── decorators.py
│   │       ├── events/
│   │       │   ├── detection.py          # Pydantic models
│   │       │   ├── alert.py
│   │       │   └── ...
│   │       ├── logging/
│   │       │   └── structlog_config.py
│   │       ├── redis_helpers/
│   │       ├── mqtt_helpers/
│   │       └── db/
│   ├── proto/                            # Contratos formais
│   │   ├── edge-api.yaml                 # OpenAPI 3.1 — endpoints /api/v1/edge/*
│   │   ├── events.yaml                   # AsyncAPI 2.6 — Redis/MQTT
│   │   ├── public-api.yaml               # OpenAPI 3.1 — endpoints públicos
│   │   └── README.md
│   └── ts/
│       └── recognition-shared/           # Tipos compartilhados pro frontend
│
├── deployments/
│   ├── cloud/
│   │   └── railway-services.md           # Lista de serviços Railway com configs
│   ├── edge/                             # Tudo que vai no Mini PC
│   │   ├── docker-compose.yml            # Stack edge completo
│   │   ├── .env.template
│   │   ├── install.sh                    # Provisionamento zero-touch
│   │   ├── update.sh                     # Atualização manual
│   │   ├── uninstall.sh
│   │   ├── nvidia-setup.sh
│   │   ├── tailscale-setup.sh
│   │   ├── cloudflared-setup.sh
│   │   ├── ufw-rules.sh                  # Firewall edge
│   │   ├── README.md                     # Pro técnico que instala
│   │   └── AGENT.md
│   └── dev/
│       └── docker-compose.harness.yml    # Stack simulando RVB localmente
│
├── deepstream/                           # Configs DeepStream
│   ├── epi/
│   │   ├── pipeline.txt
│   │   ├── tracker.yml
│   │   ├── analytics.txt
│   │   ├── calibration/
│   │   └── README.md
│   ├── fueling/
│   ├── quality/
│   └── shared/                           # Configs base reutilizáveis
│
├── models/                               # Manifestos (não os pesos)
│   └── manifests/
│       ├── epi-v3.json
│       ├── fueling-v1.json
│       └── README.md
│
├── infra/
│   ├── migrations/                       # Antigo backend/migrations
│   │   ├── 001_initial.sql
│   │   ├── ...
│   │   ├── 042_edge_sites.sql            # NOVO
│   │   ├── 043_device_tokens.sql         # NOVO
│   │   ├── 044_site_id_columns.sql       # NOVO
│   │   └── 045_deployment_mode.sql       # NOVO
│   └── scripts/
│
├── docs/
│   ├── architecture/
│   │   ├── GSD.md                        # General System Description
│   │   ├── Arquitetura_Final_Recognition_RVB.md  # Movido
│   │   └── Arquitetura_Inicial_Netbar.md         # Movido
│   ├── decisions/
│   │   ├── log.md                        # Log corrido de decisões pequenas
│   │   └── adr/
│   │       ├── 0001-deepstream-vs-ultralytics.md
│   │       ├── 0002-roboflow-licensing.md
│   │       ├── 0003-redis-mqtt-hibrido.md
│   │       ├── 0004-http-polling-edge-cloud.md
│   │       ├── 0005-monorepo-structure.md
│   │       ├── 0006-frontend-dual-mode.md
│   │       ├── 0007-deployment-modes.md
│   │       ├── 0008-device-tokens-rs256.md
│   │       ├── 0009-spec-driven-development.md
│   │       └── 0010-test-harness.md
│   ├── runbooks/                         # Operação
│   │   ├── edge-rvb-onboarding.md
│   │   ├── edge-not-syncing.md
│   │   ├── model-rollout.md
│   │   ├── rotate-device-token.md
│   │   └── ...
│   ├── security/
│   │   ├── threat-model.md
│   │   ├── credentials-inventory.md
│   │   ├── rotation-runbook.md
│   │   ├── access-control.md
│   │   └── lgpd-pending.md
│   └── product/                          # Documentos comerciais
│
└── tests/
    └── harness/                          # Test harness end-to-end
        ├── docker-compose.harness.yml
        ├── fixtures/
        │   ├── synthetic-rtsp/           # Vídeos sintéticos por 28 câmeras
        │   ├── tenants.sql
        │   └── camera-config.yaml
        ├── scenarios/
        │   ├── edge-online-baseline.py
        │   ├── edge-offline-recovery.py
        │   ├── model-rollout.py
        │   ├── 42-cameras-load.py
        │   └── multi-tenant-isolation.py
        ├── runner/
        │   ├── harness.py                # Framework execução cenários
        │   └── assertions.py
        └── README.md
```

---

## 4. Trilha S — Segurança (Paralela)

Trilha rodando em paralelo com as fases técnicas. Gates obrigatórios.

### Fase S0 — Imediato (antes da Fase 0)

**Objetivo:** Tornar o repo seguro antes de qualquer trabalho.

**Atividades:**
- [ ] Inventariar segredos atualmente em uso (Railway env vars, R2, Roboflow, JWT secret, Cloudflare, Tailscale, GitHub)
- [ ] Rotacionar TODOS os segredos listados nos provedores originais
- [ ] Atualizar Railway env vars com novos valores
- [ ] Criar `docs/security/credentials-inventory.md` com tabela de TODOS os segredos (onde vive, quem rotaciona, frequência)
- [ ] Renomear repo `EPI-CATH-V2` pra `recognition`
- [ ] Tornar repo privado
- [ ] Adicionar `.gitignore` rigoroso pra prevenir novos vazamentos:
  - `.env`, `.env.local`, `.env.*.local`
  - `*.pem`, `*.key`, `*.p12`, `*.pfx`
  - `secrets/`
  - `*.sqlite`, `*.db`
- [ ] Habilitar GitHub branch protection na `main` (require PR, no force push, no deletion)
- [ ] Habilitar `gitleaks` no CI pra varrer cada PR
- [ ] Habilitar Dependabot

**Critérios de aceitação:**
- Repo privado, renomeado, com branch protection
- Todos os segredos novos, antigos invalidados nos provedores
- `gitleaks` rodando no CI
- `credentials-inventory.md` documentado

### Fase S1 — Hardening do `api` (paralela à Fase 2)

**Atividades:**
- [ ] Auditoria de `tenant_id` em todas as queries — tarefa de Claude Code
- [ ] `pydantic-settings` pra validação de env vars no startup
- [ ] `flask-limiter` configurado com limites por endpoint
- [ ] `flask-talisman` ou middleware custom pra headers de segurança
- [ ] Audit log populado consistentemente em `audit_log` table
- [ ] Logs do app sem PII (CPF, email completo, telefone)
- [ ] CORS auditado — whitelist explícita por env

**Critérios de aceitação:**
- Zero queries sem `tenant_id` filter (script de auditoria passa)
- Headers de segurança aparecem em toda resposta HTTP
- Rate limiting ativo (testado com `curl` em loop)
- Audit log tem entrada pra: login, criação/edição/exclusão de cameras/rules/users, acessos a alertas

### Fase S2 — Hardening do Edge (paralela às Fases 4-7)

**Atividades:**
- [ ] Device tokens RS256 implementados (chave privada só no cloud)
- [ ] One-time enrollment token implementado
- [ ] Storage de credenciais no edge via Docker secrets (não `.env` plain)
- [ ] TLS no MQTT local (mesmo sendo LAN)
- [ ] Redis local com `requirepass` + `protected-mode yes`
- [ ] UFW configurado no Mini PC (regras em `deployments/edge/ufw-rules.sh`)
- [ ] Network isolation: câmeras em VLAN separada (documentado, configurado no MikroTik se aplicável)
- [ ] Certificado self-signed gerado por site pra LAN HTTPS
- [ ] Plano documentado: rotação de device token aos 60 dias

**Critérios de aceitação:**
- Edge resiste a `nmap` (só portas autorizadas respondem)
- Token de device de site X não acessa dados de site Y
- Token expirado é rejeitado
- Enrollment token só funciona uma vez

### Fase S3 — Gate Pré-Produção (antes da Fase 10)

**Atividades:**
- [ ] Pen test interno: você + checklist OWASP top 10 (1 dia)
- [ ] Backup Postgres → R2 automatizado diário
- [ ] Backup configs do edge → cloud (criptografado)
- [ ] Sentry ou similar capturando exceções (sem PII)
- [ ] Alertas Slack/email pra padrões suspeitos
- [ ] `docs/security/lgpd-pending.md` documentando o que falta jurídico endereçar (DPA com RVB, política de privacidade, direito ao esquecimento)
- [ ] Disaster recovery plan documentado e testado em ambiente de harness

**Critérios de aceitação:**
- Checklist OWASP top 10 com nota de cada item (passa/não passa/N/A)
- Restore de Postgres funciona em ambiente limpo
- Sentry recebendo eventos
- LGPD pendências documentadas pra ti levar pro jurídico

---

## 5. Fase 0 — Reorganização e Renomeação

**Status:** Bloqueante de tudo. Sem Fase 0 fechada, demais fases não começam.

### Objetivo

Reorganizar o monorepo pra estrutura final, renomear o repo, criar todos os diretórios de documentação, escrever ADRs das decisões já tomadas, e validar que tudo continua rodando.

### Atividades

1. **Renomear repo no GitHub** (`EPI-CATH-V2` → `recognition`)
2. **Atualizar referências externas** (Railway service connections, webhooks, CI/CD references)
2b. **Remover gitlink órfão `painel-adm/`** (antes de qualquer `git mv`):
   ```bash
   git rm --cached painel-adm          # remove entrada mode 160000 do index
   git worktree remove painel-adm      # remove linked worktree do filesystem
   git tag archive/microservices-attempt-1 refs/heads/painel-adm
   git push origin archive/microservices-attempt-1
   ```
   Branch `painel-adm` permanece localmente como referência de leitura.
   Os serviços de edge são criados do zero na Fase 3 (ver ADR-0014).
3. **Mover diretórios via `git mv`** (preserva histórico):
   - `backend/` → `services/api/`
   - `inference-service/` → `services/inference/`
   - `frontend/` → `apps/frontend/`
   - `landing-page/` → `apps/landing/`
   - `backend/migrations/` → `infra/migrations/`

   > **Nota:** `camera-gateway/`, `ws-gateway/`, `training-service/` e `auth-service/`
   > foram removidos de staging em maio/2026 (absorvidos pelo monolito api-v3).
   > Esses serviços serão criados do zero na Fase 3, com referência ao código em
   > `archive/microservices-attempt-1`. Não usar `git mv` nem `git checkout` deles.
4. **Criar diretórios novos:**
   - `services/edge-sync-agent/` (vazio, será preenchido na Fase 4)
   - `shared/python/recognition_shared/`
   - `shared/proto/`
   - `shared/ts/recognition-shared/`
   - `deployments/cloud/`
   - `deployments/edge/`
   - `deployments/dev/`
   - `deepstream/{epi,fueling,quality,shared}/`
   - `models/manifests/`
   - `docs/architecture/`
   - `docs/decisions/adr/`
   - `docs/runbooks/`
   - `docs/security/`
   - `docs/product/`
   - `tests/harness/`
5. **Mover docs existentes:**
   - `docs/EDGE_AGENT_ARCHITECTURE.md` → `docs/architecture/EDGE_AGENT_ARCHITECTURE.md`
6. **Atualizar paths em todos os arquivos:**
   - `Dockerfile`s — paths `COPY` e `WORKDIR`
   - `railway.toml`s — paths dos serviços
   - imports relativos no código
   - `requirements.txt`s — adicionar `recognition-shared` (instalado em modo editable do path local)
7. **Criar `AGENT.md` raiz** com mapa do monorepo, regras globais
8. **Criar `AGENT.md`** em cada `services/<nome>/` (10 arquivos)
9. **Criar `SDD.md` esqueleto** em cada `services/<nome>/` (10 arquivos)
10. **Escrever os 10 ADRs** das decisões já tomadas
11. **Escrever o GSD** (`docs/architecture/GSD.md`)
12. **Configurar `.github/workflows/ci.yml`** com lint + test
13. **Configurar `.github/workflows/security-scan.yml`** com gitleaks
14. **Validar:** todo serviço continua subindo localmente via `docker-compose.dev.yml`

### Critérios de aceitação

- [ ] Repo se chama `recognition`, é privado, branch protection na `main`
- [ ] Estrutura `services/`, `apps/`, `shared/`, `deployments/`, `docs/`, `tests/`, `infra/`, `deepstream/`, `models/` existe
- [ ] `backend/` e `inference-service/` movidos para `services/api/` e `services/inference/`
- [ ] Gitlink órfão `painel-adm/` removido; tag `archive/microservices-attempt-1` criada e pushed
- [ ] `git log --follow` em arquivos movidos mostra histórico preservado
- [ ] Todos os 10 ADRs escritos (mesmo que curtos)
- [ ] `AGENT.md` raiz + 10 `AGENT.md` por serviço escritos
- [ ] `docker-compose.dev.yml` sobe todos os serviços localmente sem erro
- [ ] CI no GitHub Actions verde no primeiro push
- [ ] Railway deploys continuam funcionando (testado em staging)

### Estimativa de complexidade

Alta em volume, baixa em risco. Maior parte é movimentação de arquivos e atualização de paths. Risco principal: esquecer de atualizar algum `railway.toml` ou import.

---

## 6. Fase 1 — Schema e Models de Edge

### Objetivo

Adicionar suporte de edge no schema do banco e nos models Python compartilhados.

### Mudanças no banco

**Migration `042_edge_sites.sql`:**

```sql
CREATE TABLE IF NOT EXISTS edge_sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    slug VARCHAR(64) NOT NULL,
    name VARCHAR(200) NOT NULL,
    location VARCHAR(500),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, provisioning, active, degraded, offline, disabled
    last_seen_at TIMESTAMPTZ,
    edge_version VARCHAR(32),
    deployment_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_edge_sites_tenant ON edge_sites(tenant_id);
CREATE INDEX IF NOT EXISTS idx_edge_sites_status ON edge_sites(status) WHERE status != 'disabled';
CREATE INDEX IF NOT EXISTS idx_edge_sites_last_seen ON edge_sites(last_seen_at);
```

**Migration `043_device_tokens.sql`:**

```sql
CREATE TABLE IF NOT EXISTS device_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES edge_sites(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    kid VARCHAR(64) NOT NULL,  -- key id pra rotação
    token_hash VARCHAR(128) NOT NULL,  -- SHA-256 do token
    scopes TEXT[] NOT NULL DEFAULT '{}',
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    rotated_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    last_used_ip INET,
    UNIQUE(token_hash)
);

CREATE INDEX IF NOT EXISTS idx_device_tokens_site ON device_tokens(site_id);
CREATE INDEX IF NOT EXISTS idx_device_tokens_active ON device_tokens(site_id, expires_at) WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS enrollment_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id UUID NOT NULL REFERENCES edge_sites(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    token_hash VARCHAR(128) NOT NULL UNIQUE,
    created_by UUID REFERENCES users(id),
    expires_at TIMESTAMPTZ NOT NULL,
    redeemed_at TIMESTAMPTZ,
    redeemed_ip INET
);
```

**Migration `044_site_id_columns.sql`:**

```sql
ALTER TABLE ip_cameras ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES edge_sites(id);
ALTER TABLE camera_events ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES edge_sites(id);
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES edge_sites(id);
ALTER TABLE counting_events ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES edge_sites(id);
ALTER TABLE counting_sessions ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES edge_sites(id);
ALTER TABLE quality_recording_segments ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES edge_sites(id);
ALTER TABLE quality_inspections ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES edge_sites(id);
ALTER TABLE operations ADD COLUMN IF NOT EXISTS site_id UUID REFERENCES edge_sites(id);

CREATE INDEX IF NOT EXISTS idx_ip_cameras_site ON ip_cameras(site_id) WHERE site_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_camera_events_site ON camera_events(site_id) WHERE site_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_alerts_site ON alerts(site_id) WHERE site_id IS NOT NULL;
```

**Migration `045_deployment_mode.sql`:**

```sql
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS deployment_mode VARCHAR(20) NOT NULL DEFAULT 'cloud_only';
ALTER TABLE tenants ADD CONSTRAINT chk_deployment_mode CHECK (deployment_mode IN ('edge', 'cloud_only'));

-- Tabela pra rastrear health check histórico do edge
CREATE TABLE IF NOT EXISTS edge_heartbeats (
    id BIGSERIAL PRIMARY KEY,
    site_id UUID NOT NULL REFERENCES edge_sites(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    edge_version VARCHAR(32),
    cpu_percent FLOAT,
    gpu_percent FLOAT,
    ram_percent FLOAT,
    disk_percent FLOAT,
    cameras_total INT,
    cameras_streaming INT,
    inference_fps FLOAT,
    pending_events_count INT,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_edge_heartbeats_site_time ON edge_heartbeats(site_id, received_at DESC);

-- Particionamento opcional por mês depois (não bloqueia agora)
```

### Mudanças em `shared/python/recognition_shared/`

Criar package Python compartilhado com models Pydantic:

**`shared/python/recognition_shared/models/edge.py`:**

```python
from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, IPvAnyAddress


class SiteStatus(str, Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    DISABLED = "disabled"


class DeploymentMode(str, Enum):
    EDGE = "edge"
    CLOUD_ONLY = "cloud_only"


class DeviceTokenScope(str, Enum):
    EVENTS_WRITE = "events:write"
    CONFIG_READ = "config:read"
    MODELS_DOWNLOAD = "models:download"
    HEARTBEAT_WRITE = "heartbeat:write"
    STREAMS_REPORT = "streams:report"


class EdgeSite(BaseModel):
    id: UUID
    tenant_id: UUID
    slug: str
    name: str
    location: str | None
    status: SiteStatus
    last_seen_at: datetime | None
    edge_version: str | None
    deployment_metadata: dict = Field(default_factory=dict)


class DeviceTokenClaims(BaseModel):
    """JWT claims for device tokens (RS256)."""
    sub: str  # 'device:<site_slug>'
    site_id: str
    tenant_id: str
    scopes: list[DeviceTokenScope]
    kid: str
    iat: int
    exp: int


class HeartbeatPayload(BaseModel):
    version: Literal["1.0"] = "1.0"
    edge_version: str
    cpu_percent: float = Field(ge=0, le=100)
    gpu_percent: float = Field(ge=0, le=100)
    ram_percent: float = Field(ge=0, le=100)
    disk_percent: float = Field(ge=0, le=100)
    cameras_total: int = Field(ge=0)
    cameras_streaming: int = Field(ge=0)
    inference_fps: float = Field(ge=0)
    pending_events_count: int = Field(ge=0)
    metadata: dict = Field(default_factory=dict)
```

### Critérios de aceitação

- [ ] **4 migrations** rodam idempotentemente (rodar 2x sem erro): 042, 043, 044, 045
- [ ] Schema atualizado em staging
- [ ] `recognition_shared` package instalável (`pip install -e shared/python`)
- [ ] Models Pydantic com tests unitários
- [ ] Documentação dos models em `shared/python/recognition_shared/README.md`

---

## 7. Fase 2 — Blueprint `/api/v1/edge/`

### Objetivo

Criar a API que o `edge-sync-agent` vai consumir. Toda comunicação edge→cloud passa por aqui. Spec-driven: contrato em `shared/proto/edge-api.yaml` precede implementação.

### Spec (OpenAPI 3.1) — `shared/proto/edge-api.yaml`

Endpoints principais (resumo, contrato completo a ser escrito):

```yaml
# POST /api/v1/edge/enrollment/redeem
#   Body: { enrollment_token: string, edge_version: string, host_info: object }
#   Response: { device_token: string, refresh_after: datetime, expires_at: datetime, server_time: datetime }
#   Auth: enrollment_token (one-time)

# POST /api/v1/edge/auth/rotate
#   Headers: Authorization: Bearer <device_token>
#   Response: { device_token: string, refresh_after: datetime, expires_at: datetime }
#   Auth: device_token (mesmo site, scope:auth)

# POST /api/v1/edge/events/batch
#   Headers: Authorization: Bearer <device_token>, X-Edge-Version, X-Batch-Id
#   Body: { events: [<DetectionEvent | AlertEvent | CountingEvent>] }
#   Response: { accepted: int, rejected: [{batch_index, reason}] }
#   Auth: device_token (scope: events:write)
#   Idempotent: X-Batch-Id evita duplicação

# GET /api/v1/edge/config/poll?since=<timestamp>
#   Headers: Authorization: Bearer <device_token>
#   Response: { changes: [{type, payload}], server_time: datetime, next_poll_in: int }
#   Auth: device_token (scope: config:read)

# GET /api/v1/edge/models/manifest
#   Headers: Authorization: Bearer <device_token>
#   Response: { models: [{module, version, engine_url, checksum, signed_until}] }
#   Auth: device_token (scope: models:download)

# GET /api/v1/edge/models/{model_id}/download-url
#   Headers: Authorization: Bearer <device_token>
#   Response: { presigned_url: string, expires_at: datetime, checksum: string }
#   Auth: device_token (scope: models:download)

# POST /api/v1/edge/heartbeat
#   Headers: Authorization: Bearer <device_token>
#   Body: HeartbeatPayload
#   Response: { received_at: datetime, server_time: datetime }
#   Auth: device_token (scope: heartbeat:write)

# POST /api/v1/edge/streams/report
#   Headers: Authorization: Bearer <device_token>
#   Body: { cameras: [{camera_id, status, fps, last_frame_at}] }
#   Response: { received_at: datetime }
#   Auth: device_token (scope: streams:report)
```

### Implementação em `services/api/app/api/v1/edge/`

Estrutura:

```
services/api/app/api/v1/edge/
├── __init__.py                  # blueprint registration
├── enrollment.py
├── auth.py
├── events.py                    # batch ingestion
├── config.py                    # config polling
├── models.py                    # model manifest + download URLs
├── heartbeat.py
├── streams.py
└── middleware.py                # device token validation
```

### Middleware de device token

`services/api/app/api/v1/edge/middleware.py`:

```python
from functools import wraps
from flask import request, g, jsonify
from recognition_shared.auth.jwt_device import verify_device_token, DeviceTokenError

def require_device_token(*required_scopes):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth = request.headers.get('Authorization', '')
            if not auth.startswith('Bearer '):
                return jsonify({'status': 'error', 'data': {'reason': 'missing_token'}}), 401
            token = auth[7:]
            try:
                claims = verify_device_token(token)
            except DeviceTokenError as e:
                return jsonify({'status': 'error', 'data': {'reason': str(e)}}), 401
            
            for scope in required_scopes:
                if scope not in claims.scopes:
                    return jsonify({'status': 'error', 'data': {'reason': f'missing_scope:{scope}'}}), 403
            
            g.device_claims = claims
            g.tenant_id = claims.tenant_id
            g.site_id = claims.site_id
            
            # Update last_used (async, não bloqueia request)
            from app.infrastructure.queue.tasks.device import update_device_token_usage
            update_device_token_usage.delay(
                token_hash=hash_token(token),
                ip=request.remote_addr,
            )
            
            return f(*args, **kwargs)
        return wrapper
    return decorator
```

### Endpoints críticos detalhados

**`POST /api/v1/edge/events/batch`** — o endpoint mais crítico, recebe TODO o output do edge:

```python
@edge_bp.route('/events/batch', methods=['POST'])
@require_device_token('events:write')
def batch_events():
    batch_id = request.headers.get('X-Batch-Id')
    if not batch_id:
        return jsonify({'status': 'error', 'data': {'reason': 'missing_batch_id'}}), 400
    
    # Idempotência: verifica se batch_id já foi processado nas últimas 24h
    if batch_already_processed(batch_id, g.tenant_id):
        return jsonify({'status': 'success', 'data': {'accepted': 0, 'duplicate': True}}), 200
    
    body = request.get_json()
    events = body.get('events', [])
    
    if len(events) > 500:  # batch máximo
        return jsonify({'status': 'error', 'data': {'reason': 'batch_too_large'}}), 413
    
    accepted = 0
    rejected = []
    
    with get_db_connection() as conn:
        for i, raw_event in enumerate(events):
            try:
                event = parse_event(raw_event)  # Pydantic
                # Garante que evento pertence ao site/tenant do token
                if event.site_id != g.site_id or event.tenant_id != g.tenant_id:
                    rejected.append({'index': i, 'reason': 'tenant_mismatch'})
                    continue
                
                persist_event(conn, event)
                publish_to_websocket(event)  # notifica frontend cloud
                accepted += 1
            except ValidationError as e:
                rejected.append({'index': i, 'reason': str(e)})
    
    mark_batch_processed(batch_id, g.tenant_id, accepted)
    
    return jsonify({
        'status': 'success',
        'data': {'accepted': accepted, 'rejected': rejected, 'server_time': now()}
    }), 200
```

### Critérios de aceitação

- [ ] `shared/proto/edge-api.yaml` escrito (OpenAPI 3.1 válido)
- [ ] Todos os endpoints implementados em `services/api/app/api/v1/edge/`
- [ ] Middleware de device token funciona (testado com token válido, expirado, sem scope, mismatch de tenant)
- [ ] Idempotência por `X-Batch-Id` (testado com requests duplicados)
- [ ] Rate limiting configurado (60 req/min por site pro batch)
- [ ] Tests unitários + integration tests com >70% coverage no blueprint edge
- [ ] Documentação Swagger UI acessível em `/api/v1/edge/docs`

---

## 8. Fase 3 — Refactor dos Microsserviços

### Objetivo

Tornar os 6 microsserviços existentes prontos pra rodar em modo edge ou cloud. Multi-backend de inferência. Configuração por env var.

### `services/inference/` — Multi-backend

Refator pra suportar dois backends selecionáveis:

```
services/inference/app/
├── backends/
│   ├── __init__.py
│   ├── base.py                  # InferenceBackend ABC
│   ├── deepstream/
│   │   ├── __init__.py
│   │   ├── runner.py
│   │   ├── pipeline_loader.py   # carrega config DeepStream do disco
│   │   └── event_parser.py
│   └── ultralytics/
│       ├── __init__.py
│       ├── runner.py
│       └── frame_consumer.py
├── core/
│   ├── redis_client.py
│   ├── mqtt_publisher.py        # pra eventos críticos
│   └── model_watcher.py
└── main.py                      # seleciona backend por env
```

`services/inference/app/main.py`:

```python
import os
from app.backends.deepstream.runner import DeepStreamRunner
from app.backends.ultralytics.runner import UltralyticsRunner

def main():
    engine = os.environ.get('INFERENCE_ENGINE', 'ultralytics')
    
    if engine == 'deepstream':
        runner = DeepStreamRunner.from_env()
    elif engine == 'ultralytics':
        runner = UltralyticsRunner.from_env()
    else:
        raise ValueError(f'Unknown inference engine: {engine}')
    
    runner.start()
    
if __name__ == '__main__':
    main()
```

### `services/camera-gateway/` — Adaptações pro edge

Mudanças:
- Configuração via `/api/v1/edge/config/poll` quando `DEPLOYMENT_MODE=edge`
- Cache local em SQLite (lista de câmeras, RTSP URLs, classes)
- Health check robusto por câmera

### `services/ws-gateway/` — Dual deploy

Roda em dois lugares:
- **Cloud**: distribui pra clientes do dashboard remoto (via Cloudflare Tunnel pro live view)
- **Edge LAN**: distribui pra clientes na rede local da fábrica

Mesma codebase, mesma imagem Docker, parametrizada por `WS_GATEWAY_MODE=cloud|edge`.

### `services/scheduler/` — Adiciona `railway.toml`

Atualmente sem `railway.toml`. Adicionar. Também adicionar tasks edge:
- Polling de health dos edges (alerta se `last_seen_at > 5min`)
- Rotação automática de device tokens próximos do vencimento
- Limpeza de heartbeats antigos (>90 dias)

### Critérios de aceitação

- [ ] `inference` suporta `INFERENCE_ENGINE=deepstream|ultralytics`
- [ ] Em modo `ultralytics`, comportamento atual preservado (sem regressão)
- [ ] Em modo `deepstream`, pipeline carrega de `/deepstream/<module>/pipeline.txt`
- [ ] `camera-gateway` em modo edge carrega config via API
- [ ] `ws-gateway` parametrizado por modo
- [ ] `scheduler` com `railway.toml` + tasks edge
- [ ] Tests cobrem ambos os backends
- [ ] Documentação `SDD.md` atualizada em cada serviço

---

## 9. Fase 4 — Novo `edge-sync-agent`

### Objetivo

Criar o serviço que faz ponte edge↔cloud. Consome MQTT local, persiste em SQLite, envia em batch pra cloud, faz polling de config, gerencia download de modelos, expõe API espelho pra frontend dual mode.

### Estrutura

```
services/edge-sync-agent/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── mqtt_consumer.py         # Subscribe MQTT local (events/critical)
│   ├── sqlite_buffer.py         # Buffer persistente offline
│   ├── uploader.py              # POST batch pra cloud com backoff
│   ├── config_poller.py         # GET /api/v1/edge/config/poll
│   ├── model_manager.py         # Download/validate/swap modelos
│   ├── heartbeat.py             # POST /api/v1/edge/heartbeat
│   ├── stream_reporter.py       # POST /api/v1/edge/streams/report
│   ├── mirror_api.py            # FastAPI espelhando endpoints essenciais pra LAN
│   └── auth/
│       ├── enrollment.py
│       └── token_manager.py     # Carrega/rotaciona device token
├── tests/
├── Dockerfile
├── requirements.txt
├── AGENT.md
└── SDD.md
```

### Fluxo principal

```python
# services/edge-sync-agent/app/main.py
import asyncio
from app.auth.token_manager import TokenManager
from app.mqtt_consumer import MqttConsumer
from app.sqlite_buffer import SqliteBuffer
from app.uploader import Uploader
from app.config_poller import ConfigPoller
from app.heartbeat import HeartbeatSender
from app.mirror_api import start_mirror_api

async def main():
    token_mgr = TokenManager.from_env()  # carrega de Docker secret
    await token_mgr.ensure_valid()
    
    buffer = SqliteBuffer(path='/var/lib/edge-sync/buffer.db')
    
    mqtt = MqttConsumer(
        broker='mqtt://mosquitto:1883',
        topics=['events/+/critical', 'alerts/+', 'recording/+/triggered'],
        on_message=buffer.enqueue,
    )
    
    uploader = Uploader(token_mgr, buffer, batch_size=100, interval_s=5)
    config_poller = ConfigPoller(token_mgr, interval_s=30)
    heartbeat = HeartbeatSender(token_mgr, interval_s=60)
    
    await asyncio.gather(
        mqtt.run(),
        uploader.run(),
        config_poller.run(),
        heartbeat.run(),
        start_mirror_api(token_mgr, buffer),  # API LAN
    )

if __name__ == '__main__':
    asyncio.run(main())
```

### `mirror_api.py` — API LAN pro frontend dual mode

FastAPI rodando na porta 8443 (HTTPS self-signed), expõe subset de endpoints que o frontend consome quando o cloud está inacessível:

```python
from fastapi import FastAPI

app = FastAPI(title="Edge Mirror API")

@app.get("/api/v1/health")
async def health():
    return {"status": "edge_lan", "site_id": SITE_ID}

@app.get("/api/v1/cameras")
async def cameras():
    # Lê do cache local SQLite
    return cached_cameras()

@app.get("/api/v1/alerts/recent")
async def alerts_recent(limit: int = 50):
    # Lê eventos não-uploaded ou recentes do SQLite buffer
    return buffer.recent_alerts(limit)

@app.get("/api/v1/streams/{camera_id}/hls.m3u8")
async def stream_hls(camera_id: str):
    # Proxy pro camera-gateway local
    return RedirectResponse(f"http://camera-gateway:8080/hls/{camera_id}/index.m3u8")
```

### SQLite buffer schema

```sql
CREATE TABLE IF NOT EXISTS pending_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,  -- JSON
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    upload_attempts INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    uploaded_at TEXT
);

CREATE INDEX idx_pending_pending ON pending_events(uploaded_at) WHERE uploaded_at IS NULL;

CREATE TABLE IF NOT EXISTS local_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS model_versions (
    module TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    engine_path TEXT NOT NULL,
    checksum TEXT NOT NULL,
    activated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### Critérios de aceitação

- [ ] `edge-sync-agent` consome MQTT local e persiste em SQLite
- [ ] Uploader envia em batches com backoff exponencial (1s, 2s, 4s, 8s, 16s, 30s max)
- [ ] Buffer aguenta 24h offline sem perda
- [ ] Config polling aplica mudanças sem restart
- [ ] Model manager baixa, valida checksum, swap atômico
- [ ] Mirror API responde em <100ms
- [ ] Heartbeat envia métricas reais (CPU/GPU/RAM/disk)
- [ ] Tests cobrem cenário offline → online recovery

---

## 10. Fase 5 — DeepStream Pipelines

### Objetivo

Configurar 3 pipelines DeepStream (EPI, Fueling, Quality) em `deepstream/`. Cada pipeline tem configs INI, tracker, analytics, e plugin de saída pra MQTT.

### Estrutura por módulo

```
deepstream/epi/
├── pipeline.txt                 # Main pipeline config (DS INI)
├── pgie_config.txt              # Primary GIE (inferência YOLO)
├── tracker.yml                  # NvDCF tracker config
├── analytics.txt                # nvdsanalytics (zonas + line crossing)
├── msgconv_config.txt           # nvmsgconv → MQTT
├── smart_record_config.txt      # Smart Record (clipes 30s)
├── labels.txt                   # Classes do modelo
├── calibration/
│   └── int8_calib.txt           # Calibration table TensorRT
└── README.md
```

### Pipeline EPI (resumo)

```ini
# deepstream/epi/pipeline.txt
[application]
enable-perf-measurement=1
perf-measurement-interval-sec=5

[tiled-display]
enable=0  # sem display, headless

[source-list]
num-source-bins=15  # 15 câmeras EPI da RVB
list=file:///configs/cameras-epi.list  # populado dinamicamente

[streammux]
batch-size=15
batched-push-timeout=40000
width=640
height=480
nvbuf-memory-type=0

[primary-gie]
plugin-type=0
enable=1
batch-size=15
gpu-id=0
nvbuf-memory-type=0
config-file=pgie_config.txt

[tracker]
enable=1
tracker-width=640
tracker-height=384
ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so
ll-config-file=tracker.yml

[nvds-analytics]
enable=1
config-file=analytics.txt

[message-converter]
msg2p-lib=libnvds_msgconv.so
config=msgconv_config.txt
msg2p-newapi=1

[message-broker]
proto-lib=libnvds_mqtt_proto.so
conn-str=mosquitto;1883;edge
config=mqtt_broker_config.txt
topic=events/epi/critical
```

### Smart Record — clipes de evidência

Configuração pra que cada alerta dispare gravação de 30s (15s antes + 15s depois) automaticamente, sem código custom.

### Pipeline Fueling (skeleton)

Mesmo padrão do EPI mas:
- 8 câmeras
- Modelo de detecção: truck/plate/nozzle/product_box
- Analytics: line crossing (entrada/saída)
- ANPR opcional como secondary GIE

### Pipeline Quality (skeleton)

Trigger-based (appsrc), não contínuo:
- Recebe frames via socket do `quality-tablet-api`
- Inferência batch=7
- Resultado vem direto sem MQTT (low latency)

### Critérios de aceitação

- [ ] 3 pipelines configurados em `deepstream/`
- [ ] EPI processa 15 streams a 3 FPS sem perda em hardware spec'd (RTX 5060 Ti)
- [ ] Fueling processa 8 streams a 3 FPS sem perda
- [ ] Quality responde em <1s do trigger
- [ ] Smart Record gera clipes válidos de 30s
- [ ] Eventos MQTT chegam no broker local
- [ ] Hot-swap de modelo funciona (engine novo carrega sem restart)
- [ ] Tests com vídeo sintético (em `tests/harness/fixtures/synthetic-rtsp/`)

---

## 11. Fase 6 — Edge Stack e Plug-and-Play

### Objetivo

Tudo que vai pro Mini PC empacotado e provisionável com script único. Quando o PC chegar na RVB, em 30 minutos está rodando.

### `deployments/edge/docker-compose.yml`

```yaml
version: '3.9'

services:
  mosquitto:
    image: eclipse-mosquitto:2.0
    restart: unless-stopped
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
      - mosquitto-data:/mosquitto/data
    networks: [edge-net]

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD} --maxmemory 1gb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    networks: [edge-net]

  mediamtx:
    image: bluenviron/mediamtx:1.8.0
    restart: unless-stopped
    volumes:
      - ./mediamtx.yml:/mediamtx.yml:ro
    networks: [edge-net]

  camera-gateway:
    image: ghcr.io/logikos33/camera-gateway:${EDGE_IMAGE_TAG}
    restart: unless-stopped
    env_file: .env
    environment:
      DEPLOYMENT_MODE: edge
    depends_on: [redis, mediamtx]
    networks: [edge-net]

  inference:
    image: ghcr.io/logikos33/inference:${EDGE_IMAGE_TAG}
    restart: unless-stopped
    env_file: .env
    environment:
      DEPLOYMENT_MODE: edge
      INFERENCE_ENGINE: deepstream
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu, video]
    volumes:
      - ../../deepstream:/opt/deepstream-configs:ro
      - models-cache:/opt/models
    depends_on: [redis, mosquitto]
    networks: [edge-net]

  ws-gateway:
    image: ghcr.io/logikos33/ws-gateway:${EDGE_IMAGE_TAG}
    restart: unless-stopped
    env_file: .env
    environment:
      WS_GATEWAY_MODE: edge
    depends_on: [redis]
    networks: [edge-net]
    ports:
      - "8443:8443"  # HTTPS LAN com cert self-signed

  edge-sync-agent:
    image: ghcr.io/logikos33/edge-sync-agent:${EDGE_IMAGE_TAG}
    restart: unless-stopped
    env_file: .env
    secrets:
      - device_token
    volumes:
      - sync-data:/var/lib/edge-sync
      - models-cache:/opt/models:rw  # baixa modelos novos aqui
    depends_on: [mosquitto, redis]
    networks: [edge-net]
    ports:
      - "8444:8443"  # Mirror API LAN

  watchtower:
    image: containrrr/watchtower:latest
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      WATCHTOWER_POLL_INTERVAL: 300
      WATCHTOWER_LABEL_ENABLE: true
      WATCHTOWER_INCLUDE_RESTARTING: true
    command: --label-enable

secrets:
  device_token:
    file: /etc/recognition/device_token

volumes:
  mosquitto-data:
  redis-data:
  sync-data:
  models-cache:

networks:
  edge-net:
    driver: bridge
```

### `deployments/edge/install.sh`

Script idempotente que provisiona o Mini PC do zero:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Pré-requisito: rodar como root
[[ $EUID -eq 0 ]] || { echo "Run as root"; exit 1; }

INSTALL_DIR=/opt/recognition
LOG_FILE=/var/log/recognition-install.log

log() { echo "[$(date +%Y-%m-%dT%H:%M:%S)] $*" | tee -a "$LOG_FILE"; }

log "=== Recognition Edge Installer ==="

# 1. NVIDIA driver + container toolkit
log "Installing NVIDIA stack..."
bash ./nvidia-setup.sh

# 2. Docker
log "Installing Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | bash
fi

# 3. Tailscale
log "Setting up Tailscale..."
bash ./tailscale-setup.sh

# 4. Cloudflare Tunnel
log "Setting up Cloudflare Tunnel..."
bash ./cloudflared-setup.sh

# 5. UFW firewall
log "Configuring firewall..."
bash ./ufw-rules.sh

# 6. Recognition install dir
log "Creating install directory..."
mkdir -p "$INSTALL_DIR" /etc/recognition /var/lib/recognition /var/log/recognition

# 7. Copy compose files
cp -r ../../deepstream "$INSTALL_DIR/"
cp docker-compose.yml "$INSTALL_DIR/"
cp -r ../../models/manifests "$INSTALL_DIR/models-manifests"

# 8. Check .env
if [[ ! -f /etc/recognition/.env ]]; then
    log "ERROR: /etc/recognition/.env not found"
    log "Copy .env.template, fill values, then re-run."
    exit 1
fi
ln -sf /etc/recognition/.env "$INSTALL_DIR/.env"

# 9. Enrollment (one-time)
if [[ ! -f /etc/recognition/device_token ]]; then
    log "Performing first-time enrollment..."
    chmod 600 /etc/recognition/.env
    source /etc/recognition/.env
    
    response=$(curl -fsSL -X POST "$CLOUD_URL/api/v1/edge/enrollment/redeem" \
        -H "Content-Type: application/json" \
        -d "{
            \"enrollment_token\": \"$ENROLLMENT_TOKEN\",
            \"edge_version\": \"$EDGE_IMAGE_TAG\",
            \"host_info\": $(./host_info.sh)
        }")
    
    device_token=$(echo "$response" | jq -r .data.device_token)
    [[ -n "$device_token" && "$device_token" != "null" ]] || { log "Enrollment failed"; exit 1; }
    
    umask 077
    echo "$device_token" > /etc/recognition/device_token
    log "Enrollment successful. Token saved."
fi

# 10. Pull images
log "Pulling Docker images..."
cd "$INSTALL_DIR"
docker compose pull

# 11. Start stack
log "Starting stack..."
docker compose up -d

# 12. Wait healthy
log "Waiting for services to be healthy..."
sleep 10
docker compose ps

# 13. Systemd service pra resiliência
cp ../../deployments/edge/recognition.service /etc/systemd/system/
systemctl enable recognition

log "=== Install complete ==="
log "Run 'docker compose -f $INSTALL_DIR/docker-compose.yml logs -f' to follow logs."
```

### `deployments/edge/.env.template`

```bash
# Identidade do site
SITE_SLUG=rvb-blumenau-01
TENANT_SLUG=rvb

# Versão de imagem (Watchtower segue isso)
EDGE_IMAGE_TAG=1.0.0

# Cloud
CLOUD_URL=https://api.recognition.logikos.com.br

# Enrollment (one-time, descartado após uso)
ENROLLMENT_TOKEN=

# Cloudflare Tunnel (gerado no provisionamento)
CLOUDFLARE_TUNNEL_TOKEN=

# Tailscale (gerado no provisionamento)
TAILSCALE_AUTH_KEY=

# Redis local
REDIS_PASSWORD=

# MQTT local
MQTT_USERNAME=edge
MQTT_PASSWORD=

# MediaMTX
RTSP_USER=
RTSP_PASS=

# Cert HTTPS LAN (gerado por site)
LAN_CERT_PATH=/etc/recognition/lan.crt
LAN_KEY_PATH=/etc/recognition/lan.key

# Roboflow (pra baixar modelos)
ROBOFLOW_API_KEY=

# Logging
LOG_LEVEL=info
```

### Critérios de aceitação

- [ ] `install.sh` provisiona Ubuntu 22.04 limpo em <30min
- [ ] Idempotente: rodar 2x não quebra nada
- [ ] Enrollment one-time funciona
- [ ] `docker compose up -d` sobe todos os serviços com healthchecks
- [ ] Watchtower configurado mas conservador (não auto-update major versions)
- [ ] UFW só libera portas necessárias
- [ ] Systemd service garante resiliência a reboot

---

## 12. Fase 7 — Frontend Dual Mode

### Objetivo

Frontend detecta se cloud está acessível e faz fallback automático pra edge LAN quando necessário. Operador da RVB consegue ver câmeras mesmo com internet caída.

### `apps/frontend/src/hooks/useDualMode.ts`

```typescript
import { useEffect, useState } from 'react';

type Mode = 'cloud' | 'edge' | 'detecting';

interface DualModeState {
  mode: Mode;
  apiBaseUrl: string;
  isOnline: boolean;
}

const CLOUD_URL = import.meta.env.VITE_API_CLOUD_URL;
const EDGE_FALLBACK_KEY = 'recognition.edge.url';

export function useDualMode(): DualModeState {
  const [state, setState] = useState<DualModeState>({
    mode: 'detecting',
    apiBaseUrl: CLOUD_URL,
    isOnline: false,
  });

  useEffect(() => {
    let cancelled = false;
    
    async function detect() {
      try {
        const r = await fetch(`${CLOUD_URL}/api/v1/health`, { 
          signal: AbortSignal.timeout(3000) 
        });
        if (r.ok && !cancelled) {
          setState({ mode: 'cloud', apiBaseUrl: CLOUD_URL, isOnline: true });
          return;
        }
      } catch (e) {
        // Cloud inacessível, tenta edge
      }
      
      const edgeUrl = localStorage.getItem(EDGE_FALLBACK_KEY);
      if (edgeUrl) {
        try {
          const r = await fetch(`${edgeUrl}/api/v1/health`, { 
            signal: AbortSignal.timeout(3000) 
          });
          if (r.ok && !cancelled) {
            setState({ mode: 'edge', apiBaseUrl: edgeUrl, isOnline: true });
            return;
          }
        } catch (e) {
          // Edge também inacessível
        }
      }
      
      if (!cancelled) {
        setState({ mode: 'cloud', apiBaseUrl: CLOUD_URL, isOnline: false });
      }
    }
    
    detect();
    const interval = setInterval(detect, 15000); // re-check a cada 15s
    
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return state;
}
```

### UI feedback

Quando em modo edge, banner amarelo no topo:
> ⚠️ Modo Offline (LAN) — Conectado ao servidor local. Algumas funcionalidades como histórico completo estão limitadas.

### Endpoints disponíveis em modo edge

Subset funcional via mirror API do `edge-sync-agent`:

| Endpoint | Cloud | Edge |
|----------|-------|------|
| `/api/v1/health` | ✓ | ✓ |
| `/api/v1/cameras` | ✓ | ✓ (cache) |
| `/api/v1/streams/{id}/hls.m3u8` | ✓ (via tunnel) | ✓ (LAN direto) |
| `/api/v1/alerts/recent` | ✓ (90d histórico) | ✓ (não-uploaded + 24h cache) |
| `/api/v1/dashboard/stats` | ✓ | ✓ (limitado a 24h) |
| `/api/v1/admin/*` | ✓ | ✗ |
| `/api/v1/training/*` | ✓ | ✗ |
| `/api/v1/reports/*` | ✓ | ✗ |

### Critérios de aceitação

- [ ] `useDualMode` detecta queda de cloud em <5s
- [ ] Fallback automático pra edge se URL configurada
- [ ] Banner UI claro indica modo edge
- [ ] Endpoints "edge-only" disponíveis em modo offline
- [ ] Cert self-signed do edge aceito pelo browser (instalação documentada)

---

## 13. Fase 8 — Provisionamento RVB

### Objetivo

Pré-provisionar TUDO no admin do cloud antes do PC chegar.

### Atividades no admin

1. **Criar tenant RVB** (ou atualizar existente):
   - `slug: rvb`
   - `deployment_mode: edge`
   - `name: RVB Isolantes`

2. **Criar site `rvb-blumenau-01`**:
   - Status inicial: `pending`
   - Location: "Fábrica Blumenau/SC"

3. **Cadastrar as 42 câmeras** (4 fases):
   - Phase 1 (Fase imediata): 15 EPI + 8 Estacionamento + 5 Qualidade = 28
   - Phase 2: +5 EPI
   - Phase 3: +5 EPI
   - Phase 4: +4 Estacionamento
   - Para cada: nome, IP no DVR, módulo, status `pending`

4. **Atribuir módulos ao tenant**:
   - EPI: ativo
   - Fueling: ativo (Estacionamento)
   - Quality: ativo

5. **Importar/atribuir modelos**:
   - EPI: v3 (último treinado no Roboflow)
   - Fueling: v1
   - Quality: v1

6. **Configurar regras YAML**:
   - EPI: "no_helmet por 3s consecutivos" → alerta
   - EPI: "no_vest em zona de produção" → alerta
   - Fueling: "carro entrando sem badge" → notificação
   - Quality: trigger manual por tablet

7. **Gerar enrollment token**:
   - Single-use, válido 24h
   - Salva no admin pra colar no `.env` do edge

8. **Configurar Cloudflare Tunnel**:
   - Subdomain `rvb.recognition.logikos.com.br` apontando pro tunnel do edge

9. **Configurar DNS LAN** (cliente provisiona):
   - `edge.rvb.local` → IP do Mini PC

10. **Imprimir runbook** `docs/runbooks/edge-rvb-onboarding.md`

### Critérios de aceitação

- [ ] Tenant + site criados no admin
- [ ] 42 câmeras pré-cadastradas com metadata
- [ ] Modelos atribuídos
- [ ] Regras YAML aplicadas
- [ ] Enrollment token gerado, anotado em local seguro
- [ ] Runbook impresso

---

## 14. Fase 9 — Test Harness

### Objetivo

Antes do PC ir pra RVB, validar TODOS os cenários localmente. Test harness simula edge + cloud em containers.

### Estrutura

```
tests/harness/
├── docker-compose.harness.yml
├── fixtures/
│   ├── synthetic-rtsp/          # MediaMTX serve vídeos sintéticos como RTSP
│   │   ├── epi-cam-01.mp4       # 30min loop, contém eventos planejados
│   │   ├── epi-cam-02.mp4
│   │   └── ...
│   ├── tenants.sql              # Seeds: tenant rvb, site harness-01
│   ├── camera-config.yaml       # Cadastro das 28 câmeras simuladas
│   └── enrollment-tokens.txt    # Tokens pre-criados pro harness
├── scenarios/
│   ├── 01-edge-online-baseline.py
│   ├── 02-edge-offline-recovery.py
│   ├── 03-model-rollout.py
│   ├── 04-42-cameras-load.py
│   ├── 05-multi-tenant-isolation.py
│   ├── 06-device-token-rotation.py
│   ├── 07-enrollment-flow.py
│   └── 08-frontend-dual-mode.py
├── runner/
│   ├── __init__.py
│   ├── harness.py               # Orchestra docker compose, executa cenários
│   ├── assertions.py            # Helpers: assert_event_received, assert_alert_in_dashboard
│   ├── fault_injection.py       # Simula queda de cloud, latência, perda de pacote
│   └── reports.py
├── reports/                     # Saída de runs (gitignored)
└── README.md
```

### Cenários críticos

**Cenário 1: Edge online baseline**
- Edge sobe, faz enrollment
- 28 câmeras streamando
- DeepStream detecta eventos
- Eventos chegam no cloud em <5s
- Frontend cloud mostra alertas em real-time

**Cenário 2: Edge offline recovery**
- Edge rodando normalmente
- Cloud "cai" (fault injection: bloqueia rede)
- Edge continua inferindo, eventos vão pra SQLite
- Frontend frontend automaticamente faz fallback pra edge LAN
- 1h depois, cloud volta
- Edge drena buffer, todos os eventos chegam no cloud em ordem
- Frontend volta automaticamente pra cloud

**Cenário 3: Model rollout**
- Modelo EPI v4 publicado no Roboflow
- API publica novo manifest
- Edge detecta via polling
- Baixa novo modelo, valida checksum
- Hot-swap sem perda de eventos
- Próximos eventos usam modelo novo

**Cenário 4: Carga 42 câmeras**
- 42 streams sintéticos rodando
- DeepStream batch=15 EPI + batch=8 Fueling + batch=7 Quality
- GPU usage <90%
- Latência por evento <500ms
- Zero frame drops em 1h de execução

**Cenário 5: Multi-tenant isolation**
- 2 tenants (rvb, harness-fake)
- Cada um com seu site
- Site rvb publica eventos
- Verifica que API harness-fake **não** vê eventos do rvb
- Tenta usar device token do harness-fake pra postar em rvb → 403

### Critérios de aceitação

- [ ] 8 cenários implementados e passam
- [ ] Cenário 4 (42 câmeras) executa por 1h sem erro
- [ ] Cenário 2 (offline recovery) com zero perda de eventos
- [ ] Reports gerados em `tests/harness/reports/`
- [ ] CI executa subset dos cenários (rápidos) em cada PR
- [ ] Cenário completo (slow) rodado manualmente antes do RVB go-live

---

## 15. Fase 10 — Plug-and-Play Day

### Objetivo

O dia que o Mini PC chega na RVB. Tudo pronto pra rodar em <30 minutos.

### Checklist do dia

**Pré-chegada (já feito):**
- [ ] Phase 0-9 fechadas, harness verde
- [ ] Provisionamento Phase 8 completo
- [ ] Enrollment token gerado e em mãos
- [ ] Runbook impresso
- [ ] Acesso ao DVR Intelbras testado (mesmo que via VPN cliente)

**Day-of:**

1. [ ] Abrir o Mini PC, conectar:
   - Energia
   - Rede (LAN da fábrica)
   - Monitor + teclado (provisionamento)

2. [ ] Boot Ubuntu 22.04 LTS (já pré-instalado em fábrica antes de mandar)

3. [ ] Configurar IP estático na LAN da fábrica

4. [ ] Conectar à internet (validar)

5. [ ] `git clone https://github.com/logikos33/recognition.git /opt/recognition-source`

6. [ ] `cd /opt/recognition-source/deployments/edge`

7. [ ] `cp .env.template /etc/recognition/.env`

8. [ ] Editar `.env`: preencher `ENROLLMENT_TOKEN`, `SITE_SLUG`, `TENANT_SLUG`, `CLOUDFLARE_TUNNEL_TOKEN`, `TAILSCALE_AUTH_KEY`, passwords, etc

9. [ ] `sudo bash install.sh`

10. [ ] Aguardar conclusão (~25min)

11. [ ] Validar serviços: `docker compose ps`

12. [ ] Validar streaming: abrir 4 câmeras no live view LAN (`https://edge.rvb.local:8443`)

13. [ ] Validar cloud: abrir dashboard (`https://app.recognition.logikos.com.br`) → site `rvb-blumenau-01` aparece como `active`

14. [ ] Validar eventos: aguardar 5min, verificar que alertas EPI estão chegando

15. [ ] Configurar DNS LAN no roteador da RVB (`edge.rvb.local` → IP do Mini PC)

16. [ ] Instalar cert self-signed nos browsers que vão acessar LAN

17. [ ] Treinar operador da fábrica: como ver dashboards, o que fazer se alerta

18. [ ] Documentar incidentes do dia em `docs/runbooks/rvb-deployment-incident-log.md`

### Critérios de aceitação

- [ ] Sistema rodando em <2h desde a chegada do PC
- [ ] 28 câmeras streamando (Phase 1 das 4 do contrato)
- [ ] Pelo menos 5 alertas EPI processados no primeiro dia
- [ ] Operador RVB consegue acessar dashboard LAN sozinho
- [ ] Monitoramento Sentry/Slack ativo

---

## 16. Critérios Globais de Aceitação

Pra considerar o projeto pronto pra entrega:

- [ ] Todas as 10 fases técnicas + 4 fases de segurança completas
- [ ] Repo `recognition` privado com branch protection
- [ ] CI/CD verde
- [ ] Coverage de testes >65% nos serviços novos (edge-sync-agent, blueprint edge)
- [ ] Coverage do api total mantido em >60%
- [ ] Documentação completa: GSD + 10 SDDs + 10 ADRs + runbooks
- [ ] Test harness com 8 cenários passando
- [ ] Edge RVB rodando 28 câmeras em produção
- [ ] Zero incidente crítico de segurança em 30 dias pós-launch
- [ ] LGPD pendência documentada e em encaminhamento jurídico
- [ ] Disaster recovery plan testado em harness

---

## 17. Apêndice A — Templates de Documentação

### ADR Template

```markdown
# ADR-XXXX: <Título da decisão>

## Status
Proposto | Aceito | Substituído por ADR-YYYY | Obsoleto

## Data
YYYY-MM-DD

## Contexto
[1-3 parágrafos descrevendo o problema/situação que levou à decisão]

## Decisão
[Decisão clara, 1-2 parágrafos]

## Alternativas consideradas

### Alternativa A: <nome>
- Prós: ...
- Contras: ...

### Alternativa B: <nome>
- Prós: ...
- Contras: ...

## Consequências

### Positivas
- ...

### Negativas
- ...

### Neutras
- ...

## Implementação
[Como implementar, se aplicável]

## Referências
- [Doc relacionado]
- [Pesquisa que embasou]
```

### SDD Template (por serviço)

```markdown
# SDD: <nome-do-serviço>

**Versão:** X.Y.Z
**Última atualização:** YYYY-MM-DD
**Owner:** <nome>

## Propósito
[1 parágrafo sobre o que esse serviço faz]

## Responsabilidades
- Faz X
- Faz Y
- Faz Z

## Não-responsabilidades
- NÃO faz A (quem faz: serviço-tal)
- NÃO faz B

## Arquitetura interna
```mermaid
graph LR
  ...
```

## Contratos

### Entrada
- HTTP: <endpoints expostos> (referencia `shared/proto/<spec>.yaml`)
- Redis: <channels assinados>
- MQTT: <topics assinados>

### Saída
- HTTP: <endpoints chamados> (referencia `shared/proto/<spec>.yaml`)
- Redis: <channels publicados>
- MQTT: <topics publicados>
- DB: <tabelas escritas>

## Configuração
| Env Var | Tipo | Default | Descrição |
|---------|------|---------|-----------|
| FOO_BAR | str | — | Obrigatório |
| FOO_BAZ | int | 30 | Opcional |

## Decisões locais
- Por que X? → ADR-NNNN
- Por que Y? → log em docs/decisions/log.md#YYYY-MM-DD

## Como rodar local
```bash
cd services/<nome>
docker-compose -f ../../docker-compose.dev.yml up <nome>
```

## Como testar
```bash
cd services/<nome>
pytest
```

## Métricas e observabilidade
- Logs: <onde>
- Métricas Prometheus: <quais>
- Healthchecks: GET /health, /health/ready, /health/deps

## Troubleshooting comum
- Problema X → solução Y
```

### GSD (General System Description) — esqueleto

```markdown
# GSD: Recognition Platform

## 1. Visão geral
[1 página explicando o que é Recognition em alto nível]

## 2. Stakeholders
- Cliente final (operador da fábrica)
- Gestor (consome dashboards)
- Logikos (operadora da plataforma)
- Anotador (treina modelos)

## 3. Capacidades
- Detecção de objetos/situações em CCTV
- Treinamento contínuo
- Alertas em tempo real
- Multi-tenant
- Edge ou cloud-only

## 4. Arquitetura macro
[Diagrama de alto nível]

## 5. Componentes
[Tabela: nome, responsabilidade, ADRs relacionados, SDDs]

## 6. Fluxos principais
- Fluxo de detecção
- Fluxo de treinamento
- Fluxo de provisionamento de cliente

## 7. Modelos de deploy
- Edge
- Cloud-only

## 8. Restrições e premissas
[Lista]

## 9. Glossário
[Termos]
```

---

## 18. Apêndice B — Prompts Prontos pro Claude Code

> **Convenção:** todo prompt começa com `ralph:` se for execução persistente. Senão é one-shot diagnóstico → plano → execução com gates.

### Prompt — Fase 0

```
ralph: Executa a Fase 0 do EDGE_DEPLOYMENT_PLAN.md (Reorganização e Renomeação).

Pré-requisito: este repo já foi renomeado pra `recognition` no GitHub e tornado privado por mim manualmente.

Sua missão é:
1. Remover o gitlink órfão painel-adm/ conforme ADR-0011:
   - git rm --cached painel-adm
   - git worktree remove painel-adm
   - git tag archive/microservices-attempt-1 refs/heads/painel-adm
   - git push origin archive/microservices-attempt-1

2. Mover diretórios via `git mv` conforme descrito na Seção 5 do plano:
   - backend/ → services/api/
   - inference-service/ → services/inference/
   - frontend/ → apps/frontend/
   - landing-page/ → apps/landing/
   - backend/migrations/ → infra/migrations/
   - docs/EDGE_AGENT_ARCHITECTURE.md → docs/architecture/EDGE_AGENT_ARCHITECTURE.md

   NÃO fazer git mv de camera-gateway, ws-gateway, auth-service, training-service
   ou scheduler-service — esses serviços foram removidos de staging em maio/2026
   e serão criados do zero na Fase 3 (ver ADR-0014).

3. Criar os diretórios novos listados na Seção 3 do plano.

4. Atualizar TODOS os paths em:
   - Dockerfiles (COPY/WORKDIR)
   - railway.toml de cada serviço
   - Imports relativos nos arquivos Python
   - vite.config.ts, tsconfig.json no frontend
   - .github/workflows/* se existir
   - README.md raiz

5. Criar AGENT.md raiz seguindo o template da Seção 17.
6. Criar AGENT.md + SDD.md (esqueleto) em cada services/*/.
7. Escrever os 10 ADRs da Seção 2 em docs/decisions/adr/, conforme template.
8. Escrever GSD em docs/architecture/GSD.md conforme template.
9. Criar docker-compose.dev.yml na raiz que sobe TODOS os serviços localmente.
10. Configurar .github/workflows/ci.yml com lint (ruff) + test (pytest) + build.
11. Configurar .github/workflows/security-scan.yml com gitleaks.
12. Atualizar .gitignore conforme Seção 4 da trilha S.

Restrições:
- Use git mv pra preservar histórico. Nunca cp/rm.
- Faça commits atômicos por subtarefa (ex: "feat(repo): move backend to services/api", "docs(adr): write ADR-0001 deepstream-vs-ultralytics").
- Branch: feature/phase-0-reorg. Não faça merge sozinho.
- Para cada serviço movido, valide que o Dockerfile builda local antes de seguir.
- Se algo der errado, NÃO continue. Pare, documente em docs/runbooks/phase-0-issues.md, e espere instrução.

Critérios de aceitação ao final:
- Estrutura final conforme Seção 3 do plano
- Todos os Dockerfiles buildam
- docker-compose.dev.yml sobe sem erro
- CI verde
- 10 ADRs + GSD + 10 SDD esqueletos escritos
- AGENT.md raiz + 10 AGENT.md por serviço

Quando terminar, abre PR pra develop com checklist marcado.
```

### Prompt — Fase 1

```
ralph: Executa a Fase 1 do EDGE_DEPLOYMENT_PLAN.md (Schema e Models de Edge).

Branch: feature/phase-1-edge-schema

Tarefas:
1. Criar migrations 042, 043, 044, 045 conforme Seção 6 do plano, em infra/migrations/.
2. Aplicar migrations em staging (use o psql via Railway CLI).
3. Criar package recognition_shared em shared/python/recognition_shared/:
   - models/edge.py (Pydantic, conforme Seção 6 do plano)
   - auth/jwt_device.py (skeleton, implementação completa fica pra Fase 2)
   - events/__init__.py (skeleton)
   - logging/structlog_config.py
   - pyproject.toml ou setup.py
4. Atualizar requirements.txt de services/api/ pra instalar recognition_shared em modo editable.
5. Adicionar test unitário pra cada model Pydantic em shared/python/tests/.
6. Atualizar SDD do services/api/ pra mencionar tabelas novas.

Restrições:
- Migrations idempotentes (ADD COLUMN IF NOT EXISTS, CREATE TABLE IF NOT EXISTS)
- NÃO usar DROP em nenhuma migration
- Tests com pytest

Critérios de aceitação:
- 4 migrations rodam 2x sem erro
- recognition_shared importável: `from recognition_shared.models.edge import EdgeSite`
- Coverage >80% nos models
- PR pra develop com testes verdes
```

### Prompt — Fase 2

```
ralph: Executa a Fase 2 do EDGE_DEPLOYMENT_PLAN.md (Blueprint /api/v1/edge/).

Branch: feature/phase-2-edge-api

Pré: Fase 1 fechada (recognition_shared disponível).

Tarefas:
1. Escrever shared/proto/edge-api.yaml (OpenAPI 3.1) com todos os endpoints da Seção 7.
2. Escrever shared/proto/events.yaml (AsyncAPI 2.6) com schemas de eventos.
3. Implementar middleware em services/api/app/api/v1/edge/middleware.py:
   - require_device_token(*scopes) decorator
   - Validação de RS256, scope check, tenant check
4. Implementar todos os endpoints listados na Seção 7.
5. Implementar lógica de idempotência em /events/batch via X-Batch-Id em Redis (TTL 24h).
6. Implementar rotação de device token automática (Celery beat task: a cada hora, verifica tokens próximos do vencimento, gera novos, marca antigos como rotated).
7. Implementar enrollment one-time:
   - Endpoint POST /api/v1/edge/enrollment/redeem
   - Marca enrollment_token como redeemed
   - Gera device token RS256, salva hash em device_tokens, retorna JWT pro cliente
8. Implementar persistência de eventos:
   - DetectionEvent → camera_events
   - AlertEvent → alerts
   - CountingEvent → counting_events
   - Publica em Redis pra ws-gateway-cloud distribuir
9. Adicionar rate limiting com flask-limiter:
   - /events/batch: 60/min por site
   - /config/poll: 30/min por site
   - /enrollment/redeem: 5/hour por IP
10. Tests:
    - Unitários: middleware, parse de eventos, rotação
    - Integration: fluxo completo enrollment → token → batch → persistência
11. Atualizar SDD do services/api/.

Restrições:
- TODO endpoint valida tenant_id do token vs tenant_id no payload
- TODO write valida site_id também
- Logs estruturados (structlog), sem PII
- Errors retornam {status: 'error', data: {reason: '...'}}, nunca expõe stack trace

Critérios de aceitação:
- edge-api.yaml passa em validator OpenAPI 3.1
- Tests >70% coverage em app/api/v1/edge/
- Swagger UI acessível em /api/v1/edge/docs
- PR verde
```

### Prompts subsequentes

Pros prompts das fases 3-10 seguem o mesmo padrão. Vou te entregar eles **separadamente** pra evitar que esse documento fique infinito. Cada prompt segue a estrutura:

- `ralph:` se persistente
- Branch específica
- Pré-requisitos
- Tarefas numeradas
- Restrições
- Critérios de aceitação
- PR pra develop

---

## Mantendo o plano vivo

Este documento NÃO é estático. Quando o Claude Code descobrir algo que muda o plano (incompatibilidade técnica, premissa errada, etc), ele deve:

1. Documentar a descoberta em `docs/decisions/log.md`
2. Propor mudança no plano via PR (modificando `docs/EDGE_DEPLOYMENT_PLAN.md`)
3. Esperar revisão antes de prosseguir

O plano vence o código. Se o código contradiz o plano, é o código que está errado (ou o plano precisa ser atualizado conscientemente).

---

**Fim do plano.**

Próximos artefatos a ser produzidos pelo Claude Code:
- 10 ADRs
- GSD
- 10 SDDs
- shared/proto/edge-api.yaml
- shared/proto/events.yaml
- Test harness com 8 cenários
- deployments/edge/* completo

Boa execução. 🚀
