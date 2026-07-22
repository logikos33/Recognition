# Plano de Controle Edge — integração Recognition ↔ Edge

**Data:** 2026-07-18 · **Autor:** Vitor Emanuel (Logikos) · **Escopo:** plano de controle completo
**Premissa:** *controlar o Edge e a operação pelo front, sem tocar no código a todo momento.*
**Trilha de segurança:** separada (ver `PLANO_SEGURANCA_EDGE_2026-07-18.md`) — prioridade alta, não se mistura aqui.

> **Base de evidência:** varredura do repo real em 2026-07-18 (C-04 — validado no código, não em memória).
> Todo item abaixo tem caminho de arquivo. Onde diz "não existe", foi confirmado por `grep` no código.

---

## 1. O princípio, dito de forma testável

"Controlar pelo front sem tocar no código" só é verdade se valer esta frase:

> **Toda mudança de comportamento do Edge — modelo, FPS, ROI, threshold, regra, módulo, agenda — é uma
> escrita no banco pela UI, que chega ao Jetson por polling, sem SSH, sem editar arquivo, sem restart, sem deploy.**

Hoje essa frase é **falsa em quase toda a superfície**. Não por falta de UI ou de banco — os dois existem e são
bons — mas porque **a ponte entre o banco e o Jetson não existe**, e porque parte da config gravada **não tem
consumidor de runtime**.

**Critério de aceite do programa inteiro:** um operador muda o FPS de uma câmera na UI, e o pipeline no Jetson
passa a rodar naquele FPS em menos de 1 ciclo de poll, sem ninguém abrir um terminal. Hoje: impossível.

---

## 2. Estado real — o que existe, o que está quebrado, o que é decorativo

### 2.1 O que está SÓLIDO (não reconstruir)

| Área | Onde | Observação |
|---|---|---|
| Sites, enrollment, heartbeat, observabilidade de frota | `services/api/app/api/v1/edge/routes.py` (781 linhas) | Único blueprint edge maduro. 11 arquivos de teste de integração + `tests/security/test_edge_invariants.py`. `/heartbeat` é a **referência correta** de device auth |
| Modelo por câmera (task-045) | `cameras/model_handlers.py` · `cameras.model_{epi,quality,counting}_id` · migration `026_` | Caminho mais maduro do sistema. Resolução com fallback pro default do módulo + pub/sub `camera:model_change:{id}` |
| Operações (ROI, linha, zonas, threshold) | `operations/routes.py` · `operations.config` JSONB · migration `038_` | CRUD sólido, valida contra `OperationTypeRegistry` antes de persistir, DELETE exige `confirm_name` se há histórico |
| Cenário composto por câmera | `scenarios/routes.py` | Compõe câmera + módulos + classes + operações + regras + agenda. **É exatamente o payload que o edge precisa** — só está inacessível ao device |
| Hot-reload de modelo | `services/inference/inference/model_watcher.py` | Canal `model:reload`, baixa de R2, `engine.reload_model()` sem restart. Padrão a replicar |
| CRUD de câmera, probe SSRF-safe, retenção, integrações | `cameras/` (~1900 linhas, 12 arquivos) | Probe tem proteção SSRF + DNS pinning |

### 2.2 O que está QUEBRADO (conserto, não construção)

| # | Problema | Onde | Impacto |
|---|---|---|---|
| **B1** | `extract_device_id_unverified(request)` e `verify_device_token(request, ...)` recebem o **objeto `request` do Flask** onde a função espera a **string do token** → `jwt.decode()` sempre levanta `DecodeError` | `edge_commands/routes.py:32-48` · `edge_events/routes.py:41,49` | **Canal de comandos e de eventos nunca autenticou.** `GET /commands/pending`, `PATCH /commands/<id>`, `POST /events/ingest` inoperantes desde sempre. Zero testes nos dois blueprints |
| **B2** | Em `poll_pending_commands` a chamada de auth está **fora do `try`** → a exceção propaga crua | `edge_commands/routes.py` | Erro 500 em vez de 401 |
| **B3** | `docs/API_CONTRACT_MAP.md:22` afirma que o bug B1 "já foi corrigido em edge_commands" — **falso**, está presente nos dois | `docs/API_CONTRACT_MAP.md` | Doc mente sobre o código; induz a próxima sessão a erro |
| **B4** | `PATCH /site-gateways/<id>/status` tem docstring "usado pelo edge ao confirmar provisionamento", mas exige **JWT de usuário** | `site_gateways/routes.py` | O edge **não consegue** chamar a rota que foi feita pra ele |
| **B5** | `CountingLineOperation` registrada **duas vezes** | `operations/canonical/__init__.py:12,18` | Menor, mas indica registry sem validação de duplicata |

