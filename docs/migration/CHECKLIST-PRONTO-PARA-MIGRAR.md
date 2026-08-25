# Checklist "PRONTO PARA MIGRAR" — novo frontend assume 100% do backend

> Critérios **objetivos** de cobertura. A migração só é declarada pronta quando TODOS os itens
> abaixo estiverem marcados, com evidência (link para PR/commit/print/teste) ao lado de cada um.
> Fonte dos números: `docs/migration/inventory/map_summary.json` (regere com
> `python3 tools/build_migration_map.py build`). Zero mudança de comportamento no backend até lá.

## 0. Pré-condições (antes de começar a migrar)

- [ ] Inventário regenerado no HEAD que será o alvo da migração: `cd services/api && FLASK_ENV=testing python ../../tools/api_inventory.py && python ../../tools/frontend_api_calls.py && cd ../.. && python3 tools/build_migration_map.py inputs build` — diff do `docs/migration/inventory/endpoints.json` revisado (endpoint novo/removido desde o mapa = mapa desatualizado).
- [ ] Coluna **NOVO FRONT** do `MAPA-MIGRACAO-FRONTEND.md` preenchida para **100 %** das linhas (`cobre` / `não cobre` / `n.a.`) — nenhuma célula vazia.
- [ ] Para cada `FRONT-ATUAL` marcado `não cobre`: decisão consciente registrada (dono + data + motivo) — "não cobre" sem decisão = bloqueio.
- [ ] Para cada `GAP-DE-PRODUTO`: decisão `cobre` (entra no design) ou `não cobre` (fica sem UI, registrado) — ver `LISTA-PARA-O-DESIGN.md`.
- [ ] `BACKEND-ONLY` e `ÓRFÃO`: `n.a.` por padrão; nenhum removido nesta rodada (remoção de órfão = rodada própria com issue).

## 1. Endpoints REST (cobertura funcional)

- [ ] 100 % dos endpoints `FRONT-ATUAL` com `cobre` têm chamada equivalente no novo front (mesmo método + path + auth + envelope) — verificável rodando `tools/frontend_api_calls.py` apontado para o novo front (`FRONT_SRC`) e comparando o conjunto de regras casadas com o do front atual: **conjunto novo ⊇ conjunto atual − descartes conscientes**.
- [ ] Nenhuma chamada do novo front **sem regra** no matcher (seção "SEM regra" de `consumers.md` vazia) e nenhuma chamada **dinâmica** não resolvida.
- [ ] As **10 chamadas sem regra** do front atual (lista em `inventory/consumers.md` §"SEM regra") NÃO foram copiadas: `useScenario` → `/api/v1/cameras/<id>/scenario` e `/api/v1/scenarios/operation-types`; `PATCH gate/config`, `export-wiser`×2 e `gate/photos/<path>` não existem no back; `PATCH gate/stations/<code>` é `PUT`; CSV de peças com JWT na query — ou o backend ganhou os endpoints em PR próprio antes.
- [ ] Aliases `/api` × `/api/v1` (cameras, counting, health): o novo front usa **uma** família por recurso e isso está escrito no mapa (recomendado: `/api/v1` onde existir).
- [ ] Envelopes não-padrão tratados: CSV/PDF/binário (`downloadBlob`), `jsonify` cru, redirect, 207 multi-status, 202 + polling.
- [ ] Paginação/cursor, filtros e ordenação replicados exatamente como o back espera (cursor posicional da fila de reapresentação, `page/per_page`, `limit/offset`).
- [ ] Uploads multipart com os mesmos nomes de campo e limites (vídeos de treino, frames, logo de branding, snapshots).
- [ ] Tratamento de 401 (expiração + restauração de impersonation/contexto), 403, 404 cross-tenant (C-01), 409 (seat limit), 429 (rate limit) igual ou melhor que o atual — incluindo os erros do Flask-JWT-Extended que saem com envelope `{status,data:{error}}` e **422 para token inválido** (hoje não dispara logout).
- [ ] Paginação heterogênea respeitada por recurso (`page/per_page` em admin/alerts/demo-videos · `limit` em edge commands/events/heartbeats/feedback · `limit+offset` em `/api/cameras/<id>/alerts` · **cursor** em `/api/v1/edge/events`, heartbeats por site e na galeria de treino/fila de reapresentação) — nenhuma tela assume um único esquema.
- [ ] Datas: regra única no cliente para o formato misto do back (ISO com offset onde há `isoformat()`, **RFC 822 sem offset** onde é `jsonify` default — ex.: `created_at/updated_at` de `/auth/login` e `/auth/me`) e para colunas `timestamp without time zone` (tratar como UTC) — com teste em filtros por período (alertas, eventos, turnos de qualidade).
- [ ] Respostas não-JSON previstas: SSE de `POST /api/chat` (leitor de stream sem timeout de 15 s), CSV/PDF/xlsx via blob autenticado, `redirect`, 207 multi-status.
- [ ] Rotas canônicas escolhidas onde há duplicata com comportamento diferente (branding flat `/api/v1/admin/tenants/<id>/branding` e não `PUT /api/v1/admin/branding` DEPRECATED; retenção `/api/v1/tenant/retention` e não `/api/cameras/tenant/retention` (500); ativação de modelo `/api/v1/models/<id>/activate` e não `/api/training/models/<id>/activate`; alertas pelo domínio `alerts`, não `/api/cameras/<id>/alerts`).
- [ ] Nenhum endpoint da fila `risk:security` do `RESUMO-EXECUTIVO.md` é consumido pelo novo front sem que o backend tenha fechado o furo (ou a decisão de aceitar o risco esteja registrada).

