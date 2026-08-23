# Contrato SocketIO + ambiente transversal

> Fonte: código real em `origin/develop @ 98bff30e` (worktree `wt-mapa-front`). Todas as referências são `arquivo:linha` desse commit. Onde o código não permite afirmar, está escrito `indeterminado`.

## Contrato tempo real (SocketIO)

### Topologia real

```
publicador → Redis PUBLISH canal → socket_bridge (thread na API) → socketio.emit(evento, namespace) → broadcast GLOBAL → browser
```

- **Servidor:** `SocketIO()` em `services/api/app/extensions.py:14`, inicializado em `services/api/app/__init__.py:133-140` com `cors_allowed_origins=config.CORS_ORIGINS`, `async_mode="gevent"` (threading só em TESTING), `message_queue=REDIS_URL` (fora de TESTING), `logger=False`. Path default `/socket.io`. Gunicorn 1 worker `GeventWebSocketWorker` (`railway_start.py:183-189`); `--max-requests 100000` (`railway_start.py:195`) — reciclagem derruba todas as conexões WS.
- **Bridge:** `services/api/app/core/socket_bridge.py:144-254`. Thread daemon iniciada em `__init__.py:199-203` só quando `REDIS_URL` setada e não-TESTING. `psubscribe("det:*","training:*","quality:*","operations:*","edge_telemetry:*")` (`socket_bridge.py:138-140`). Reconexão com backoff 2s→60s (`socket_bridge.py:241-244`). Conexão Redis dedicada `socket_timeout=None`, `health_check_interval=25` (`socket_bridge.py:129-134`).
- **Handlers de evento no servidor:** **NENHUM**. `grep` por `@socketio.on`, `socketio.on_event`, `on_namespace`, `join_room`, `leave_room`, `ConnectionRefusedError` em `services/api/app` (fora de testes) → zero ocorrências. Não há handler de `connect`, não há validação de token, não há rooms.
- **Versões pinadas:** `flask-socketio==5.6.1`, `python-socketio==5.16.3`, `python-engineio==4.13.3` (`requirements/api.txt:464,1213,1219`); front `socket.io-client ^4.8.3` (`apps/frontend/package.json:35`).

### Como o front conecta

| Hook | URL base | Namespace | Auth enviada | Transports | Reconexão |
|---|---|---|---|---|---|
| `useMonitoringSocket` (`apps/frontend/src/hooks/useMonitoringSocket.ts:51-58`) | `wsUrl` prop = `VITE_WS_URL \|\| VITE_API_URL \|\| ''` (`pages/MonitoringPage.tsx:84`, `components/camera-grid/CameraGrid.tsx:29`) ou `VITE_API_URL ?? ''` (`components/training/TrainingModeLayout.tsx:31`) | `/monitor` | `query: {token}` (JWT do localStorage) | `['websocket']` | infinita, 1s→10s |
| `useEdgeTelemetrySocket` (`hooks/useEdgeTelemetrySocket.ts:44-51`) | idem (`pages/DashboardIntegradoPage.tsx:44`) | `/monitor` | `query: {token}` | `['websocket']` | infinita, 1s→10s |
| `useOperationLiveStatus` (`hooks/useOperationLiveStatus.ts:37-44`) | `VITE_API_URL ?? ''` (`TrainingModeLayout.tsx:31`) | `/monitor` | `query: {token}` | `['websocket']` | infinita, 1s→10s |
| `useTrainingSocket` (`hooks/useTrainingSocket.ts:73-80`) | `VITE_API_URL \|\| ''` (`pages/TrainingPage.tsx:259,329`) | `/training` | `query: {token}` | `['websocket']` | infinita, 1s→10s |
| `useQualityWebSocket` (`modules/quality/hooks/useQualityWebSocket.ts:32-42`) | `VITE_WS_URL \|\| VITE_API_URL \|\| window.location.origin` | `/quality` | **nenhuma** | `['websocket','polling']` | 10 tentativas, 2s |
| `useTabletWebSocket` (`modules/quality/tablet/useTabletWebSocket.ts:41-52`) | idem | `/quality` | **nenhuma** | `['websocket','polling']` | infinita, 1s |
| `useAdminWebSocket` (`modules/admin/hooks/useAdminWebSocket.ts:23-28`) | **relativa** `io('/admin')` (mesma origem do front) | `/admin` | `auth: {token}` | `['websocket']` | 5 tentativas, 2s |

- Guarda de conexão: os 4 hooks de `/monitor`/`/training` retornam sem conectar se `!wsUrl || !token` (ex.: `useMonitoringSocket.ts:49`). Com `VITE_API_URL`/`VITE_WS_URL` vazios (modo dev via proxy Vite) **o socket nunca abre**, apesar de o proxy `/socket.io` (ws:true) existir em `apps/frontend/vite.config.ts:18`.
- `useQualityWebSocket` e `useAdminWebSocket` **não têm call site** fora de testes (grep em `apps/frontend/src`). `useTabletWebSocket` é usado em `modules/quality/tablet/TabletKiosk.tsx:45` (rota `/tablet/:station`, `AppRoutes.tsx:166-169`).
- Token: viaja em `query` (ou `auth`) mas **nenhum handler o lê** — conexão é anônima na prática. CORS do handshake = `config.CORS_ORIGINS` (`__init__.py:135`).