### 2.3 O que está AUSENTE (a ponte cortada)

| # | Falta | Evidência | Consequência |
|---|---|---|---|
| **A1** | **`GET /api/v1/edge/config/poll`** | `grep -n "config"` em `edge/routes.py` → **zero linhas**. Mas o cliente existe e está testado: `services/edge-sync-agent/app/config_poller.py:48`. E `docs/API_CONTRACT_MAP.md:218` **documenta a rota como existente** | **Nenhuma config chega ao Jetson.** É o gap arquitetural central |
| **A2** | **`POST /api/v1/edge/detections`** | Cliente em `edge-sync-agent/app/uploader.py:45` aponta pra rota que não existe na API | Detecções não sobem por esse caminho |
| **A3** | **Endpoint de download de modelo pro device** | ADR-0019 prevê escopo `models:download`; nenhum endpoint implementa | Device não busca o próprio modelo — distribuição manual |
| **A4** | **`/api/v1/edge/auth/rotate`** | ADR-0019 especifica; não existe | Sem rotação de chave sem re-enrollment |
| **A5** | **Todo o pipeline DeepStream** | `deepstream/{epi,quality,fueling,shared}/` = **só `.gitkeep`**. Nenhum `.txt` de nvinfer no repo inteiro | Não existe nem config estático nem gerador. A decisão "banco vs arquivo" está **em aberto** |
| **A6** | **Loop de produção das operações** | única chamada de `evaluate(` é `operations/routes.py:223` (o `/test`) | `operation_results` **não é populada por nenhum worker**. Operações não rodam em produção |
| **A7** | **operation-types do cenário RVB** | Registry tem 7 tipos; **faltam `attention_points`, `stage_timer`, `crowd_zone`, `dwell_zone`** | **Bloqueia o cenário RVB (ADR-0053)** — qualidade precisa de attention_points + stage_timer |
| **A8** | **Cliente de comandos no main tree** | `command_poller.py` só existe em `.claude/worktrees/`, não em `services/edge-sync-agent/app/` | Mesmo com B1 corrigido, não há quem consuma |

### 2.4 O que é UI DECORATIVA (grava no banco, não muda nada)

Este é o achado mais perigoso, porque **parece** que funciona.

| Config | Banco + UI | Consumidor de runtime | Comportamento real vem de |
|---|---|---|---|
| **FPS por câmera** | ✅ `cameras.fps_target` (migration `052_camera_fps_quality`), `config_handler.py`, `CameraFpsConfig.tsx` | ❌ **nenhum** — `grep fps_target` fora de migration/front/teste só acha o handler | `YOLO_INFERENCE_EVERY_N_FRAMES` — **env var global** (`queue/tasks/inference.py:46`) |
| **Threshold de confiança** | ✅ por operação (`operations.config`) e por modelo (`trained_models.scenario_config`) | ❌ não chega ao detector | `DETECTION_CONFIDENCE_THRESHOLD` env (`inference/config.py`) |
| **Quality preset** | ✅ `cameras.quality_preset` | ❌ nenhum | — |
| **Classes de violação** | — | — | `VIOLATION_CLASSES` env, hardcoded em `inference_engine.py:38-42` |
| **Tracker** | — | — | `DeepSort(max_age=30, n_init=3)` literal em `inference_engine.py:53` |
| **Janela dia/noite EPI** | — | — | `_DAY_HOUR_START=6` / `_DAY_HOUR_END=18` em `canonical/epi_zone.py:22-23` |
| **Intervalo de poll do edge** | — | — | `_DEFAULT_INTERVAL = 300.0` em `config_poller.py:17` |

> **Um operador pode mudar o FPS na UI hoje, salvar com sucesso, e nada acontece no Edge.** Isso é pior que não
> ter a tela: cria confiança falsa. Fechar esse laço (banco → runtime) é pré-requisito de qualquer promessa de
> "controlável pelo front".

---

## 3. O desenho — 5 planos de controle

A integração não é "uma API". São **cinco canais** com contratos, cadências e modos de falha distintos.

```
                    ┌─────────────────── RECOGNITION (cloud) ───────────────────┐
                    │  Postgres (config canônica)  ·  Redis  ·  API Flask       │
                    └───┬──────────┬───────────┬───────────┬──────────┬─────────┘
                        │          │           │           │          │
              (1) CONFIG│  (2) CMD │  (3) EVT  │ (4) MODEL │ (5) OBS  │
               pull     │   pull   │   push    │   pull    │   push   │
                        ▼          ▼           ▲           ▼          ▲
                    ┌───────────────────── EDGE (Jetson Orin NX) ───────────────┐
                    │  edge-sync-agent  ·  DeepStream  ·  Redis local  ·  buffer│
                    └───────────────────────────────────────────────────────────┘
```

