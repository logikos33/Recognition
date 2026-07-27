# ADR-0056 — Agente edge de produção: daemon supervisionado único (Fase 4)

**Status:** Proposta · **Data:** 2026-07-27 · **Autores:** Vitor Emanuel (Logikos)
**Relaciona:** ADR-0019 (device tokens RS256, auto-assinatura S7), ADR-0020 (WireGuard outbound),
ADR-0002 (Redis pub/sub detecções), ADR-0055 (plano de controle edge — 5 canais), ADR-0045 (evidence recorder-first)
**Detalhamento/execução:** `docs/edge/PLANO_FASE4_AGENTE_EDGE.md`

## Contexto (validado no código, C-04 — 2026-07-27)

A **artéria edge→cloud foi provada** no DEV (2026-07-26): do pandora real, `/edge/enroll` → 201 e
`/edge/heartbeat` → 201 com telemetria real. **Mas** o que provou foi `scripts/edge_artery_probe.py`,
um **utilitário de diagnóstico** (chave privada em memória, guardrail anti-produção, um único loop). **Não é
o agente de produção.**

O pacote `services/edge-sync-agent/` **não é um placeholder vazio** — a auditoria mostrou o contrário:

**Já pronto e testado** (tasks 090/091/096/100):
- `app/main.py` — sobe evidence-API + discovery-API num único processo Flask/porta (bind-host guard, ADR-0020).
- Auth RS256 **inbound**: `evidence_auth.TrustAnchor` (verifica, nunca assina).
- Família RecorderClient (ONVIF Profile G + RTSP-timestamp), `rtsp_validator`, `rtsp_clip_stream`.
- **Os quatro loops de sync existem e têm teste**, cada um com assinatura `run(stop_event: threading.Event)`:
  `config_poller.ConfigPoller` (poll `/edge/config/poll`, ETag/304), `command_poller.CommandPoller`
  (`/edge/commands/pending` + ack), `uploader.Uploader` (drena buffer → `/edge/detections`, backoff),
  `sqlite_buffer.SQLiteBuffer` (fila WAL idempotente).
- Coletor de telemetria: `app/telemetry/` (`build_heartbeat_payload`, `HeartbeatSink`, parser tegrastats) +
  systemd unit `deploy/edge-telemetry-collector.service`.

**O gap NÃO é lógica de base — é integração/wiring + o pedaço de identidade do device:**
1. `main.py:16-18` **declara explicitamente** que NÃO inicia os loops de heartbeat/config-poll/uploader — não há
   orquestrador único. Os loops só rodam em teste.
2. Não existe módulo de **enrollment** de produção (só o probe DEV, com guardrail anti-produção).
3. Não existe **persistência/rotação de credencial** (`app/auth/token_manager.py` ausente): a chave privada RS256
   vive só em memória no probe; os loops recebem `token` por parâmetro, ninguém o obtém/persiste/re-assina.
4. O heartbeat de produção só existe como **processo separado** (`app/telemetry`) que exige um `EDGE_DEVICE_BEARER`
   provisionado à mão e **não faz enroll**.
5. Sem **wiring env→loop** (não há `build_*_from_env` para os pollers, como há para o recorder).
6. Ninguém **alimenta o SQLiteBuffer** em produção (`mqtt_consumer.py` ausente) → uploader com fila vazia.
7. Sem `model_manager.py`, `mirror_api.py`, `stream_reporter.py` (citados no AGENT.md, não existem).
8. Deploy: só há systemd unit para o **coletor de telemetria**, não para o daemon `app.main`/loops.

## Decisão

Construir a **Fase 4** como um **único daemon supervisionado** que **costura os componentes já existentes e
testados** — não reescrever base — adicionando apenas o que falta de **identidade do device** e **orquestração**:

1. **Identidade do device (novo, `app/auth/`):** módulo de enrollment de produção + `token_manager` que
   **gera/persiste a chave privada RS256 em disco** (`chmod 600`, `DEVICE_KEY_PATH`), guarda o resultado do enroll
   (tenant/site/scopes) e **re-assina** o JWT de curta duração sob demanda. Contrato de referência: o probe
   (`/edge/enroll` público → device auto-assina, ADR-0019 S7). **O probe segue como utilitário de diagnóstico,
   não é promovido a produção** (chave efêmera + guardrail anti-produção são inadequados a um daemon).
2. **Heartbeat integrado:** um loop de heartbeat que **reutiliza** `telemetry.build_heartbeat_payload` para o corpo
   e o `token_manager` para a assinatura — assim o heartbeat passa a incluir enroll+chave persistida, sem exigir
   bearer manual. Métricas de pipeline (inference_fps/câmeras) seguem `null` até a task-112.
3. **Orquestrador único:** um entrypoint de daemon que sobe, em threads com `stop_event` e shutdown gracioso
   (SIGTERM), os loops **que já existem**: config-poll + command-poll + uploader + heartbeat. Reaproveita o padrão
   de bind-host/único-processo do `main.py` atual. Inclui `build_*_from_env` para fechar o wiring env→loop.
4. **Deploy:** systemd unit para o daemon (análogo ao do coletor), com `Restart=always` e `EnvironmentFile`.

**Fora da Fase 4 (sub-blocos posteriores, para não inchar o escopo):**
- **Ingestão de detecções** (`mqtt_consumer`/ponte pipeline→`SQLiteBuffer`): depende do DeepStream ligado (Fase 4
  de inferência, não deste agente). Sem ela o uploader fica ocioso — aceitável nesta fase.
- **Telemetria por câmera** (FPS/drops por stream) — **task-112**.
- **`model_manager`** (download/validação SHA256/swap de modelo) — sub-bloco próprio.
- **`mirror_api`/`stream_reporter`** (fallback LAN, ADR-0006) — sub-bloco próprio.

## Alternativas consideradas

- **Promover a sonda a agente.** Rejeitada: chave efêmera em memória, um só loop, guardrail que recusa produção —
  é diagnóstico por design. Serve como **referência de contrato**, não como base do daemon.
- **Manter o coletor de telemetria separado como "o heartbeat".** Rejeitada: exige `EDGE_DEVICE_BEARER`
  provisionado à mão e não faz enroll — não fecha a identidade do device de forma supervisionada.
- **Um processo por loop (N systemd units).** Rejeitada: os loops compartilham a mesma credencial/estado de config;
  um processo único com threads (o que as assinaturas `run(stop_event)` já sugerem) é mais simples e coeso.

## Consequências

- **Positivas:** reaproveita ~100% da lógica testada; o gap vira wiring + identidade, reduzindo risco e superfície.
  Fecha o caminho crítico do go-live RVB (device supervisionado que sobrevive a reboot).
- **Custos/riscos:** nada foi validado em hardware real (mocks); a validação no pandora é obrigatória antes de
  declarar pronto. Persistência de chave privada em disco no device é superfície de segurança nova (mitigar:
  `chmod 600`, fora de git, `/run` ou dir dedicado). Pré-requisitos de cloud (migrations 042/043/044, blueprint
  `/api/v1/edge/*`) já existem — enroll/heartbeat foram exercitados na prova da artéria.

## Classificação

**P0-CRÍTICO** (multi-arquivo, caminho de go-live). Verificação: testes por módulo (já é o padrão do pacote) +
validação e2e no pandora real antes do aceite. Execução faseada em PRs — ver o plano.
