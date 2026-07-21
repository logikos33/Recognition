# Diagnóstico — Observabilidade do Edge (pandora ↛ admin cloud)

> **Data:** 2026-07-21 · **Escopo:** ambiente de TESTE (Jetson `pandora`, `pandora@100.93.126.76` via Tailscale).
> **Método (C-04):** diagnosticado contra o sistema REAL rodando dos DOIS lados — SSH read-only no pandora + API
> de produção da nuvem + leitura do código na develop. Nada foi modificado no box nem promovido a staging/main.

## Sintoma
O Jetson de teste está ligado e gerando dados (4 pipelines DeepStream + coletor de telemetria rodando há dias),
mas o admin da plataforma **não reflete NADA** — nem saúde do device, nem detecções, nem telemetria, nem métricas
de modelo.

## Achado central (a causa-raiz, em uma frase)
**O pandora foi montado como uma stack de SOAK 100% LOCAL e auto-contida; os sinks de upload para a nuvem estão
desligados e o device nunca foi enrolado contra o control plane que o admin lê. Nada sai do box para a nuvem.**
Secundariamente, mesmo com o box configurado, há **duas pilhas de observabilidade desconectadas** no código
(heartbeat vs. "dashboard integrado") e um **descompasso de auth** (bearer estático vs. RS256 assinado) que
precisam ser resolvidos para as 4 superfícies fecharem.

Isto **confirma a hipótese principal** da tarefa.

---

## O que está rodando no pandora (evidência SSH, read-only)

```
ps aux  →  (todos processos do usuário pandora, jul18→hoje)
  python3 -m app.telemetry                         # coletor task-100 (cwd=/home/pandora/recognition-edge-telemetry)
  4× deepstream-app -c .../app_mm_all_prod_{epi,park,qaux,qmain}.txt   # pipelines multi-módulo
  soak113/micromamba/envs/pg/bin/postgres -D soak113/pgdata           # POSTGRES LOCAL
  soak113/redis/src/redis-server 127.0.0.1:6390                        # REDIS LOCAL
  soak113/.../gunicorn ... app:create_app() --bind 0.0.0.0:8090        # API cloud rodando LOCALMENTE no Jetson
  soak113/scripts/soak_{sampler,producer,consumer}.py                  # harness de soak

ss -tlnp  →  LISTEN em :8090 (api local), :6390 (redis), :5442 (postgres), :22 (ssh). Nada mais.
```

**Config real dos processos (lida de `/proc/<pid>/environ`):**
```
API local (pid 4986):
  DATABASE_URL=postgresql://recognition@127.0.0.1:5442/recognition   # ← LOCAL
  REDIS_URL=redis://127.0.0.1:6390/0                                  # ← LOCAL
  SERVICE_TYPE=api   DEPLOYMENT_MODE=edge

Coletor de telemetria (pid 1546):
  EDGE_DEVICE_ID=pandora-orin-rvb-provisorio
  EDGE_TELEMETRY_PHASE=idle
  EDGE_TELEMETRY_DIR=/home/pandora/edge-telemetry
  EDGE_VERSION=task-100-mvp
  # grep -c EDGE_API_URL  →  0   ← SINK DE HEARTBEAT DESLIGADO (sem URL da nuvem, sem bearer)
```

**Outras evidências no box:**
- Coletor grava JSONL local ativamente: `~/edge-telemetry/idle_20260718T151353Z.jsonl` = **30 MB, crescendo hoje**.
- Redis local só tem chaves `soak:evidence:*` (harness) — **nenhuma `detections:*`/`det:*`** (o canal ADR-0002 não é publicado).
- **Nenhum processo** `uploader`/`command_poller`/`config_poller`/`edge_sync` rodando → nada posta detecção à nuvem.
- `EDGE_DEVICE_ID=...-provisorio` → id provisório, coerente com "nunca enrolado de verdade contra a nuvem".
- Métricas de treino existem em `~/jetson-experiments/mm/train_metrics/` (dados do shootout — fonte da superfície 4).