### Plano 1 — CONFIG (cloud → edge, pull) — *o que falta e destrava tudo*

**Rota:** `GET /api/v1/edge/config/poll` · **auth:** device RS256 · **cadência:** 30–60s (hoje 300s hardcoded)

O device pergunta "qual é a minha configuração?" e recebe **o cenário completo do site**: câmeras, modelo por
câmera, módulo ativo, FPS, thresholds, operações (ROI/linhas/zonas), regras, agenda, retenção.

Decisões de contrato:
- **Versionamento obrigatório.** Resposta traz `config_version` (monotônico por site) + `ETag`. Device manda
  `If-None-Match` → **304 quando nada mudou** (o caso comum; sem isso são 28 câmeras × poll × payload grande).
- **Escopo = site**, não câmera. Uma chamada traz tudo do site; o device distribui internamente.
- **Fonte = o composer que já existe.** `scenarios/routes.py` já monta câmera + módulos + classes + operações +
  regras + agenda. **Reusar esse composer**, trocando a auth de user-JWT para device — não escrever um segundo.
- **Aplicação sem restart.** O `config_poller.py` já aplica em memória. Onde exigir reload de pipeline, usar o
  padrão do `model_watcher.py` (pub/sub + reload localizado).
- **Idempotência e rollback.** Device guarda a última config boa; config nova que falhar ao aplicar → mantém a
  anterior e reporta falha no heartbeat. **Config ruim não pode derrubar o site.**

### Plano 2 — COMANDO (cloud → edge, pull) — *existe, está quebrado*

**Rotas:** `POST /commands` (admin) · `GET /commands/pending` (device) · `PATCH /commands/<id>` (device)

Ações pontuais que não são estado: reiniciar pipeline, recarregar modelo, capturar frame de diagnóstico, rodar
teste de câmera, sincronizar relógio, coletar log.

- **Consertar B1/B2 primeiro** — o canal nunca autenticou.
- **Escrever o cliente** (`command_poller.py` está preso num worktree).
- **Ciclo de vida explícito:** `pending → acked → running → done|failed|expired`, com TTL. Comando sem ack em N
  minutos expira sozinho — não fica pendente pra sempre.
- **Idempotência por `command_id`** — o device pode receber o mesmo comando duas vezes num retry.

### Plano 3 — EVENTO / DETECÇÃO (edge → cloud, push) — *existe, está quebrado*

**Rota:** `POST /api/v1/edge/events/ingest` (batch ≤500, `X-Batch-Id`, dedup por `batch_id:sha256(evt)[:16]`)

- Consertar B1. Reconciliar `/edge/detections` (A2): **ou** implementar a rota, **ou** apontar o `uploader.py`
  para `/events/ingest`. Decidir **um** caminho e matar o outro — hoje há dois contratos divergentes.
- Buffer SQLite + backoff já existe no agent. Garantir **entrega ao menos uma vez** com dedup no servidor (já há).

### Plano 4 — MODELO (cloud → edge, pull) — *ausente*

O escopo `models:download` está previsto no ADR-0019 e **nenhum endpoint o implementa**. Sem isso, trocar o
modelo de uma câmera pela UI não faz o modelo chegar no Jetson — alguém copia à mão.

- `GET /api/v1/edge/models/<model_id>/download` com device auth + escopo, URL assinada do R2, checksum.
- Device valida checksum, guarda versão anterior, e faz **rollback automático** se o engine novo falhar ao carregar.

### Plano 5 — OBSERVABILIDADE (edge → cloud, push) — *o mais maduro*

`POST /heartbeat` já funciona e tem testes. `GET /sites/health`, `/heartbeats`, `/heartbeat-summary` já servem o front.

Falta: **telemetria por módulo/câmera** (FPS por stream, drops, latência, profundidade de fila) chegando ao
dashboard integrado (task-112), e o vínculo com as métricas de treino (Training Studio).

---

## 4. Superfície de ADM — o que o front precisa expor

Rotas que **existem mas não têm cliente no frontend** (trabalho de UI, não de API):

| Já existe na API | Falta no front |
|---|---|
| `POST/GET /edge/sites`, `PATCH /edge/sites/<id>` | CRUD de site |
| `POST /edge/sites/<id>/enrollment-tokens`, `GET`, `POST /revoke` | Fluxo de enrollment (gerar token, mostrar 1x, revogar) |
| `POST /edge/devices/<pk>/revoke` | Revogar device |
| `GET/PUT /site-gateways/<site_id>` | Config de gateway (MikroTik/WireGuard, lan_subnet) |
| `POST/GET /edge/commands` | Console de comandos + histórico |