### Tabela de eventos

Direção: S→C = servidor emite; C→S = front emite. "Assinante no front" = `socket.on(...)`.

| Namespace | Evento | Direção | Publicador (Redis canal → bridge) | Assinante no front | Chaves do payload (shape real do publicador) | Status |
|---|---|---|---|---|---|---|
| `/monitor` | `detection` | S→C | canal `det:{camera_id}` ← `services/api/app/infrastructure/queue/tasks/inference.py:691-697` (Celery cloud) e `services/inference/inference/inference_engine.py:178-186`; bridge `socket_bridge.py:176-182` | `hooks/useMonitoringSocket.ts:72` | `{camera_id, timestamp, detections:[{class, confidence, bbox:[x,y,w,h], track_id}], has_violation}` (bridge prefixa `camera_id` do canal). Front espera `is_violation?` por detecção — nunca enviado | ok (shape compatível); ver achado A1 (conexão recusada) e A4 (edge não alimenta `det:*`) |
| `/monitor` | `alert` | S→C | **ninguém emite** (único emissor é o bridge; não há branch `alert`) | `hooks/useMonitoringSocket.ts:79` | — | **assinatura-morta** |
| `/monitor` | `subscribe_camera` / `unsubscribe_camera` | C→S | — | emitido em `useMonitoringSocket.ts:64,94,99` `{camera_id}` | — | **emit-sem-handler** (servidor não escuta; broadcast é global, "subscribe" não filtra nada) |
| `/monitor` | `operation:status_changed` | S→C | canal `operations:status:{op_id}` ← `services/api/app/domain/services/operations/engine.py:220-223` (normal) e `:232-235` (erro), via `core/operations_worker.py:47-48`; bridge `socket_bridge.py:229-231` | `hooks/useOperationLiveStatus.ts:49` | normal: `{operation_id, camera_id, result, metric_value, condition_satisfied}`; erro: `{operation_id, camera_id, status:"error"}`. Front espera `{operation_id, status, last_value?, timestamp}` (`types/operations.ts:50-55`) → `status` undefined no caminho normal | **ok com shape incompatível** (achado A5) |
| `/monitor` | `operation:reloaded` | S→C | canal `operations:reload:{op_id}` ← `api/v1/operations/routes.py:30-55` (callers `:121,159,191`); bridge `socket_bridge.py:221-228` | `hooks/useOperationLiveStatus.ts:60` | `{operation_id:int, version}` ou `{operation_id, removed:true}` | ok (shape compatível com `OperationReloadedEvent`) |
| `/monitor` | `edge_telemetry` | S→C | canal `edge_telemetry:{tenant_id}` ← `domain/services/dashboard_edge_service.py:89-120` (ingest `POST /api/v1/dashboard/edge-telemetry`); bridge `socket_bridge.py:232-237` | `hooks/useEdgeTelemetrySocket.ts:56` | `{tenant_id, site_id, label, sampled_at, payload}` | ok (shape compatível); broadcast global sem filtro de tenant (achado A2) |
| `/training` | `training_progress` | S→C | bridge `socket_bridge.py:183-196` assina `training:*`, mas **nenhum publicador usa `training:`**: Celery e progress-callback publicam em `training_progress:{job_id}` de propósito (`infrastructure/queue/tasks/training.py:138-143`, `api/v1/training/job_handlers.py:444-460` "Ajuste vinculante #2: NÃO usar training:{job_id}"); `constants.py:340 RedisChannel.TRAINING_PROGRESS="training:{job_id}"` não é usado | `hooks/useTrainingSocket.ts:85` | (se existisse) `{job_id, status, progress, epoch?, total_epochs?, loss?, metrics?, eta_seconds?, model_key?}` | **assinatura-morta** (front depende do polling 3s `GET /api/training/jobs/current/status`, `pages/TrainingPage.tsx:332-374`) |
| `/training` | `quality_training` | S→C | canal `quality:training_progress:{job_id}` ← `infrastructure/queue/tasks/quality_training.py:58-66`; bridge `socket_bridge.py:200-202` | nenhum | `{job_id, step, progress, message, timestamp}` | **sem-assinante** |
| `/quality` | `quality_inspection` | S→C | canal `quality:inspection:{schema}:{camera_id}` ← `infrastructure/queue/tasks/quality_inference.py:431-442`; bridge `socket_bridge.py:197-199` | `modules/quality/hooks/useQualityWebSocket.ts:54` (hook sem call site) | `{inspection_id, camera_id, result, defect_class:str, confidence, nok_rate_1h, timestamp}`; front tipa `defect_class:number` (`types/quality.ts:194`) | sem-assinante efetivo (hook não montado) |
| `/quality` | `quality_cep_alert` | S→C | canal `quality:cep_alert:{schema}:{camera_id}` ← `quality_inference.py:170-174`; bridge `socket_bridge.py:203-205` | `useQualityWebSocket.ts:60` (hook sem call site) | `{camera_id, nok_rate_1h, limit}` | sem-assinante efetivo |
| `/quality` | `quality_andon` | S→C | canal `quality:andon_live:{camera_id}` ← `quality_inference.py:471-477`; bridge `:206-208` | nenhum | `{camera_id, recent_inspections:[...], nok_rate_1h}` | **sem-assinante** |
| `/quality` | `quality_piece_identified` | S→C | canal `quality:piece_identified:{schema}` ← `api/v1/quality/gate_service.py:167-170`; bridge `:209-211` | `modules/quality/tablet/useTabletWebSocket.ts:84` filtra `data.station_code === stationCode` | `{event:"piece_identified", piece:{...}}` — **sem `station_code` no topo** → filtro nunca casa (front espera `PieceIdentifiedEvent` `types/gate.ts:123-130`) | **ok com shape incompatível** |
| `/quality` | `quality_inspection_started` | S→C | canal `quality:inspection_started:{schema}` ← `gate_service.py:218-221`; bridge `:212-214` | nenhum | `{event:"inspection_started", piece, validation_type}` | **sem-assinante** |
| `/quality` | `quality_inspection_result` | S→C | canal `quality:inspection_result:{schema}` ← `gate_service.py:353-362` (`{event, piece_id, result, confidence, new_status, validation_type}`), `:422-425` (`{event:"false_positive", piece_id, new_status}`) e `quality_inference.py:666-669` (`{piece_id, validation_type, camera_id, result, confidence, ok_ratio, ok_count, total_frames, detections, photo_path, photo_r2_key, timestamp}`); bridge `:215-217` | nenhum (front escuta `quality_gate_result`, nome diferente) | dois shapes distintos no mesmo evento | **sem-assinante** |
| `/quality` | `quality_gate_result` | S→C | canal `quality:gate_result:{schema}:{piece_id}` ← `quality_inference.py:661-664` **é publicado, mas o bridge não tem branch** para `quality:gate_result:` → descartado | `useTabletWebSocket.ts:70` | (no Redis) shape de `InspectionResultEvent` | **assinatura-morta** (bridge descarta) |
| `/quality` | `quality_station_state` | S→C | canal `quality:station_state:{schema}` ← `gate_service.py:126-129,462-465,502-505,573-576`; bridge `:218-220` | `useTabletWebSocket.ts:77` filtra `data.station_code === stationCode` | `{event:"piece_created"\|"released_to_bench_b"\|"rework_started"\|"rework_completed", piece?\|rework?, piece_id?}` — sem `station_code`/`current_piece`/`tower_state` (front espera `StationStateEvent` `types/gate.ts:115-120`) | **ok com shape incompatível** |
| `/admin` | `worker_status`, `training_approval`, `ticket_created`, `announcement` | S→C | ninguém emite em `/admin` (bridge não usa esse namespace; `admin/routes.py:1374,1427,2385` publicam `notification:*`/`announcement:*` no Redis, que o bridge **não assina**) | `modules/admin/hooks/useAdminWebSocket.ts:34-44` (hook sem call site) | — | **assinatura-morta** |
| (Redis, sem SocketIO) | — | — | canais `quality:{annotation_ready,clip_ready,retrain_threshold,setup_mode,model_changed}:*` (`tasks/quality_annotation.py:209`, `tasks/quality_clips.py:305`, `api/v1/quality/routes.py:100,337,1220`) caem no `psubscribe("quality:*")` mas sem branch → descartados (`socket_bridge.py:197-220`) | — | — | ruído para o bridge; não é contrato de front |