## O que a nuvem responde (probe HTTP, `api-v3-production-2b22.up.railway.app`)
```
200  GET  /health
401  GET  /api/v1/edge/overview            # existe, exige JWT admin
401  GET  /api/v1/edge/sites/health        # existe, exige JWT admin
401  POST /api/v1/edge/heartbeat           # existe, exige device RS256 (heartbeat:write)
401  POST /api/v1/edge/events/ingest       # existe, exige device RS256 (events:write)
```
→ **A nuvem está pronta para receber.** As rotas existem e exigem auth de device. O edge simplesmente não envia.

---

## Diagnóstico por superfície (onde a cadeia quebra)

### As duas pilhas desconectadas (contexto para as superfícies 1 e 2)
- **Pilha A (heartbeat/frota):** device → `POST /api/v1/edge/heartbeat` (device RS256, `heartbeat:write`) →
  tabela `edge_heartbeats` → painel admin `EdgeFleetPanel.tsx` (aba "edge" da observabilidade). **É a pilha que o
  coletor task-100 mira.** Cloud + frontend **CONSTRUÍDOS**.
- **Pilha B (task-112 "Dashboard Integrado"):** `POST /api/v1/dashboard/edge-telemetry` (**JWT de usuário, NÃO
  device auth**) → tabela `edge_telemetry_samples` → `DashboardIntegradoPage.tsx` (gauges ao vivo + SocketIO
  `/monitor`). **Só é alimentada por um SEED script** (`seed_dashboard_observability.py`). Nenhum caminho de
  device vivo a alimenta.
- As duas **não se juntam**: mesmo com heartbeats reais chegando (Pilha A), o dashboard "ao vivo" (Pilha B) lê
  outra tabela alimentada só por seed.

