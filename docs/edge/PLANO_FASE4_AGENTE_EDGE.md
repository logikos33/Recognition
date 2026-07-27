# Plano de execução — Fase 4: agente edge de produção

> Execução do **ADR-0056**. Objetivo: transformar os componentes já testados de `services/edge-sync-agent/`
> num **daemon supervisionado único** com identidade de device persistida. **DEV primeiro; validar no pandora
> real antes do aceite.** Não promover para staging/main sem gate humano.

## Terreno (auditado 2026-07-27, C-04)

| Componente | Estado | Reuso na Fase 4 |
|---|---|---|
| `app/main.py` (evidence+discovery, bind-host guard) | ✅ testado | padrão de bootstrap/single-process |
| `config_poller.ConfigPoller.run(stop_event)` | ✅ testado, não iniciado | subir como thread |
| `command_poller.CommandPoller.run(stop_event)` | ✅ testado, não iniciado | subir como thread |
| `uploader.Uploader.run(stop_event)` + `sqlite_buffer.SQLiteBuffer` | ✅ testados, não iniciados | subir como thread |
| `telemetry.build_heartbeat_payload` / `HeartbeatSink` / parser tegrastats | ✅ testado (processo à parte) | corpo do heartbeat |
| `evidence_auth.TrustAnchor` (RS256 inbound) | ✅ testado | inalterado |
| **enrollment de produção** | ❌ só o probe DEV | **novo** |
| **persistência/rotação de chave+token RS256** | ❌ ausente | **novo (`app/auth/`)** |
| **orquestrador único (inicia os loops)** | ❌ `main.py` não sobe loops | **novo (entrypoint daemon)** |
| **wiring env→loop** (`build_*_from_env` p/ pollers) | ❌ ausente | **novo** |
| systemd unit p/ o daemon | ❌ só existe p/ telemetria | **novo** |

Contrato de referência já provado: `scripts/edge_artery_probe.py` (enroll público → device auto-assina RS256,
ADR-0019 S7; escopo `heartbeat:write`; envelope `data`; login cloud é `/api/auth/login`).

## Faseamento em PRs (cada um isolado, testável, DEV)

### PR-A — Identidade do device (`app/auth/`)
- `enrollment.py`: consome token one-time, `POST /edge/enroll`, guarda `{tenant_id, site_id, scopes}` em estado local.
- `token_manager.py`: **gera e persiste** a chave privada RS256 (`DEVICE_KEY_PATH`, `chmod 600`, fora de git);
  re-assina o JWT curto sob demanda (claims `{tenant_id, site_id, device_id, scopes, iat, exp}`).
- Testes espelhando o padrão do pacote (chaves efêmeras em teste; verificação contra `DeviceClaims` real).
- **Reuso, não cópia:** portar a lógica de assinatura do probe, sem o guardrail-anti-prod nem a chave em memória.

### PR-B — Heartbeat integrado
- `heartbeat.py`: loop `run(stop_event)` que monta o corpo com `telemetry.build_heartbeat_payload` e assina via
  `token_manager`. Métricas de pipeline `null` (task-112 depois). Reusa o parser tegrastats já testado.
- Teste: heartbeat assinado aceito pelo verificador; corpo válido no modelo `Heartbeat`.

### PR-C — Orquestrador único (o daemon)
- Entrypoint que sobe em threads, com `stop_event` compartilhado e shutdown gracioso (SIGTERM):
  config-poll + command-poll + uploader + heartbeat. Decidir: estender `app/main.py` ou novo `app/daemon.py`
  (preferência: entrypoint separado do HTTP evidence/discovery, para o daemon não depender de servir porta).
- `build_config_poller_from_env` / `..._command_poller` / `..._uploader` fechando `CLOUD_API_URL`, `DEVICE_ID`,
  `SQLITE_BUFFER_PATH`, `HEARTBEAT_INTERVAL_S`, `UPLOAD_BATCH_SIZE` (hoje documentados sem leitor).
- Teste de integração: daemon sobe, cada loop tick uma vez (http_client mockado), SIGTERM encerra limpo.

### PR-D — Deploy
- systemd unit do daemon (análogo ao `edge-telemetry-collector.service`): `Restart=always`, `EnvironmentFile`,
  usuário sem privilégio, `DEVICE_KEY_PATH` num dir dedicado. `.env.example`. Doc de provisionamento.

### Validação e2e (gate de aceite — no pandora real)
- Rodar o daemon no pandora contra o DEV; confirmar enroll persistido (sobrevive a restart **sem** re-enrolar —
  reusa a chave), heartbeat contínuo, config-poll recebendo config das câmeras, uploader ocioso (sem ingestão
  ainda — esperado). Só então marcar o site como `active`.

## Fora desta fase (sub-blocos próprios)
- **Ingestão de detecções** (`mqtt_consumer`/ponte pipeline→buffer) — depende do DeepStream ligado.
- **task-112** — telemetria por câmera (FPS/drops/latência por stream).
- **`model_manager`** — download/validação SHA256/swap de modelo.
- **`mirror_api`/`stream_reporter`** — fallback LAN (ADR-0006).

## Ordem sugerida
PR-A → PR-B → PR-C → PR-D, cada um com teste verde, depois a validação no pandora. O probe continua disponível
como ferramenta de diagnóstico e como referência de contrato durante toda a fase.