### Rooms / tenant / auth (resumo)

- **Sem `join_room`, sem rooms, sem filtro por tenant.** Todo `socketio.emit(..., namespace=...)` no bridge é broadcast para **todos os clientes do namespace**, de **qualquer tenant** (`socket_bridge.py:178-237`). Os canais carregam `tenant_schema`/`tenant_id` (`quality:*:{schema}`, `edge_telemetry:{tenant_id}`) mas o bridge **não usa** essa parte do nome para rotear.
- **Sem validação do JWT na conexão** (nenhum handler `connect`). O `query.token` do front é ignorado.
- **message_queue Redis:** ativo fora de TESTING (`__init__.py:137`) — prepara multi-worker, mas o serviço roda com `-w 1`.

### Achados

- **A1 — Conexões aos namespaces são RECUSADAS pelo servidor (comprovado).** `python-socketio 5.16.3` só aceita namespace que tenha handler registrado ou esteja em `namespaces=` (`socketio/server.py:_handle_connect` 518-529; default `namespaces=['/']` em `base_server.py:65`). `create_app` não registra handler nenhum nem passa `namespaces=` (`__init__.py:133-140`). Probe com as versões pinadas (flask-socketio 5.6.1 / python-socketio 5.16.3, app sem handlers): `/` conecta; `/monitor`, `/training`, `/quality`, `/admin` → `connected=False` ("Unable to connect"). Consequência: **todo o tempo real do front atual é inoperante**; as telas funcionam por polling (ex.: `TrainingPage.tsx:372` 3s; `CameraGrid.tsx:65` `usePolling(fetchCameras, 60000)`). Corrigir no servidor = registrar handler `connect` por namespace (que é também o lugar de validar JWT e fazer `join_room(tenant)`) ou `namespaces=[...]`.
- **A2 — Broadcast global sem filtro de tenant (C-01).** Mesmo após A1, `detection`, `edge_telemetry`, `operation:*`, `quality_*` vazariam entre tenants. Novo servidor precisa `join_room(tenant_schema)` no `connect` + `emit(..., to=room)` usando o tenant que já vem no nome do canal.
- **A3 — `training_progress` nunca emite:** canal `training:*` não tem publicador; decisão explícita em `job_handlers.py:447` para evitar dupla criação de `trained_models` (o bridge registra modelo em `status=="completed"`, `socket_bridge.py:190-196`). Ou remove-se o side effect do bridge e publica-se em `training:`, ou o bridge passa a assinar `training_progress:*` sem o side effect.
- **A4 — Edge não alimenta `det:*` na cloud.** Únicos publicadores de `det:{camera_id}` são a inferência Celery cloud (`tasks/inference.py:697`) e `services/inference` (`inference_engine.py:186`). O `edge-sync-agent` tem `Uploader` apontando para `POST /api/v1/edge/detections` (`services/edge-sync-agent/app/uploader.py:45`) — **rota inexistente** no `url_map` (`docs/migration/inventory/endpoints.json` não a lista; POST em rota desconhecida cai no catch-all GET-only → 405) — e nada no agent chama `SQLiteBuffer.enqueue` (`sqlite_buffer.py:50`) fora de testes. Em `DEPLOYMENT_MODE=edge`, `detection` via WS não tem fonte. Indeterminado: se `services/inference` roda contra o Redis da cloud em algum deploy.
- **A5 — Shapes divergentes:** `operation:status_changed` (sem `status`/`last_value`/`timestamp`), `quality_station_state` e `quality_piece_identified` (sem `station_code` no topo), `quality_inspection.defect_class` (str vs number), `quality_inspection_result` com 2 shapes no mesmo evento.
- **A6 — Eventos mortos no front:** `alert`, `quality_gate_result` (bridge descarta `quality:gate_result:`), todo `/admin`, e `subscribe_camera`/`unsubscribe_camera` (emit sem handler).
- **A7 — Hooks sem montagem:** `useQualityWebSocket`, `useAdminWebSocket` (este com URL relativa `io('/admin')` — em prod apontaria para o host do front, `serve.py`, que não fala SocketIO).
- **A8 — Dev via proxy:** `wsUrl=''` desliga os hooks (`useMonitoringSocket.ts:49`), embora o proxy `/socket.io` exista (`vite.config.ts:18`). `useQualityWebSocket`/`useTabletWebSocket` caem em `window.location.origin` (funciona no proxy).
- **A9 — Reciclagem do worker:** `--max-requests 100000` (`railway_start.py:195`) derruba todas as conexões WS periodicamente; a reconexão do cliente é o que sustenta.