| # | Superfície | Cadeia pretendida | Onde QUEBRA | Estado |
|---|---|---|---|---|
| 1 | **Saúde edge/frota** | coletor → `/edge/heartbeat` → `edge_heartbeats` → `EdgeFleetPanel` | **Edge não envia:** coletor sem `EDGE_API_URL`/`EDGE_DEVICE_BEARER` (sink off) **e** device não enrolado contra a nuvem. Cloud+front prontos. | Cloud **BUILT**, envio **OFF** (config+enrollment) |
| 2 | **Telemetria ao vivo** | coletor → ingest → tabela → gauges ao vivo | **(a)** coletor só grava JSONL local (sink off); **(b)** o painel ao vivo (Pilha B) lê `edge_telemetry_samples`, que **nenhum device alimenta** (só seed) — e o ingest dele é **JWT, não device**. | Ingest+painel **BUILT** mas **sem caminho de device**; pilhas A/B não unidas |
| 3 | **Eventos & alertas** | detecção → `/edge/events/ingest` → `edge_events` → histórico/alerta admin | **Edge não envia:** uploader não roda **e** aponta para rota morta `/api/v1/edge/detections` (não existe; canônico é `/events/ingest`, issue #206/F3). **Frontend inexistente:** nenhum consumidor de `GET /edge/events`. | Ingest+tabela **BUILT**; sender morto; **front ausente** |
| 4 | **Métricas de modelo** | JSONL de treino → `/dashboard/training-metrics` → `model_training_metrics` → Training Studio | Stack completa **construída**, mas alimentada **só por seed** (`seed_dashboard_observability.py`); nenhum pipeline de treino posta automaticamente. Os JSONL do shootout existem (`docs/edge/train_metrics/*.jsonl`) e no box (`jetson-experiments/mm/train_metrics/`). | **BUILT (como demo)**, sem produtor automático |

### O descompasso de auth (bloqueia 1 e 2 mesmo após config)
`POST /edge/heartbeat` (`edge/routes.py:166-191`) exige um **JWT RS256 assinado pela chave privada do device**,
não-expirado, com `heartbeat:write` e claims batendo com o enrollment. O `HeartbeatSink`
(`edge-sync-agent/app/telemetry/__main__.py:56-58`) manda um **`Bearer {EDGE_DEVICE_BEARER}` estático** e **não
assina nem renova** nada. Então o bearer precisa SER um RS256 válido — que só o **enrollment** produz (e, se
long-lived, expira; o device deveria auto-assinar, ADR-0019 S7, mas o coletor não implementa signer).

---

## O que depende do VITOR (caminho crítico — PARADO, aguardando)
Nenhum código faz o admin refletir o pandora sem estes 3 passos (todos fora do meu alcance autônomo):

1. **Enrollment do pandora contra a nuvem** — gerar um enrollment-token
   (`POST /api/v1/edge/sites/<site_id>/enrollment-tokens`, JWT admin) e redimir no device
   (`POST /api/v1/edge/enroll`) para o device obter seu **token RS256** com escopos `heartbeat:write` + `events:write`.
2. **Configurar o box:** `EDGE_API_URL=https://api-v3-production-2b22.up.railway.app` + `EDGE_DEVICE_BEARER=<token
   RS256 do enrollment>` no `edge-telemetry.env`, e (re)iniciar o coletor (systemd
   `edge-telemetry-collector.service`) — precisa de **sudo**.
3. **Confirmar o site/tenant de teste** no qual enrolar (o `EDGE_DEVICE_ID` atual é `...-provisorio`).

Também precisa de decisão de Vitor: um **token JWT admin de leitura** para eu confirmar do lado da nuvem que o
`/edge/overview` está de fato vazio (o lado do envio já prova que nada chega; isto é só a confirmação simétrica).

---

## Plano Fase 2 (o delta de código, condicionado à decisão do Vitor)
Ordem por prioridade (o diagnóstico manda começar por 1):

1. **Saúde/frota (maior prioridade, sintoma direto):** o SENDER já existe (coletor). O fix é **config+enrollment
   (Vitor)** — não há código novo de sender a escrever. Após isso, `EdgeFleetPanel` renderiza online/offline +
   último heartbeat sem mudança de código. **Verificar** o descompasso de auth: se o bearer estático RS256 do
   enrollment funcionar até expirar, ok; se precisar auto-assinatura/renovação, é delta de código no coletor
   (edge, F-phase).
2. **Telemetria ao vivo — unir Pilha A → Pilha B (delta de código, verificável por teste):** fazer o heartbeat
   real alimentar o dashboard ao vivo. Duas opções (decisão de Vitor sobre qual dashboard é canônico):
   (a) o handler de `/edge/heartbeat` também gravar `edge_telemetry_samples` + publicar no socket `/monitor`; **ou**
   (b) o `DashboardIntegradoPage` passar a ler `edge_heartbeats` (Pilha A) em vez de `edge_telemetry_samples`.
   Sem tabela nova (reusa o existente). **Não construir antes de decidir qual pilha é canônica.**
3. **Eventos & alertas:** já rastreado — o sender é a consolidação do canal (issue #206 / F3, reshape de payload
   `{events:[...]}` + device auth). **Frontend ausente:** construir uma view admin consumindo `GET /edge/events`.
4. **Métricas de modelo:** stack pronta; falta o produtor automático (o pipeline de treino postar
   `/dashboard/training-metrics`). Para o teste, pode-se rodar o seed com os JSONL do shootout.

## Confirmação de escopo
- ✅ Diagnóstico feito contra o sistema real, dos dois lados, read-only. **Nada modificado no pandora.**
- ✅ **Nada promovido a staging/main.** Este doc vai por PR para `develop`.
- ⏸️ Fase 2 (código) **parada** aguardando as decisões do Vitor (enrollment/env/sudo + qual pilha é canônica).