E o que **não existe em lugar nenhum** e o produto precisa:

- **Editor de operation-types** — hoje adicionar tipo novo é classe Python + deploy (`canonical/__init__.py`).
  Enquanto o registry for estático, "sem tocar no código" é falso para essa dimensão. **Decisão necessária:**
  registry estático (aceitar deploy) vs tipos declarativos em banco (config_schema JSONB).
- **Painel de config efetiva** — mostrar ao operador **o que o Edge realmente está rodando** (config_version
  aplicada, drift entre banco e device). Sem isso ninguém confia no sistema.
- **Duplo enrollment** — `devices/` (claim code, JWT HS256) e `edge/enroll` (token opaco, SHA-256) são
  **incompatíveis**. Escolher um, aposentar o outro.

---

## 5. Fases (ordem por dependência, não por preferência)

| Fase | Entrega | Por que nesta ordem |
|---|---|---|
| **F0 — Fundação** | Corrigir B1/B2 (device auth em commands+events); corrigir B3 (doc mente); testes nos dois blueprints | Sem auth funcionando, nada acima disso é testável |
| **F1 — A ponte** | `GET /edge/config/poll` reusando o composer do `scenarios/`; versionamento + ETag/304; agent aplicando sem restart | É o gap central. Destrava todo o resto |
| **F2 — Fechar o laço decorativo** | `fps_target`, `quality_preset`, `confidence_threshold` passam a ser **lidos do config** pelo runtime; aposentar as env vars globais | Faz a UI existente virar verdade. Alto valor, baixo custo |
| **F3 — Comandos ponta a ponta** | Cliente `command_poller` no main tree; ciclo de vida + TTL + idempotência; console no front | Operação remota real (restart, reload, diagnóstico) |
| **F4 — Modelo pro device** | `/edge/models/<id>/download` + escopo + checksum + rollback | Fecha o ciclo "troquei o modelo na UI → chegou no Jetson" |
| **F5 — Operation-types faltantes** | `attention_points`, `stage_timer` (+ `crowd_zone`, `dwell_zone`); decidir registry estático vs declarativo | **Bloqueia RVB (ADR-0053)** |
| **F6 — Motor de operações em produção** | Loop que avalia operações contra o stream de detecções e popula `operation_results` | Hoje operações só rodam em `/test` |
| **F7 — DeepStream configurado pelo banco** | Definir o contrato: gerador de config a partir do cenário, ou pipeline que lê config em runtime | `deepstream/` está vazio — decisão em aberto, não retrabalho |
| **F8 — ADM + observabilidade no front** | Telas de site/enrollment/gateway/comandos; painel de config efetiva e drift | Superfície de controle visível |

**Regra de ouro entre fases:** cada fase entrega uma frase verdadeira do tipo *"o operador muda X na UI e o Edge
obedece"*. Fase que não consegue enunciar isso não terminou.

---

## 6. Riscos e decisões em aberto (precisam do Vitor)

1. **Registry de operation-types: estático ou declarativo?** Estático = simples, mas todo tipo novo é deploy.
   Declarativo = "sem tocar no código" de verdade, mas exige schema-driven UI e validação em banco. **Impacta a
   promessa central do produto.**
2. **`deepstream/` vazio: gerar config do banco, ou pipeline lê config em runtime?** A primeira é mais simples
   e reinicia o pipeline; a segunda é mais elegante e permite hot-reload. Decidir **antes** de escrever a F7.
3. **Dois enrollments incompatíveis** (`devices/` vs `edge/enroll`) — qual sobrevive?
4. **`/edge/detections` vs `/events/ingest`** — qual é o contrato canônico? O outro morre.
5. **Cadência de poll** — 300s hoje. Config precisa ser mais rápida (30–60s) sem virar DDoS em frota grande.
   Sugerido: poll de config rápido com 304, telemetria no heartbeat.

---

## 7. Pendências herdadas (não são deste plano, mas bloqueiam go-live)

- 🔴 Senha `admin@rvb.com.br` commitada no git — rotacionar pela aplicação.
- ⚠️ Fan `quiet→cool` antes da carga 24/7 (sudo, task-097).
- Promoção `develop→staging` (108 commits) — evento próprio, com janela e rollback.
- Trilha de segurança: escopos de device nunca aplicados, `serve_hls` sem checagem de tenant,
  `toggle_module_class` cross-tenant. Ver `PLANO_SEGURANCA_EDGE_2026-07-18.md`.