### O que o novo front precisa implementar (tempo real)

1. Um cliente SocketIO único (`socket.io-client`), base = `VITE_WS_URL || VITE_API_URL`, path default `/socket.io`, `transports: ['websocket']` (polling só se o servidor passar a exigir), token no `auth` (contrato a fechar com o servidor — hoje nada é lido).
2. Namespaces: `/monitor` (`detection`, `operation:status_changed`, `operation:reloaded`, `edge_telemetry`), `/training` (`training_progress`, `quality_training`), `/quality` (`quality_inspection`, `quality_cep_alert`, `quality_andon`, `quality_piece_identified`, `quality_inspection_started`, `quality_inspection_result`, `quality_station_state`). **Não** implementar `alert`, `quality_gate_result`, `/admin`, `subscribe_camera` até existir emissor/handler.
3. Tratar payloads pelos shapes do publicador (tabela acima), não pelos tipos TS atuais.
4. Manter polling como caminho principal (treino 3s, câmeras 60s) enquanto A1 não for resolvido no servidor; WS é incremento.
5. Reconexão infinita com backoff (1s→10s) e re-render tolerante a `disconnect` (A9).
6. Filtrar por tenant no cliente **não basta** (A2) — exigir do servidor rooms por tenant antes de expor dados multi-tenant em tempo real.