## 2. Tempo real (SocketIO)

- [ ] **Pré-requisito backend — PR [#524](https://github.com/logikos33/Recognition/pull/524) / ADR-0065 mergeado em `develop` (e promovido):** handler `connect` em `/monitor`, `/training`, `/quality` com JWT no handshake (`auth: {token}`) + `join_room('tenant:<tenant_schema>')`; bridge emite só na room. Antes de #524 (estado mapeado em `98bff30e`) o servidor recusava os 4 namespaces e, se aceitasse, vazaria entre tenants. Enquanto #524 não estiver no ambiente-alvo, polling é o contrato real.
- [ ] Todos os eventos da tabela "Contrato tempo real" com status `ok` são assinados pelo novo front nos namespaces corretos (`/monitor`, `/training`, `/quality`) com o mesmo shape de payload (shapes do **publicador**, não dos tipos TS atuais — 5 divergências listadas em `socketio-env.md` A5).
- [ ] Assinaturas mortas e emits sem handler do front atual (`subscribe_camera`/`unsubscribe_camera`, namespace `/admin` — **continua não registrado em #524**) **não** são copiados — ou ganham handler no servidor em PR próprio.
- [ ] Cliente manda o JWT em `auth: {token}` (não em `?token=`) e trata `connect_error` (`auth_required` / `invalid_token` / `tenant_required`); superadmin sem contexto assumido não conecta — a UI não deve tentar.
- [ ] `wsUrl` derivado da mesma regra (`VITE_WS_URL` → fallback `VITE_API_URL`), transports/path iguais, reconexão com backoff.
- [ ] Isolamento por tenant verificado no ambiente-alvo (evento do tenant A não chega ao socket do tenant B — teste de `tests/unit/core/test_socket_auth.py` reproduzido contra DEV/staging com dois tokens).

## 3. Ambiente e contrato transversal

- [ ] `VITE_API_URL` / `VITE_WS_URL` configurados nos 3 ambientes (Desenvolvimento / staging=produção / main) e `API_BASE = VITE_API_URL + /api`.
- [ ] `Authorization: Bearer` em toda chamada autenticada; chaves de `localStorage` (`token`, `user`, `impersonation*`, `tenant_context*`) ou equivalente novo com a mesma semântica de restauração.
- [ ] Impersonation "ver como" e contexto de tenant assumido: início/fim/expiração e banner.
- [ ] URLs pré-assinadas (R2) consumidas direto pelo browser; CORS do bucket confirmado para a origem do novo front.
- [ ] Token de playback HLS (`/api/cameras/<id>/stream/s/<token>/…`) obtido e renovado como hoje (m3u8 sem token = 404).
- [ ] Branding público (`GET /api/v1/tenant/branding`, sem auth) carregado no boot; white-label por tenant.
- [ ] Timeouts (15 s REST / 30 s download) e toasts de erro equivalentes.
- [ ] CORS da API (`CORS_ORIGINS`) inclui a origem do novo front em cada ambiente.
- [ ] `FRONTEND_URL` (env da **API**, `password_reset_service.py`) aponta para o domínio do novo front — o link de "redefinir senha" (`/reset-password?token=`) é montado no servidor.
- [ ] Rota pública `/reset-password` (e `/login`, `/admin/tenants` usados em redirects do `api.ts`) existe no novo front com os mesmos paths, ou os redirects são ajustados.
- [ ] Estado local além da sessão migrado/descartado conscientemente: `recognition-app` (zustand), `recognition-theme`, `epi-chat-messages`, `recognition-dashboard-widgets`, `epi-camera-grid` (layouts/presets VMS), `propagation_dismissed:*`/`search_dismissed:*`, `epi_crop_classifier_session_v1`, `quality_dashboard_mode`, `obs.*` — inventário completo em `inventory/domains/frontend-flows-pages.md` §0.
- [ ] `public/manifest.json` (PWA: nome/cor) revisto — hoje é estático, não white-label por tenant.
- [ ] Swagger (`/api/v1/docs`) **não** é tratado como contrato (cobre ~35/421 rotas); o contrato é o mapa + `inventory/endpoints.json`.
- [ ] Serviço do front em produção decidido (hoje `serve.py` single-thread via Dockerfile; `nginx.conf` existe e não é usado) — cache de `index.html`, gzip, headers.

## 4. Comportamentos (contrato além do REST)

- [ ] Fluxos multi-etapa documentados nas seções "Fluxos" do mapa reproduzidos na mesma ordem: login→`/auth/me`, câmera→probe→config→live view, upload→processa→poll→resultado (treino/propagação/busca), propose→confirm (anotação/propagação), enroll→heartbeat (só visualização no front), harness/test console (superadmin).
- [ ] Gating por role/permission/módulo/feature flag aplicado nas mesmas telas (superadmin-only → 404, não 403).
- [ ] Polling e intervalos (progresso de job, fila, live status) iguais ou melhores, sem aumentar carga na API.

## 5. Prova

- [ ] Suíte e2e do front novo cobre pelo menos os fluxos críticos do RVB (login, live view, galeria/anotação, alertas/eventos, admin de câmeras) no DEV.
- [ ] Smoke contra DEV com o novo front servido por URL própria; `tools/frontend_api_calls.py` sobre o novo front commitado junto (inventário de consumo do novo front no repo).
- [ ] Decisão registrada (ADR) do corte: data, quem aprovou, o que foi conscientemente descartado.