## Dependências de ambiente e contrato transversal

### URLs e derivação

- `API_BASE = VITE_API_URL ? \`${VITE_API_URL}/api\` : '/api'` (`apps/frontend/src/services/api.ts:105-107`). Callers passam `/v1/...` (→ `/api/v1/...`, 182 chamadas) ou caminho legado `/training|/cameras|/alerts|/auth|...` (→ `/api/...`, 127 chamadas) — contagem de `docs/migration/inventory/consumers.json` (`frontend_calls`). Backend: 286 rotas `/api/v1/*`, 129 `/api/*` sem v1, 6 na raiz (`/`, `/<path>`, `/health`, `/livez`, `/readyz`, `/status`) — `endpoints.json`.
- Bypass do `api.ts` com `VITE_API_URL` direto + `fetch`/`<img src>`: `components/annotation/AnnotationStudio.tsx:191,348,936`, `CropClassifier.tsx:217`, `SearchFindingsPanel.tsx:58`, `components/training/TrainingGallery.tsx:165`, `pages/CamerasPage.tsx:210`, `pages/TrainingPage.tsx:259`, `hooks/useLiveView.ts:33`, `theme/ThemeProvider.tsx:16-17`, `modules/quality/pages/{QualityPiecesPage.tsx:12,QualityReportsPage.tsx:146,QualityReworkPage.tsx:13}` (default `'http://localhost:5001'`), `modules/quality/services/qualityService.ts:183-184`. `<img src>` para `GET /api/training/frames/<id>/image` (`AnnotationStudio.tsx:936`) bate em rota `@jwt_required` (`api/v1/training/routes.py:125-126`) sem header → 401; `/api/v1/quality/gate/photos/<path>` (`QualityPiecesPage.tsx:378` etc.) **não existe** no backend (`consumers.json.frontend_unmatched`).
- `VITE_WS_URL`: usado só em `MonitoringPage.tsx:84`, `CameraGrid.tsx:29`, `DashboardIntegradoPage.tsx:44`, `useQualityWebSocket.ts:32`, `useTabletWebSocket.ts:42`; fallback sempre `VITE_API_URL`. Ambas são `ARG` de build do Docker do front (`apps/frontend/Dockerfile:18-21`) — **baked no bundle**.
- Dev: proxy Vite `/api`, `/health`, `/socket.io`(ws) → `http://localhost:5001` (`apps/frontend/vite.config.ts:16-19`), porta 3000.

### Headers

- Request: `Authorization: Bearer <token>` (`api.ts:133`); `Content-Type: application/json` exceto `FormData` (omitido → browser define multipart boundary, `api.ts:130-132`). Nenhum header de tenant/impersonation é enviado: contexto assumido e "ver como" viajam **dentro do JWT** (claims `tenant_id`, `tenant_schema`, `role`, `modules`, `impersonated_by`/`tenant_ctx` — `core/auth.py:87-131`, `core/tenant_context.py:73`), trocando o token inteiro no localStorage (`services/tenantContext.ts:85-104`).
- `X-Request-ID`: lido se vier, senão UUID gerado; **sempre devolvido** na resposta (`core/middleware.py:167-177`; 429 também, `:194-203`). Front não envia.
- Outros headers lidos pelo backend, não do front: `X-Callback-Token` (progress-callback), `X-Batch-Id` (`api/v1/edge_events/routes.py:37`), `X-Worker-Secret`, `X-Forwarded-For` (ProxyFix 1 hop, `__init__.py:101`).
- Response: `X-Content-Type-Options`, `X-Frame-Options: SAMEORIGIN`, `X-XSS-Protection`, `Referrer-Policy`; HSTS só com `FLASK_ENV=production` (`middleware.py:114-128`).

### CORS

- `CORS(app, origins=config.CORS_ORIGINS)` (`__init__.py:122`); `CORS_ORIGINS` = env CSV, default `http://localhost:3000,http://localhost:5173,https://frontend-production-bf96.up.railway.app` (`services/api/app/config.py:48-56`). Mesma lista no SocketIO (`__init__.py:135`). Novo front em outro domínio ⇒ **setar `CORS_ORIGINS` no Railway** (api-v3) antes do primeiro deploy.
- Preflight OPTIONS tem bucket próprio de rate limit (2000/min por IP, `core/rate_limiting.py:66`).

### Rate limit

- Buckets gerais em todos os blueprints exceto `health` (`rate_limiting.py:74,180-213`): por usuário (`tenant:<id>:user:<id>`) 300/min default ou plano/override do tenant (`:59,135-162`); piso por IP 900/min (`:62`); OPTIONS 2000/min (`:66`). Rotas com decorator próprio saem dos gerais: login 10/min, register 5/h, etc. (`api/v1/auth/routes.py:48,89,312,344`), HLS 240/min por token de playback + 6000/min por IP (`cameras/stream_handlers.py:376-406`), criação de job de treino 20/dia (`training/routes.py:209`), upload vídeo 10/h (`videos/routes.py:59`), tenant-context 20-30/min, impersonation 10/min.
- **Shape 429:** `{"success": false, "error": "Muitas requisições. Tente novamente mais tarde."}` (`middleware.py:200-202`). **Sem** `Retry-After`/`X-RateLimit-*` (`RATELIMIT_HEADERS_ENABLED` não é setado em `__init__.py:126-129`; flask-limiter 4.1.1 default desligado). Front atual só mostra toast genérico (`errorTranslator.ts` não trata 429).
- Storage: `RATELIMIT_STORAGE_URI = REDIS_URL || memory://`; desligado em TESTING (`__init__.py:127-128`).

### Forma de erros e envelope

- Sucesso: `{"success": true, "message": "OK", "data": {...}}` (`data` omitido se None) — `core/responses.py:23-32`. Erro de rota: `{"success": false, "error": "...", "error_code"?: "..."}` — `responses.py:35-44`; 404/405/500 globais e exceções de domínio idem (`middleware.py:77-111`).
- **Exceções ao envelope (achados):** erros do Flask-JWT-Extended devolvem `{"status":"error","data":{"error": msg}}` — expirado/ausente/revogado → **401**, token inválido → **422** (`__init__.py:551-567`). O `api.ts` lê `data.error || data.msg` (`api.ts:146`) → nesses casos mostra `HTTP 401`/`HTTP 422`; o 422 **não** dispara o fluxo de logout. `/health*` usam `{"status": ..., "checks": ...}` sem `success` (`api/v1/health/routes.py:64-72,107-112,144-165,201-215`). Módulo quality tipa `ApiResponse {status, data}` (`modules/quality/types/quality.ts:208-211`) — divergente do envelope real.
- **Catch-all do SPA:** `GET /<path:path>` registrado na API (`__init__.py:590-600`); como o `dist` do front **nunca existe no container da API** (nixpacks só builda `apps/landing`, `nixpacks.toml:8`; caminhos procurados `__init__.py:573-577`), qualquer **GET em rota inexistente devolve 200 `{"status":"API online","frontend":"separate service"}`** em vez de 404; POST/PUT em rota inexistente → 405. O front é serviço Railway separado (`apps/frontend/railway.toml`, `Dockerfile` → `serve.py` SPA fallback, `frontend-railway.toml` na raiz). Para `api.ts`, `res.ok` é true e `data.success` é undefined.
- 401 no `api.ts` (fora de `/auth/*`): single-flight (`api.ts:120,152-155`) → se há `impersonation_backup` restaura superadmin e vai a `/admin/tenants`; senão se há `tenant_context_backup` idem (guardando meta em sessionStorage); senão `removeToken()` + `window.location.href='/login'` (`api.ts:147-181`). Outros status → `ApiError(msg, status)` + toast via `utils/errorTranslator.ts:45-75` (tradução por status/URL, dedup 3s, regras silenciosas para polling `:28-43`; 403 → "Sem permissao", ≥500 → "Erro interno do servidor").
- Timeouts: `request` 15s (`api.ts:136`), `downloadBlob` 30s (`api.ts:220`), `fetchRaw` sem timeout (`api.ts:235-242`), `ThemeProvider` 5s (`ThemeProvider.tsx:85`). Timeout → toast "Servidor nao respondeu a tempo." + `Error('Timeout na requisicao')` (`api.ts:191-196`).

### localStorage / sessionStorage

| Chave | Onde | Conteúdo |
|---|---|---|
| `token` | `api.ts:8,26-27`; `useAuth.ts:47` | JWT (24h default `config.py:20`/`__init__.py:86`; 30 min para impersonation `impersonation_routes.py:52` e contexto assumido `tenant_context.py:69`) |
| `user` | `useAuth.ts:48,68`, `tenantContext.ts:103,172` | JSON `{id,email,role,modules,permissions,tenant_id,...}` do login (`res.data.user`) |
| `impersonation_backup` / `impersonation` | `api.ts:43-44`, `services/impersonation.ts` | backup `{token,user}` do superadmin + meta |
| `tenant_context_backup` / `tenant_context` | `api.ts:72-73`, `tenantContext.ts:91-101` | idem para contexto assumido (`{tenant_id,tenant_name,tenant_slug,started_at}`) |
| `recognition-app` (migra de `epi-monitor-app`) | `stores/appStore.ts:21-28` | zustand persist (`sidebarOpen`, `selectedModule`) |
| `epi_crop_classifier_session_v1`, `quality_dashboard_mode`, `obs.refreshInterval`, `obs.window` | `CropClassifier.tsx:81`, `QualityDashboard.tsx:8`, `AdminObservabilityPage.tsx:53-54` | preferências locais |
| sessionStorage `impersonation_expired`, `tenant_context_expired`, `tenant_context_expired_meta`, `auto_assume_attempt:tenant-rvb` | `api.ts:45,74,81`; `services/tenantContext.ts` | flags pós-reload |

`removeToken()` limpa `token`, `user`, os 4 de impersonation/contexto (`api.ts:28-38`).

### URLs pré-assinadas R2

- Geração: `infrastructure/storage/r2_storage.py:136-166` — download default `ttl=3600`, upload default `ttl=900`. `configure_cors` (`:85-133`) **nunca é chamado** por default (credencial sem escopo de bucket; opt-in `R2_CONFIGURE_CORS=1`) — CORS do bucket é responsabilidade de infra, fora do código. Browser faz GET/PUT direto no R2 ⇒ origem do novo front precisa estar no CORS do bucket (ação Vitor, dívida já registrada).
- Quem devolve URL assinada ao front: `GET /api/training/videos/<id>/frames` (`training/video_handlers.py:105`, 1h), frames do estúdio (`training/image_handlers.py:322`, 1h), `GET /api/alerts/<id>/snapshot` → `{snapshot_url}` (`alerts/routes.py:161`, 1h), `GET /api/v1/events/*` → `frame_url` (`events/routes.py:94`, 1h), `GET /api/cameras/<id>/snapshot` → `url` (`cameras/snapshot_handlers.py:131`, `_DEFAULT_URL_TTL_S`), `POST /api/v1/videos/upload-url` → `upload_url` PUT (`videos/routes.py:172`, 15 min), `GET /api/v1/videos/<id>/download-url` (`videos/routes.py:406`, 15 min), datasets (`domain/services/dataset_service.py:157`, 1h), busca/propagação (`tasks/search.py:136`, `tasks/propagation.py:178-196`), relatório compliance PDF (`domain/services/compliance_report_service.py:201`), branding logo `POST /api/v1/admin/branding/logo` → `{url,key}` com **ttl=365 dias** (`branding/routes.py:267-269`) e `POST /api/v1/admin/tenants/<id>/branding/logo` **ttl≈10 anos** (`admin/branding_routes.py:192`). Achado a verificar: SigV4/R2 limita URL assinada a 7 dias — URLs de logo persistidas no `branding` podem expirar/ser rejeitadas (indeterminado pelo código; validar em runtime). Fora do R2 (dev) a rota devolve `/local-storage/{key}` (`branding/routes.py:271-273`) — **nenhuma rota serve `/local-storage/`** (cai no catch-all).

### Tokens de playback HLS

- `POST /api/cameras/<id>/stream/start` → `data.hls_url = /api/cameras/<id>/stream/s/<token>/stream.m3u8` (`cameras/stream_handlers.py:285-297`); `GET /api/cameras/<id>/stream/info` → `data.url` idem (`:744-748`). Enforcement **ON por default** (`core/playback_token.py:38-59`; `HLS_REQUIRE_PLAYBACK_TOKEN=0` desliga). TTL `HLS_PLAYBACK_TOKEN_TTL` default 3600 s (`playback_token.py:35`), assinatura HMAC com `JWT_SECRET_KEY` (`:62-76`). Segmentos `.ts` herdam o token pelo path relativo.
- `GET /api/cameras/<id>/stream/s/<token>/<file>` sem JWT (hls.js não manda header): token expirado → **410** `{"success":false,"error":"Token de playback expirado","error_code":"playback_token_expired"}` + `Cache-Control: no-store` (`stream_handlers.py:454-460`); inválido/sem token → 404 (`:461-467`, C-01: igual a stream inexistente). Rate limit 240/min por token, 6000/min por IP (`:376-406`).
- Front: `hooks/useLiveView.ts` cacheia por câmera, lê `exp` do token na URL e renova via novo `/stream/start` antes de vencer (`:60-92,190-261`); `CameraPlayer.tsx:232-240` trata 410 com `refreshLiveViewUrl`. Novo front deve replicar: URL vem **só** do backend, renovação proativa por `exp`, 410 → refresh, 404 → câmera fora do tenant.

### Branding / assets

- `GET /api/v1/tenant/branding` (JWT opcional; sem tenant → default `is_default:true`) → `{"branding": {product_name, logo_url, favicon_url, color_primary, color_secondary, color_bg_*, color_text_*, color_border}, "is_default": bool}` (`api/v1/branding/routes.py:60-113`). Front: `theme/ThemeProvider.tsx:69-100` (manda `?tenant_id=` que o backend ignora; aplica favicon dinamicamente `:43-51`). Upload de logo: ver R2 acima. Fontes: `@fontsource-variable/inter` empacotada (sem CDN).

### Swagger / health

- Swagger só fora de TESTING e se `flasgger` instalado (`flasgger==0.9.7.1`, `requirements/api.txt:430`): UI `/api/v1/docs`, spec `/api/v1/apispec.json`, estáticos `/flasgger_static` (`__init__.py:457-510`). Não aparecem em `endpoints.json` (inventário gerado em TESTING).
- Health sem auth e isentos de rate limit: `GET /health` = `GET /api/v1/health` → `{status: healthy|degraded, checks:{database,redis}}` 200/503 (`health/routes.py:34-72`); `/livez` → `{status:"alive", uptime_seconds, commit, running_jobs}` (`:75-112`); `/readyz` → `{status, ready, stale, age_seconds, invariants, dependencies}` 200/503 (`:115-170`); `/status` → detalhado com latências (`:173-215`). `GET /api/v1/health/metrics` exige JWT (`:293-295`). Front atual não consome nenhum.

### Serviço do front em produção

- API **não** serve o SPA (ver catch-all acima). Front = serviço Railway próprio: build Docker com `ARG VITE_API_URL/VITE_WS_URL` (`apps/frontend/Dockerfile:18-23`), `npm run build` (`tsc && vite build`), servido por `python3 serve.py` (http.server com fallback `index.html`, `serve.py:22-36`); `railway.toml` `rootDirectory=apps/frontend`. URLs prod: API `https://api-v3-production-2b22.up.railway.app`, front `https://frontend-production-bf96.up.railway.app` (`CLAUDE.md`, `config.py:53`).

### CHECKLIST — ambiente/contrato que o novo front precisa cobrir

- [ ] `VITE_API_URL` (sem `/api`; o cliente concatena `/api`) e `VITE_WS_URL` (opcional, fallback para `VITE_API_URL`) como variáveis de build; dev via proxy `/api`, `/health`, `/socket.io` (ws).
- [ ] Origem do novo front adicionada a `CORS_ORIGINS` da api-v3 (REST **e** SocketIO) e ao CORS do bucket R2 (infra, não código).
- [ ] Cliente HTTP único: `Authorization: Bearer`, JSON por padrão, `FormData` sem `Content-Type`, timeout 15s (30s para blobs), tratamento de `AbortError`.
- [ ] Envelope `{success, message, data}` / `{success:false, error, error_code?}`; **tolerar** `{status:"error", data:{error}}` dos erros JWT; tratar **422 de token inválido como logout**, não só 401.
- [ ] 401 fora de `/auth/*`: restaurar backup de impersonation/contexto (chaves `impersonation_backup`, `tenant_context_backup`) antes de deslogar; single-flight por página.
- [ ] 429: mensagem amigável; não esperar `Retry-After` (não é enviado); backoff no cliente para polling.
- [ ] GET em rota inexistente devolve **200** `{"status":"API online",...}` — validar `success === true` / presença de `data`, nunca só `res.ok`.
- [ ] Propagar/ler `X-Request-ID` da resposta para correlação de logs (opcional, já devolvido).
- [ ] Chaves de storage compatíveis durante a transição: `token`, `user`, `impersonation*`, `tenant_context*`, `recognition-app`; limpar tudo no logout.
- [ ] Tokens: JWT 24h; impersonation e contexto assumido 30 min (claims no próprio JWT, sem header extra); renovação de contexto via `POST /api/v1/admin/tenant-context/.../renew`.
- [ ] Live view: URL tokenizada **só** de `/stream/start` ou `/stream/info`; renovar pelo `exp` do token (TTL 3600 s default); 410 `playback_token_expired` → refresh; 404 → fora do tenant; nunca montar URL HLS à mão.
- [ ] Presigned R2: usar a URL recebida até o `ttl` (1h download, 15 min upload); não cachear além; uploads grandes via PUT direto (`/api/v1/videos/upload-url`).
- [ ] Imagens protegidas (`/api/training/frames/<id>/image`) **não** podem ir em `<img src>` sem auth — usar blob/fetch autenticado ou URL assinada do próprio payload; remover `/api/v1/quality/gate/photos/*` (rota inexistente).
- [ ] Branding: carregar `GET /api/v1/tenant/branding` no boot (5s timeout), aplicar `logo_url`/`favicon_url`/cores; tratar `is_default`.
- [ ] SocketIO: cliente único, namespaces `/monitor`, `/training`, `/quality`, token no `auth`, reconexão infinita; **não depender** dele até o servidor aceitar os namespaces (A1) e isolar por tenant (A2); polling como caminho principal.
- [ ] Não consumir `/health*` para UI (sem envelope, sem auth); usar apenas em smoke/e2e.
- [ ] Swagger `/api/v1/docs` como referência viva em staging (não existe em TESTING/CI).
- [ ] Build/deploy: imagem própria (Dockerfile + `serve.py` ou equivalente com SPA fallback), `ARG` de build para as duas envs, `railway.toml` com `rootDirectory`.
