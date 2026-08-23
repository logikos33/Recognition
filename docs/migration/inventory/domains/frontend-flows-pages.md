# Fluxos do front atual — páginas (pages/, hooks/, components/, stores/, services/)

> Fonte: worktree `origin/develop @ 98bff30e` (`apps/frontend/src`, fora de `modules/`). Tudo abaixo foi lido do código — paths são relativos a `apps/frontend/src/` salvo indicação; backend em `services/api/app/`. Rotas do front são resolvidas como `api.get('/x')` → `GET /api/x` (`services/api.ts:105-107`, `API_BASE = VITE_API_URL + '/api'` ou `/api` via proxy Vite).
> Convenção: **[404]** = chamada sem rota correspondente no Flask (confirmado contra `docs/migration/inventory/consumers.json` e `endpoints.json`); **indeterminado:** = não dá para cravar pelo código.

## 0. Fundamentos transversais (valem para todas as telas)

| Tema | Como o front atual faz | Arquivo:linha |
|---|---|---|
| Cliente HTTP | `request()` único: `Content-Type: application/json` (omitido se `FormData`), `Authorization: Bearer <token>` de `localStorage['token']`, timeout 15 s (`AbortController`), `res.json()` sempre; erro = `data.error \|\| data.msg \|\| 'HTTP n'` | `services/api.ts:128-201` |
| Envelope | O front lê `res.data` (envelope real do backend `{success,message,data}` — `core/responses.py`); vários tipos locais ainda declaram `{status,data}` (ex.: `services/moduleService.ts:22`, `services/cameraService.ts:101`) — só tipagem, runtime usa `.data` | `services/api.ts:189`; `services/eventsService.ts:7-9` |
| 401 | Fora de `/auth/*`: single-flight (`authRedirectStarted`); se há backup de impersonation → restaura superadmin e `window.location='/admin/tenants'`; senão se há backup de contexto de tenant → grava meta expirado em `sessionStorage` e restaura; senão `removeToken()` + `window.location='/login'`. Em `/auth/*` o 401 vira `Error(msg)` para a tela | `services/api.ts:147-181` |
| 403 / 404 / 429 / 5xx | Não há tratamento específico: qualquer `!res.ok` ≠ 401 lança `ApiError(msg,status)` e dispara `showErrorToast` (traduz 403 → "Sem permissão", 503, 500+, timeout; silencia 503/500 de `/cameras`, `/modules/`, `/training`, 410 de `/training/images`, 404 de `/stream/info`; dedup 3 s). **429 não é tratado** (vira toast genérico com a mensagem do backend) | `services/api.ts:183-187`; `utils/errorTranslator.ts:7-75` |
| Download binário | `api.downloadBlob(path)` (timeout 30 s, Bearer) → `URL.createObjectURL` + `<a download>` | `services/api.ts:215-228` |
| SSE / raw | `api.fetchRaw(path, init)` (só Bearer, sem parse) — usado só pelo chat | `services/api.ts:235-242` |
| Sessão | `user` = JSON em `localStorage['user']`; `isAuthenticated = !!(token && user)`; **não há** chamada a `GET /api/auth/me` nem refresh de token de sessão; expiração só é percebida no 1º 401 | `hooks/useAuth.ts:24-29` |
| Gating de UI | `isSuperAdmin = role==='superadmin'`; `isAdmin = admin\|superadmin`; `hasModule(m)` = `user.modules` (claim `modules` do JWT = `tenants.modules_enabled`, `api/v1/auth/routes.py:153-167,189`); `can('dominio:acao')` = `user.permissions` (superadmin sempre true) | `hooks/useAuth.ts:31-42` |
| Sockets | socket.io-client, `transports:['websocket']`, `query:{token}`, reconexão infinita (1 s→10 s); namespaces `/monitor` (detections/alerts/operation:*/edge_telemetry) e `/training` (training_progress); URL = `VITE_WS_URL \|\| VITE_API_URL` | `hooks/useMonitoringSocket.ts:51-58`; `hooks/useTrainingSocket.ts:73-80`; `hooks/useOperationLiveStatus.ts:37-44`; `hooks/useEdgeTelemetrySocket.ts:44-51` |
| Polling | `usePolling(fn, interval, {maxInterval=60s})` com backoff exponencial em falha e pausa quando a aba está oculta (obrigatório por `hooks/AGENTS.md`); várias telas ainda usam `setInterval` cru (listado por tela) | `hooks/usePolling.ts:15-67` |
| Tema | zustand persist `recognition-theme` (modos `recognition-dark` \| `professional` \| `cyberpunk`), classe aplicada em `<html>` + `data-theme` | `stores/themeStore.ts:19-35`; `components/layout/AppShell/AppShell.tsx:40-57` |
| White-label | `ThemeProvider` faz `fetch GET /api/v1/tenant/branding?tenant_id=<user.tenant_id>` (raw fetch, Bearer, timeout 5 s) → CSS vars em `<style id=recognition-tenant-theme>`, `document.title`, favicon; fallback silencioso | `theme/ThemeProvider.tsx:69-138` |
| Env | `VITE_API_URL` (API base + HLS absoluto), `VITE_WS_URL` (sockets) | `services/api.ts:105`; `hooks/useLiveView.ts:33`; `components/camera-grid/CameraGrid.tsx:29` |

### Chaves de storage do cliente (inventário)

| Chave | Tipo | Conteúdo / dono |
|---|---|---|
| `token` | localStorage | JWT de sessão (ou de impersonation/contexto quando ativos) — `services/api.ts:8,26-27` |
| `user` | localStorage | JSON do usuário do login — `hooks/useAuth.ts:48` |
| `impersonation_backup`, `impersonation` | localStorage | backup `{token,user}` do superadmin + meta do alvo — `services/impersonation.ts:64-74` |
| `tenant_context_backup`, `tenant_context` | localStorage | backup + meta `{tenant_id,tenant_name,tenant_slug,started_at}` — `services/tenantContext.ts:90-101` |
| `impersonation_expired`, `tenant_context_expired`, `tenant_context_expired_meta` | sessionStorage | flags pós-401 para toast/banner "Reassumir" — `services/api.ts:159-172` |
| `auto_assume_attempt:<tenantId>` | sessionStorage | anti-loop do auto-assume (60 s) — `hooks/useAutoAssumeTenantContext.ts:41-57` |
| `recognition-app` (migra de `epi-monitor-app`) | localStorage (zustand) | `selectedModule` — `stores/appStore.ts:20-47` |
| `recognition-theme` | localStorage (zustand) | modo de tema — `stores/themeStore.ts:34` |
| `epi-chat-messages` | localStorage (zustand) | últimas 100 mensagens do chat — `stores/chatStore.ts:56-59` |
| `recognition-dashboard-widgets` | localStorage (zustand) | ordem/visibilidade de widgets + período — `stores/dashboardStore.ts:97-104` |
| `epi-camera-grid` | localStorage (zustand) | layout ativo, `cellAssignments` posição→cameraId, presets custom (máx 10), `showLabels` — `stores/cameraGridStore.ts:121-129` |
| `epi_crop_classifier_session_v1` | localStorage | sessão da aba Classificar (aprovações pendentes, contadores, rascunho) — `components/annotation/CropClassifier.tsx:81,592-608` |
| `propagation_dismissed:<jobId>` / `search_dismissed:<jobId>` (prefixos) | localStorage | dispensa de barras de job — `components/annotation/propagationUi.ts:237-253`; `components/annotation/searchContentUi.ts:303-311` |

---

## (a) Tabela de rotas (`AppRoutes.tsx`, `App.tsx`)

Pré-auth (`App.tsx:54-63`): sem `token`+`user` válidos, **qualquer** rota renderiza `Login`, exceto `/forgot-password` e `/reset-password`. Pós-auth: `ThemeProvider` → `AppShell` → `GlobalBanners` → `AppLayout` (TopBar + Sidebar + HealthFooter) → `AppRoutes`; `ChatFAB` em todas as rotas menos `/epi/training*` (`App.tsx:28-33`).

| Rota | Componente | Gating | Endpoints (método path) | Sockets | Storage local |
|---|---|---|---|---|---|
| `*` (deslogado) | `pages/Login.tsx` | nenhum | `POST /api/auth/login`, `POST /api/auth/register` (`hooks/useAuth.ts:45,65`) | — | grava `token`, `user`; `window.location='/'` |
| `/forgot-password` | `pages/ForgotPasswordPage.tsx` | nenhum | `POST /api/auth/forgot-password` (`:22`) | — | — |
| `/reset-password?token=` | `pages/ResetPasswordPage.tsx` | nenhum (token na query) | `POST /api/auth/reset-password` (`:29`) | — | — |
| `/` | `RootRedirect` (`AppRoutes.tsx:38-41`) | role: superadmin→`/admin`, demais→`/modules` | — | — | — |
| `/modules` | `pages/ModuleSelectionPage.tsx` | cards: EPI sempre; Qualidade se `hasModule('quality')`; Carregamento se `isSuperAdmin \|\| hasModule('fueling')` (`:73,118`) | — | — | `recognition-app.selectedModule` |
| `/epi/dashboard` | `pages/epi/EpiDashboard.tsx` | nenhum | `GET /api/cameras` (KPIRow + CameraGrid), `GET /api/modules/epi/stats`, `GET /api/alerts?page=1&per_page=10` (drawer), `GET /api/alerts?per_page=50&page=1`, `GET /api/v1/events/timeline`, `GET /api/v1/events/summary`, `GET /api/cameras/<id>/stream/info?module=epi`, `POST /api/cameras/<id>/stream/start`, `GET /api/v1/admin/inventory?camera_id=` (superadmin, 404 cross-tenant) | `/monitor` on `detection`,`alert` | `epi-camera-grid`, `recognition-dashboard-widgets` |
| `/epi/cameras` | `pages/epi/EpiCameras.tsx` → `pages/CamerasPage.tsx` | botões de edição sem gate no front (backend decide); `CameraModelAssignment` select só `isAdmin`; `CameraFpsConfig` editável p/ `superadmin\|admin\|operator` (`components/cameras/CameraFpsConfig.tsx:49,124`) | `GET /api/cameras`; `POST /api/cameras/probe`; `POST /api/cameras`; `PUT /api/cameras/<id>`; `POST /api/cameras/<id>/test`; `POST /api/cameras/<id>/stream/start`; `POST /api/cameras/<id>/stream/stop`; `POST /api/cameras/<id>/archive`; `POST /api/cameras/<id>/restore`; `PATCH /api/cameras/<id>/config`; `GET /api/cameras/<id>/health-context`; `GET/PUT /api/cameras/<id>/models`; `GET /api/training/models` | — | — |
| `/epi/cameras/triagem` | `pages/CameraTriagePage.tsx` | nenhum no front | `GET /api/cameras`; `PUT /api/cameras/<id>` (name / position_confirmed / is_active); `POST /api/cameras/<id>/snapshot/refresh`; `GET /api/cameras/<id>/snapshot`; `POST /api/cameras/<id>/stream/start` (preview 1 por vez) | — | — |
| `/epi/alerts` | `pages/epi/EpiAlerts.tsx` → `pages/AlertsHistoryPage.tsx` | nenhum | `GET /api/alerts?…`; `GET /api/alerts/export?…` (blob); `POST /api/alerts/<id>/acknowledge`; `GET /api/alerts/<id>/snapshot` | — | filtros iniciais de query string |
| `/epi/training` | `pages/TrainingPage.tsx` | link na sidebar só se `hasModule` em `epi\|quality\|counting` (`components/layout/Sidebar/CollapsibleSidebar.tsx:63-67`); a rota em si não tem guard; aba "Modelos por câmera" editável só com `can('training:approve')` | ver §10 (galeria, estúdio, classificar, cobertura, modelo, treino, propagação, busca) | `/training` on `training_progress` | `epi_crop_classifier_session_v1`, dispensas de job |
| `/epi/training/classes` | `pages/ModuleClassesPage.tsx` | nenhum | `GET /api/modules/epi/classes?include_archived=1`; `PATCH /api/classes/<id>`; `POST /api/classes` | — | — |
| `/epi/cameras/:cameraId/operations` | `pages/epi/EpiOperationsPage.tsx` → `components/training/TrainingModeLayout.tsx` | nenhum | `POST /api/cameras/<id>/stream/start`; `GET /api/cameras/<id>/operations?module_id=ppe`; `GET /api/modules/ppe/operation-types`; `POST /api/cameras/<id>/operations`; `PUT /api/operations/<id>`; `DELETE /api/operations/<id>?confirm_name=` | `/monitor` on `detection`, `operation:status_changed`, `operation:reloaded`; emit `subscribe_camera` | — |
| `/epi/cameras/:cameraId/scenario` | `pages/epi/EpiScenarioEditorPage.tsx` → `components/scenario/ScenarioEditor.tsx` | nenhum | `POST /api/cameras/<id>/stream/start`; **`GET /api/cameras/<id>/scenario` [404]**; **`GET /api/scenarios/operation-types?module=` [404]**; `GET/POST /api/cameras/<id>/operations` | — | — |
| `/epi/reports` | `pages/ReportsPage.tsx` | nenhum | nenhum (placeholder "Em breve") | — | — |
| `/epi/verification` | `pages/VerificationQueuePage.tsx` | nenhum | `GET /api/verification/queue` (poll 15 s); `POST /api/verification/<id>/review` | — | — |
| `/epi/counting` | `pages/CountingPage.tsx` | nenhum | `GET /api/cameras`; `GET /api/counting/sessions`; `POST /api/counting/sessions`; `GET /api/counting/sessions/<id>/stats` (poll 3 s); `DELETE /api/counting/sessions/<id>` | — | — |
| `/epi/health` | `StreamHealthRedirect` (`AppRoutes.tsx:83-92`) | superadmin→`/admin/observability?tab=streams`, demais→`/epi/dashboard` | — | — | — |
| `/epi/sites-health` | `SitesHealthRedirect` (`AppRoutes.tsx:62-72`) | superadmin→`/admin/observability?tab=edge`; admin→`/epi/sites`; demais→`/epi/dashboard` | — | — | — |
| `/epi/sites` | `pages/epi/EpiSitesPage.tsx` | `isAdmin` (senão mensagem "sem permissão", `:45,80`) | `GET /api/v1/edge/sites`; `PATCH /api/v1/edge/sites/<id>` `{deployment_mode}` | — | — |
| `/epi/edge-observability` | `pages/DashboardIntegradoPage.tsx` | nenhum | `GET /api/v1/dashboard/training-metrics/models`; `GET /api/v1/dashboard/training-metrics?models=`; `GET /api/v1/dashboard/edge-telemetry?window=&site_id=` | `/monitor` on `edge_telemetry` | — |
| `/epi/investigation` | `pages/epi/InvestigationPage.tsx` | nenhum | `GET /api/modules/` (useModules); `GET /api/cameras`; `GET /api/modules/<code>/classes`; `GET /api/v1/events/search?…`; `GET /api/v1/events/timeline?…` | — | — |
| `/epi/monitoring` | `pages/MonitoringPage.tsx` | abas de módulo = `user.modules` | `GET /api/cameras` (ou `?module=<m>` — param ignorado pelo backend, filtro é local); `POST /api/cameras/<id>/stream/start`; `GET /api/cameras/<id>/health-context`; `PATCH /api/cameras/<id>/config` | `/monitor` on `detection`,`alert`; emit `subscribe_camera` p/ todas | — |
| `/monitoring` | `EdgeMonitoringGate` → `pages/monitoring/EdgeMonitoringPage.tsx` | `isSuperAdmin`, senão `RootRedirect` (C-01, `AppRoutes.tsx:48-57`) | `GET /api/v1/monitoring/sites`; `POST …/sites/<id>/query`; `POST …/sites/<id>/snapshot`; `GET …/commands/<id>`; `GET/PUT …/sites/<id>/thresholds`; `POST …/sites/<id>/logtail`; `GET …/sites/<id>/detections?window_minutes=` | — | — |
| `/admin/*` | lazy `modules/admin/AdminLayout` | `AdminRoute` (`isSuperAdmin`, senão `/`) (`components/guards/AdminRoute.tsx:9-17`) | ver domínio admin (fora deste doc) | `/admin` | — |
| `/design-system` | lazy `pages/DesignSystemPage.tsx` | `AdminRoute` | nenhum | — | — |
| `/quality/*` | lazy `modules/quality/QualityLayout` | nenhum na rota (card em `/modules` só c/ `hasModule('quality')`) | ver domínio quality | `/quality` | — |
| `/fueling/validation` | `pages/fueling/FuelingValidationPage.tsx` | nenhum | `GET /api/counting/sessions/validation-report?start&end&bay_id&threshold`; `PATCH /api/counting/sessions/<id>` | — | — |
| `/fueling/*` (`?tab=dashboard\|baias\|eventos`) | `pages/fueling/FuelingPage.tsx` | `isSuperAdmin` → busca vídeo demo | `GET /api/fueling/dashboard?period=`; `GET /api/fueling/bays`; `GET /api/cameras`; `GET /api/admin/demo-videos?module=fueling&per_page=1` (superadmin); `GET /api/fueling/events?limit=30`; `GET /api/cameras/<id>/stream/info?module=fueling`; `POST /api/cameras/<id>/stream/start` | — | — |
| `/tablet/:station` | lazy `modules/quality/tablet/TabletKiosk` | pública (sem JWT) | ver domínio quality | `/quality` | — |
| legadas `/home`,`/dashboard`,`/cameras`,`/annotation`,`/training`,`/module-classes`,`/alerts` | `Navigate` | — | — | — | — |
| `*` | `RootRedirect` | — | — | — | — |

Shell comum a todas as rotas autenticadas: `GET /api/v1/health/metrics` (react-query, 60 s, só `isAdmin\|isSuperAdmin`, `components/layout/HealthFooter/HealthFooter.tsx:17-27`); `GET /api/alerts?acknowledged=false&per_page=10&page=1` (sino, 30 s, `components/ui/NotificationBell/NotificationBell.tsx:67-74`); `GET /api/v1/tenant/branding` (1× por `tenant_id`); `POST /api/chat` SSE (chat); `POST /api/v1/admin/tenant-context/renew` (só em contexto assumido).

---

## (b) Fluxos por tela

### 1. Login / registro / recuperação de senha / primeiro acesso

- **Login** (`pages/Login.tsx:22-38`; `hooks/useAuth.ts:44-53`): form `{email,password}` → `POST /api/auth/login` → espera `res.data.{token,user}` → grava `token` e `user` em localStorage → `window.location.href='/'` (reload inteiro; `RootRedirect` decide `/admin` ou `/modules`). Erro (401/429/5xx em `/auth/*`) vira `Error(msg)` exibido inline (`services/api.ts:181`). Backend aplica rate limit em login/register/forgot/reset (`endpoints.json: rate_limited`) — o front só mostra a mensagem, sem contagem regressiva.
- **Criar conta** (aba "Criar Conta", `pages/Login.tsx:25-32`; `hooks/useAuth.ts:62-71`): `POST /api/auth/register {name,email,password}` → grava token/user mas **não** redireciona (fica na tela; próximo render de `App` já vê `isAuthenticated`). Não há tela de "primeiro acesso"/onboarding de tenant nem troca de senha obrigatória — indeterminado no front (nenhum código).
- **Esqueci minha senha** (`pages/ForgotPasswordPage.tsx:17-30`): `POST /api/auth/forgot-password {email}` → sempre mostra "se existir, enviamos" (anti-enumeração).
- **Redefinir** (`pages/ResetPasswordPage.tsx:12-36`): lê `?token=` da URL; sem token mostra erro; `POST /api/auth/reset-password {token,password}` → "Ir para o login".
- **Logout** (`hooks/useAuth.ts:55-60`; `services/api.ts:28-38`): só cliente — remove `token`, `user`, backups de impersonation/contexto; `window.location='/'`. Não chama endpoint.
- **Perfil**: não existe página de perfil/preferências do usuário; TopBar mostra `user.name` + `role` (`components/layout/TopBar/TopBar.tsx:98-109`). Mudança de senha logado: inexistente no front (só via admin, fora deste doc).

### 2. Shell pós-login

- **Seleção de módulo** (`pages/ModuleSelectionPage.tsx:21-34`): seta `appStore.selectedModule` e navega (`/epi/dashboard`, `/quality/dashboard`, `/fueling/dashboard`). Sidebar muda de menu por `selectedModule` (EPI vs FUELING; Qualidade não aparece na sidebar, `CollapsibleSidebar.tsx:45,124`); "Trocar Módulo" limpa e volta a `/modules`; "Painel Admin"/"Configurações" só superadmin (`:148-170`).
- **TopBar** (`TopBar.tsx:46-116`): hambúrguer, breadcrumb por `ROUTE_LABELS`, `NotificationBell`, `ThemeToggle`, nome/role, "Sair".
- **Sino** (`NotificationBell.tsx:67-77,130-133`): react-query 30 s → badge = min(len,99); clique em alerta → `/epi/alerts?camera_id=&acknowledged=false&highlight=<id>`.
- **HealthFooter** (`HealthFooter.tsx:13-66`): só admin/superadmin; superadmin clica → `/admin/observability`.
- **Chat** (`components/chat/ChatFAB.tsx:40-93`; `stores/chatStore.ts`): `POST /api/chat {message, history: últimas 6}` via `fetchRaw`, lê SSE linha a linha `data: {token}` até `[DONE]`; histórico (100 msgs) em localStorage `epi-chat-messages`. Oculto em `/epi/training*`.
- **Banners globais** (`components/layout/GlobalBanners.tsx:27-55`): sticky, publica `--global-banner-offset` (altura) em `:root` para telas `position:fixed` (estúdio de anotação) não ficarem sob o banner.

### 3. Superadmin: "ver como" (impersonation), "assumir contexto" de tenant e câmeras cross-tenant

- **Impersonation** (`services/impersonation.ts:56-92`): `POST /api/v1/admin/users/<id>/impersonate {}` → `res.data.{token,user,expires_in_minutes}`; salva backup `{token,user}` em `impersonation_backup`, meta em `impersonation`, troca `token`/`user`, `window.location='/'`. Sair: `POST /api/v1/impersonation/stop {}` (best-effort) + `restoreImpersonationBackup('/admin/tenants')`. Expiração: 401 → restaura + flag `impersonation_expired` → toast no `ImpersonationBanner` (`components/ImpersonationBanner.tsx:27-36`).
- **Assumir contexto** (`services/tenantContext.ts:59-115`): `GET /api/v1/admin/tenant-context/tenants` (lista) → `POST …/tenants/<id>/assume {}` → backup em `tenant_context_backup`, meta em `tenant_context`, troca token, reload. Sair = só restaurar backup local (sem endpoint, `:107-115`). **Renovação proativa** (`:200-249`): `TenantContextBanner` agenda `POST /api/v1/admin/tenant-context/renew {}` em `exp(JWT) − 5 min` (fallback TTL 30 min), retry 30 s em falha enquanto o token vive, catch-up ao voltar visível; resposta troca `token`/`user` sem reload. Expiração: 401 → restaura superadmin + `tenant_context_expired(_meta)` → banner warning com botão **Reassumir** (novo `/assume`) (`components/TenantContextBanner.tsx:61-137`).
- **Câmera de outro tenant na grade** (`components/camera-grid/CameraCell.tsx:100-127`; `services/crossTenantCameras.ts:92-106`; `hooks/useAutoAssumeTenantContext.ts:63-92`; `components/CrossTenantCameraBanner.tsx:31-88`): `GET /api/cameras/<id>/stream/info` 404 (C-01) → se superadmin, `GET /api/v1/admin/inventory?camera_id=<id>` para descobrir o tenant → store zustand; se TODAS as 404 são de 1 tenant, auto-`/assume` (guard 60 s em sessionStorage); se 2+ tenants, banner manual "Assumir contexto de X". Não-superadmin: toast "Câmera não está transmitindo".

### 4. Dashboard EPI (`/epi/dashboard`)

Ordem de montagem (`pages/epi/EpiDashboard.tsx:110-131`): `CrossTenantCameraBanner` → `KPIRow` → `CameraGrid module="epi"` → `DashboardToolbar` → widgets (drag `@dnd-kit`, ordem/visibilidade em `recognition-dashboard-widgets`).
1. **KPIRow** (`components/dashboard/KPIRow.tsx:41-73`): `usePolling` 30 s de `Promise.allSettled([GET /api/cameras, GET /api/modules/epi/stats])`; lê `data.stats.{alerts_today, compliance_rate, alerts_last_hour, alerts_prev_hour, active_model_name, active_model_map50, compliance_by_class}`; câmeras ativas = `stream_status==='active' || is_active` contadas no cliente. Card "Alertas Hoje" expande → `GET /api/alerts?page=1&per_page=10` (`:76-83`).
2. **CameraGrid** (`components/camera-grid/CameraGrid.tsx:57-72`): `usePolling(GET /api/cameras, 60 s)`; socket `/monitor` (detections por `camera_id`, alerts). Layouts `1x1,2x2,3x3,4x4,1+5,1+7` (`types/cameraGrid.ts`), atribuição célula→câmera, swap por drag, presets custom (máx 10), fullscreen, menu de contexto, `GridPanel` (seletor + botão "Nova câmera" que abre `CameraWizard`) — tudo client-side em `epi-camera-grid`. Cada `CameraCell` (`CameraCell.tsx:68,100-127`): `useLiveView` (→ `POST /stream/start`) + `GET /api/cameras/<id>/stream/info?module=epi` (decide `hls` vs `demo_video` superadmin); overlay `DetectionOverlay` escala bbox em pixels do frame original → canvas (`components/monitoring/DetectionOverlay.tsx:59-66`).
3. **Widgets**: timeline (`GET /api/v1/events/timeline?from&to&bucket&module_code=epi`, react-query 60 s, `components/dashboard/widgets/AlertsTimelineWidget.tsx:35-45`), distribuição e top câmeras (`GET /api/v1/events/summary?…`, `ViolationsDistributionWidget.tsx:20-25`), últimos alertas + registro de eventos (`GET /api/alerts?per_page=50&page=1`, 60 s, query compartilhada `useDashboardAlerts.ts:36-41`). Período `24h|7d|30d` do store.

### 5. Câmeras (`/epi/cameras`)

- **Listar** (`pages/CamerasPage.tsx:76-94`): `GET /api/cameras` → `data.cameras` + `data.gateway_status.status` (badge "Gateway"); lista à esquerda, painel à direita.
- **Nova câmera = CameraOnboardingWizard** (4 passos, `components/cameras/CameraOnboardingWizard.tsx:35-116`): Fabricante (`intelbras|hikvision|dahua|generic`) → Acesso (`name, ip_or_host, port=554, username=admin, password, channel=1, is_behind_nat`) → **probe** `POST /api/cameras/probe {manufacturer, ip_or_host, port, username, password, channel, is_behind_nat}` → `data.{ok,method,codec,resolution,fps,substream_url_sugerida,gateway_available,warning,error}` (passo "Verificação") → Confirmar: `POST /api/cameras {name, manufacturer, host, port, username, password, channel, detection_stream_url: substream_url_sugerida, video_codec: codec}` → `onComplete` recarrega lista. (Não envia `site_id` — o backend avisa que sem ele a câmera fica invisível pro edge, `api/v1/cameras/crud_handlers.py:113-115`.)
- **Editar = CameraWizard** (4 passos, `components/cameras/CameraWizard.tsx:38-158`; também usado p/ criar a partir da grade): Fabricante → Conexão (`ip` IPv4 validado por regex, `port`, `username`, `password`, `path` → `rtsp_url_override`) → Identificação (`name`, `location`) → Teste: **fase 1** salva (`POST /api/cameras` se novo, senão `PUT /api/cameras/<id>`, mapeamento `ip→host`, `path→rtsp_url_override`, `services/cameraService.ts:55-68`) → **fase 2** `POST /api/cameras/<id>/test` → `checks{url_format,host_reachable,port_open,rtsp_response,stream_available}` + `suggestion`; "Concluir" só habilita com `success`.
- **Testar conexão** do painel (`CamerasPage.tsx:155-174`): `POST /api/cameras/<id>/test`, log local com tradução de erro.
- **Iniciar/Parar stream** (`:133-153`): `POST /stream/start` → `data.hls_url` (absolutiza com `VITE_API_URL`) → `CameraPlayer`; `POST /stream/stop` zera URL. (Obs.: `/stream/stop` mata o FFmpeg para todos os espectadores — `components/monitoring/CameraPlayer.tsx:274-285`.)
- **Arquivar/Desarquivar** (`:100-131`): `ConfirmDialog` → `POST /api/cameras/<id>/archive` | `/restore` (nunca `DELETE` — `services/cameraService.ts:187-194`).
- **Modelos por módulo** (`components/cameras/CameraModelAssignment.tsx:71-106`): `Promise.all([GET /api/cameras/<id>/models, GET /api/training/models])` → 3 selects (epi/quality/counting); `PUT /api/cameras/<id>/models {module, model_id|null}`; só `isAdmin` edita.
- **FPS/qualidade/coleta** (`components/cameras/CameraFpsConfig.tsx:145-189`): `GET /api/cameras/<id>/health-context` ao montar (telemetria do site p/ semáforo de carga; fallback heurístico `fps×n×2`); salvar = `PATCH /api/cameras/<id>/config {fps_target, quality_preset, collection_subtype?}` → toast extra se `data.propagation.queued`. Edita: `superadmin|admin|operator`.
- Atalhos: "Operações" → `/epi/cameras/<id>/operations`; "Cenário" → `/epi/cameras/<id>/scenario` (`:369-373`).

### 6. Live view HLS com token de playback (transversal)

- `useLiveView(cameraId, enabled)` (`hooks/useLiveView.ts:118-264`): `POST /api/cameras/<id>/stream/start` → `data.hls_url` (`/api/cameras/<id>/stream/s/<exp>.<sig>/stream.m3u8`, token **no path**; `?token=` não funciona, `:11-15`); cache module-level por câmera + dedupe in-flight (`:48-92`); renovação ancorada no `exp` extraído da URL (`playbackTokenExpMs`, `:56-59`) com margem 5 min, retry 30 s em falha, pausa quando a aba está oculta, catch-up ao voltar (`:190-259`); `refresh()`/`refreshLiveViewUrl()` forçam novo start.
- `CameraPlayer` (`components/monitoring/CameraPlayer.tsx`): hls.js `lowLatencyMode`, `liveSyncDurationCount:2`, retries internos 2×2 s (`:203-215`); watchdog de stall 14 s (`:16`) → backoff 1/2/5 s (`:22,106-117`); **HTTP 410** (token expirado, sinal dedicado do `serve_hls`) → recuperação imediata pedindo URL nova (`:232-243`); erro fatal de rede (404 manifesto / 425 nos .ts) → ciclo 0,2,4,8,16,30 s com limite e estado "recoveryFailed" + botão tentar de novo (`:30,247-253`); aba oculta → destrói hls.js e solta `<video>` (sem endpoint de release; o backend expira `epi:stream:{id}:active` sozinho, `:280-302`); ao voltar visível → `refreshLiveViewUrl` (`:317-335`). Safari nativo via `canPlayType` (`:263-268`). `feedType='demo_video'` renderiza `<video loop>` (superadmin demo).
- Regra de sessão única: card da grade suprime o player quando o drawer da mesma câmera está aberto (`pages/MonitoringPage.tsx:133-158`).

### 7. Triagem de canais (`/epi/cameras/triagem`)

`GET /api/cameras` → ordena por `channel` (`pages/CameraTriagePage.tsx:76-94`); totalizador local de upload/egress por `live_view_subtype` (constantes medidas, `:28-41`). Ações: renomear inline `PUT /api/cameras/<id> {name}` (`:138-143`); "posição confirmada" `PUT {position_confirmed:true}` otimista com rollback (`:155-165`); ativar/arquivar selecionadas em lote = N × `PUT {is_active}` sequenciais (`:173-200`, `ConfirmDialog` para arquivar); preview ao vivo de **uma** câmera por vez (`useLiveView(previewId)`, `:72,226-232`); miniatura de câmera draft = `CameraSnapshotThumbnail` (IntersectionObserver → `useCameraSnapshot`: `POST /api/cameras/<id>/snapshot/refresh` → poll `GET /api/cameras/<id>/snapshot` a cada 4 s, máx 15 tentativas, fila de concorrência compartilhada `snapshotQueue`; `url` presignada R2 quando `status==='ready'`, `hooks/useCameraSnapshot.ts:18-19,41-91`); modal ampliado `CameraSnapshotViewer`.

### 8. Monitoramento VMS (`/epi/monitoring`)

`pages/MonitoringPage.tsx:390-470`: abas "Todas" + `user.modules`; `GET /api/cameras` (ou `?module=<m>` — o backend ignora o param, `api/v1/cameras/crud_handlers.py:67-98`; o filtro real é local por `module_code`, `:558-564`); socket `/monitor` e `subscribe_camera` para todas as câmeras quando conecta (`:463-466`); cards com IntersectionObserver (rootMargin 150 px) → `useLiveView` só visível (`:125-158`); overlay de detecções com debounce 200 ms (`:480-491`); drawer (`AppDrawer`) por câmera com abas Feed / Logs (throttle 500 ms, últimos 50) / Desempenho (`CameraFpsConfig` + `health-context`) (`:234-300,536,645`). Banner cross-tenant idem §3.

### 9. Alertas (`/epi/alerts`)

`pages/AlertsHistoryPage.tsx:41-118`: filtros (`camera_id`, `start_date`, `end_date`, `violation_type ∈ no_helmet|no_vest|no_gloves|no_safety_glasses`, `acknowledged ∈ ''|false|true`, `page`, `per_page=20`) inicializados da query string (deep-link do sino, `?highlight=<id>` rola e destaca 4 s); `GET /api/alerts?…` → `data.{alerts,total,page,per_page,pages}`; exportar `GET /api/alerts/export?…` via `downloadBlob` → `alertas.csv`; reconhecer `POST /api/alerts/<id>/acknowledge` (também ao pairar o mouse por alguns segundos, `:168-187`); clique abre detalhe e, se `evidence_key`, `GET /api/alerts/<id>/snapshot` → `data.snapshot_url` (URL presignada). Rótulos de violação hardcoded (`utils/labels.ts`, `NotificationBell.tsx:44-50`).

### 10. Treinamento (`/epi/training`) — seis abas (`pages/TrainingPage.tsx:470-478`)

Ao montar: `GET /api/v1/training/propagation/jobs` (reexibe barra de job ativo/recente não dispensado, `:226-240`); `Promise.allSettled([GET /api/training/models, GET /api/classes])` (`:258-269`); `GET /api/training/jobs/current/status` imediato + `setInterval` 3 s (`:334-367`); `GET /api/training/jobs` (`:361`); socket `/training` (`:329-331`).

**10.1 Imagens = galeria** (`components/training/TrainingGallery.tsx`): `GET /api/training/images?page&page_size=60[&curation_status=active|duvida|excluida][&is_annotated=true|false][&pending_review=true][&camera_ids=a,b][&source=nvr|upload|auto|video]` (`:233-285`, descarta resposta superada por `loadSeqRef`) → `data.{frames[],total,total_pending_proposals,page,page_size,total_pages}`; facetas `GET /api/training/images/facets?…` (`:288-303`); seleção múltipla (clique/Shift/Ctrl); curadoria em lote `POST /api/training/frames/curation {frame_ids[], status: active|duvida|excluida}` sem diálogo + toast "Desfazer" 8 s que reverte com outro POST (`:494-532`); **upload** `POST /api/v1/videos/images/upload` multipart campo `images` (N arquivos jpg/png/webp, máx 50) → `data.uploaded` (`:541-574`); clique simples abre o **estúdio** com a lista congelada da página atual + continuação paginada (`:457-471`); "Anotar selecionadas"; "Buscar por conteúdo" na seleção (§10.7).

**10.2 Estúdio de anotação** (`components/annotation/AnnotationStudio.tsx`, tela cheia, `position:fixed` com `--global-banner-offset`): `GET /api/modules/<moduleCode>/classes` (filtra `is_active!==false && !archived_at`, `:224-240`); por frame `GET /api/training/frames/<id>/annotations` → **`{success, annotations[]}` no topo (não em `data`)** (`:268-285`; backend `api/v1/training/annotation_handlers.py:62`); autosave debounce 800 ms e flush ao trocar de frame/sair = `POST /api/training/frames/<id>/annotations {annotations:[{class_id,class_name,module_code,x_center,y_center,width,height}]}` replace-all (`:80,292-330`); `beforeunload` faz `fetch keepalive` do mesmo POST com Bearer (`:343-360`); F = dúvida (`POST /training/frames/curation` status `duvida`, `:500-512`); fila de propostas de IA (`source==='ai'`): **V** aprova — se editou, flush do save e depois `POST /training/frames/<id>/pre-annotation-review {status:'accepted'}`; se não editou, `POST /training/frames/<id>/accept-suggestions` (`:523-558`); **X** rejeita `POST …/pre-annotation-review {status:'rejected'}` sem salvar caixas (`:561-583`); criar classe inline `POST /api/classes` (`:904`); imagem = `frame.url` presignada com fallback `GET /api/training/frames/<id>/image` (`:934-937`; ver (c)); painel "buscar imagens iguais" (§10.6); atalhos D/→ A/← 1–9 C F V X H B +/− Esc Ctrl+Z ? G (`:10-18`).

**10.3 Classificar = CropClassifier** (`components/annotation/CropClassifier.tsx`): `GET /api/modules/epi/classes` (`:374`), `GET /api/training/coverage-matrix` (lacunas p/ ordenar por carência, `:393`), fila `GET /api/training/images?page=1&page_size=40&is_annotated=false&curation_status=active&only_crops=true[&camera_ids][&proposal_classes=a,b]` (`:405-446`) + prefetch keyset `&before_id=<último>` (`:447-480`); por recorte `GET /api/training/frames/<id>/annotations` (`:515-522`); teclado por tipo/estado de EPI (`cropClassifierLogic.ts:398-418`); **Aprovar** = `POST /api/training/frames/<id>/annotations` com humanas preservadas + novas (`:728-770`); "Não sei"/"Recorte ruim" = `POST /training/frames/curation` `duvida|excluida` (`:783`); desfazer reverte via `curation active` ou novo POST de anotações (`:811,837`); **toda a sessão é persistida em `localStorage['epi_crop_classifier_session_v1']` ANTES de cada POST e replayed no próximo mount** (proteção contra o redirect de 401 que recarrega a página, `:29-31,592-608`); "Ajustar caixa" abre o estúdio.

**10.4 Cobertura** (`components/training/CoverageMatrix.tsx:75`): `GET /api/training/coverage-matrix` → `targets`, `totals`, `classes[]`, `cameras[]`, `cells[]`, `gaps[]`; deep-links "anotar →" (galeria filtrada por câmera) e "classificar →" (aba Classificar com `camera_id`+`class_id`) (`pages/TrainingPage.tsx:196-211`).

**10.5 Modelo / Modelos por câmera / Treino ao vivo / Classes**
- Modelo (`TrainingPage.tsx:258-312,530-706`): lista `GET /api/training/models` (+`GET /api/classes`), badge "simulado" (`origin==='simulated' || metrics.simulated`), ativar `POST /api/v1/models/<id>/activate {}` (409 `eval_rejected` exibido pelo toast global), "Configurar" abre `ModelScenarioWizard` (6 passos: identificação, classes, linha, ROI, confiança 0.10–0.99, câmera; carrega `GET /api/training/scenarios/<modelId>/config` + `GET /api/cameras`; salva `PUT /api/training/scenarios/<modelId>/config {classes, counting_line, roi, confidence_threshold, camera_id}`, `components/scenario/ModelScenarioWizard.tsx:111-112,147-169`); link `/epi/training/classes`.
- Modelos por câmera (`components/training/CameraModelScope.tsx:136-200`): `cameraService.list()` + `GET /api/v1/models` (só com `r2_onnx_key`) → N×`GET /api/v1/models/<id>` (classes via `lineage.dataset_version.class_distribution`) + N×`GET /api/cameras/<id>/model-config?module=<active_module|epi>`; salvar `POST /api/cameras/<id>/model-config {model_id, module_code, config:{classes[...]}}`; edição só `can('training:approve')` (`:123`).
- Treino ao vivo (`TrainingPage.tsx:334-462,709-993`): banner "GPU não configurada" quando `gpu_enabled=false` (link `/admin/integrations?type=vast_ai` só superadmin); `POST /api/training/jobs {preset:'balanced', module, model_size, total_epochs, batch_size, learning_rate}`; `POST /api/training/jobs/<id>/stop {}`; logs = poll 3 s `current/status.live` + eventos `training_progress` (sparklines loss/mAP50 com histórico 200, `hooks/useTrainingSocket.ts:85-113`).
- Classes (`pages/ModuleClassesPage.tsx:224,272-282,315-323,387,400-414`): `GET /api/modules/epi/classes?include_archived=1`; rename/arquivar/restaurar/reordenar = `PATCH /api/classes/<id> {display_name|archived|display_order}` (drag reordena e **muda a tecla 1–9**); criar `POST /api/classes {name,color,module:'epi'}`; toast "Desfazer".

**10.6 Propagação semeada ("buscar imagens iguais")** (`components/annotation/SimilarSearchPanel.tsx:81-125`; `services/propagationService.ts:131-156`): painel ancorado no estúdio; **propose→confirm**: `GET /api/v1/training/propagation/preflight?camera_id&date_from&date_to&validation_only` → `{gpu_provider, pool_total, pool_effective, seed_*, active_job, third_party_cloud_enabled, runpod_configured, gpu{estimated_cost_usd,price_error,…}}` (CTA bloqueado sem preço, nuvem desabilitada ou job ativo) → `POST /api/v1/training/propagation/jobs {camera_ids:[id], date_from, date_to, validation_only, max_results?}` → `PropagationStatusBar` faz `GET …/propagation/jobs/<id>` a cada **5 s** (`PropagationStatusBar.tsx:20,56`); "Revisar" troca o filtro da galeria para `proposta_pendente`; dispensa em localStorage.

**10.7 Busca por conteúdo** (`components/annotation/SearchContentPanel.tsx:50-147`; `services/searchService.ts:113-157`): sobre a seleção da galeria; **propose→confirm**: `POST /api/v1/training/search/preflight {frame_ids[], terms[{label,query}]}` (recalcula a cada mudança de termo; máx `MAX_TERMS_PER_JOB`) → `POST /api/v1/training/search/jobs {frame_ids, terms}` → `SearchStatusBar` `GET …/search/jobs/<id>` a cada **4 s** (`SearchStatusBar.tsx:18,52`) → `SearchFindingsPanel`: achados agrupados por termo, promover `POST …/search/jobs/<id>/promote {items:[{index,class_name}]}` → `data.promoted` (`:132-147`), criar classe inline `POST /api/classes` (`:163`); lista `GET …/search/jobs` ao abrir a galeria (reexibe job recente).

### 11. Eventos / Investigação (`/epi/investigation`)

`pages/epi/InvestigationPage.tsx:238-320`: `GET /api/modules/` (módulos do tenant) → filtros módulo/classes (`GET /api/modules/<code>/classes`)/câmeras (`GET /api/cameras`)/período/confiança; lista `GET /api/v1/events/search?from&to[&module_code][&class_name[]…][&camera_id[]…][&min_confidence]&page&per_page=20` → `data.{events,total,pages}`; timeline `GET /api/v1/events/timeline?…&bucket=` (best-effort); cada evento com `frame_url` (URL presignada) abre modal `<img>`.

### 12. Verificação humana (`/epi/verification`)

`pages/VerificationQueuePage.tsx:52-79`: `GET /api/verification/queue` → `data.items[]` (só `needs_human`), `setInterval` **15 s**; `POST /api/verification/<id>/review {verdict:'approve'|'reject'}` remove da lista.

### 13. Contagem (`/epi/counting`)

`pages/CountingPage.tsx:60-160`: `Promise.all([GET /api/cameras, GET /api/counting/sessions])`; se há sessão `status==='active'` retoma polling; iniciar `POST /api/counting/sessions {camera_id}` → `data.session`; stats `GET /api/counting/sessions/<id>/stats` (`setInterval` **3 s**) → `{counts,total}`; encerrar `DELETE /api/counting/sessions/<id>` → `data.session.total_counts`. Validação/aceite (fueling): `GET /api/counting/sessions/validation-report?start&end&bay_id&threshold` e `PATCH /api/counting/sessions/<id> {manual_count|acceptance_status}` (`pages/fueling/FuelingValidationPage.tsx:123,136,255`).

### 14. Operações por câmera (`/epi/cameras/:id/operations`)

`components/training/TrainingModeLayout.tsx` + `hooks/useOperations.ts:20-109`: `GET /api/cameras/<id>/operations?module_id=ppe` → `data.operations`; catálogo `GET /api/modules/ppe/operation-types` → `data.types`; modais criar `POST /api/cameras/<id>/operations {module_id,type_id,name,config}`, editar `PUT /api/operations/<id> {name,config}`, excluir `DELETE /api/operations/<id>?confirm_name=<nome digitado>`; formulários por tipo (`components/training/operationTypeForms/*`: count_static, overlap_dynamic/fixed, position, zone_tuning); ROI/linha desenhados sobre o vídeo (`RoiDrawer`, `LiveVideoWithOperations` com `useMonitoringSocket` para detecções); status ao vivo via `/monitor` `operation:status_changed` / `operation:reloaded` (`hooks/useOperationLiveStatus.ts:49-70`). Observação: `moduleId='ppe'` fixo (`pages/epi/EpiOperationsPage.tsx:63`) — indeterminado se o backend trata `ppe` como sinônimo de `epi` (não verificado aqui).

### 15. Cenário (`/epi/cameras/:id/scenario`) — quebrado, ver (c)

`components/scenario/ScenarioEditor.tsx:69,172-177,217`: `useScenario` (`GET /api/cameras/<id>/scenario` **[404]**) + `useScenarioOperationTypes` (`GET /api/scenarios/operation-types?module=` **[404]**) + `useOperations`; salvar = `createOperation` (`POST /api/cameras/<id>/operations`). Com os dois GETs em 404 a página mostra o erro do cenário (`:308-313`) e o editor não abre.

### 16. Sites edge (`/epi/sites`) · 17. Dashboard integrado (`/epi/edge-observability`) · 18. `/monitoring` oculta

- Sites (`pages/epi/EpiSitesPage.tsx:40-80`): `GET /api/v1/edge/sites` → select `deployment_mode ∈ edge|hybrid|cloud` → `PATCH /api/v1/edge/sites/<id> {deployment_mode}` otimista com rollback. Só `isAdmin`.
- Dashboard integrado (`pages/DashboardIntegradoPage.tsx:203-250`): `GET /api/v1/dashboard/training-metrics/models` → multi-seleção → `GET /api/v1/dashboard/training-metrics?models=a,b` (curvas por época); telemetria `GET /api/v1/dashboard/edge-telemetry?window=15m|1h|6h|24h[&site_id]` + socket `/monitor` `edge_telemetry` (buffer 120 amostras).
- `/monitoring` (`pages/monitoring/EdgeMonitoringPage.tsx:43-94`; `SiteMonitor.tsx:96-218`; `LogtailModal.tsx:67-79`; `services/monitoringService.ts:54-105`): `GET /api/v1/monitoring/sites` → seleciona site → padrão **comando assíncrono**: `POST …/sites/<id>/query {window,max_points?,layers?,from_epoch?,to_epoch?}` ou `POST …/sites/<id>/snapshot {}` (usePolling 10 s) ou `POST …/sites/<id>/logtail {unit,lines}` devolvem `command_id` → `usePolling(GET …/commands/<id>, 2,5 s)` até concluir; `GET …/sites/<id>/detections?window_minutes=60` (30 s); thresholds `GET/PUT …/sites/<id>/thresholds {thresholds}`.

### 19. Relatórios (`/epi/reports`)
Placeholder sem chamada (`pages/ReportsPage.tsx`). `GET /api/reports/home` e `GET /api/v1/reports/export` só são referenciados por código morto (ver anexo).

### 20. Fueling (`/fueling/*`, `/fueling/validation`)
`pages/fueling/FuelingPage.tsx:248-368`: aba por `?tab=` (deep-link da sidebar); `GET /api/fueling/dashboard?period=`, `GET /api/fueling/bays`, `GET /api/cameras`, `GET /api/fueling/events?limit=30`; `setInterval` 30 s (dashboard + baias); superadmin busca `GET /api/admin/demo-videos?module=fueling&per_page=1` e `BayCameraCard` consulta `GET /api/cameras/<id>/stream/info?module=fueling` (demo vs HLS) + `useLiveView`.

---

## (c) Fluxos SEM endpoint claro / quebrados

Conferido contra `consumers.md` (seção "SEM regra"), `consumers.json` e `endpoints.json`; itens marcados † não aparecem no matcher (template literal multilinha) e foram verificados manualmente.

| # | Chamada do front | Arquivo:linha | Situação no backend | Tela impactada |
|---|---|---|---|---|
| 1 | `GET /api/cameras/<id>/scenario` | `hooks/useScenario.ts:25` | 404 — a rota existe só como `GET /api/v1/cameras/<id>/scenario` (`api/v1/scenarios/routes.py:44`) | `/epi/cameras/:id/scenario` (ScenarioEditor) mostra erro e não abre |
| 2 † | `GET /api/scenarios/operation-types?module=` | `hooks/useScenario.ts:53-56` | 404 — existe `GET /api/v1/scenarios/operation-types` (`api/v1/scenarios/routes.py:102`) | idem — catálogo de tipos vazio |
| 3 | `GET /api/cameras?module=<m>` | `pages/MonitoringPage.tsx:439-443` | Rota existe, mas `list_cameras` não lê `module` (`api/v1/cameras/crud_handlers.py:67-98`); filtro é feito no cliente | `/epi/monitoring` (funciona, param inútil) |
| 4 † | `<img src="…/api/training/frames/<id>/image">` (fallback quando a presignada falha) | `components/annotation/AnnotationStudio.tsx:934-937` | Rota `@jwt_required()` só por header (`api/v1/training/routes.py:125-128`; sem `JWT_QUERY_STRING`) — `<img>` não manda Bearer → 401 | Estúdio: frame sem URL presignada aparece "quebrado" |
| 5 | `api.ts:139/222/238` `/api<param>` | `services/api.ts` | falso positivo do matcher (é o próprio `fetch` genérico) | — |
| 6 | `CameraCell.tsx:106` e `MonitoringPage.tsx:443` "dinâmicas" | idem | resolvidas acima (`/stream/info?module=` e `/cameras[?module=]`) | — |
| 7 | Logout | `hooks/useAuth.ts:55-60` | só cliente; não existe/não é chamado endpoint de logout ou revogação de sessão | todas |
| 8 | Hidratação de sessão | `hooks/useAuth.ts:24-29` | nunca chama `GET /api/auth/me` (existe em `api/v1/auth/routes.py:276`); `user`/`permissions`/`modules` podem ficar desatualizados até novo login | gating de UI (sidebar, cards de módulo, `can()`) |
| 9 | Sair do contexto de tenant | `services/tenantContext.ts:112-115` | só troca de token local — sem endpoint de "stop" (diferente do impersonation) | banner de contexto |
| 10 | Seleção de módulo, layout da grade, presets, widgets do dashboard, tema, chat history, dispensa de jobs, sessão do classificador | stores/localStorage (§0) | estado 100 % cliente — não há endpoint de preferências do usuário | perde-se ao trocar de navegador |
| 11 | `/epi/reports` | `pages/ReportsPage.tsx` | placeholder; backend tem `GET /api/reports/home`, `/api/reports/compliance`, `/api/v1/reports/export` sem consumidor vivo | relatórios inexistentes na UI |
| 12 | Tipos `{status, data}` | `services/moduleService.ts:22`, `cameraService.ts:101`, `countingService`, `hooks/useOperations.ts:26` | envelope real é `{success,message,data}`; só tipagem (runtime lê `.data`) — não quebra, mas engana | — |
| 13 | `moduleId='ppe'` nas operações | `pages/epi/EpiOperationsPage.tsx:63` | indeterminado: não verificado se `operations` aceita `ppe` como módulo EPI | `/epi/cameras/:id/operations` |
| 14 | 429 (rate limit) em login/forgot/reset/test/training jobs/tenant-context | `services/api.ts:183-187` | backend limita (`endpoints.json: rate_limited`); front só mostra a mensagem do erro, sem `Retry-After` | Login, Testar conexão, Treino, Assumir contexto |

Código morto (não roteado/não importado; mantém chamadas no inventário): `pages/HomePage.tsx` (`GET /api/reports/home` via `services/reportService.ts`), `pages/DashboardPage.tsx` (`GET /api/v1/dashboard/stats`, `/api/training/videos`, `/api/training/jobs`, `GET /api/v1/reports/export`), `components/layout/Header/Header.tsx`, `components/monitoring/AlertsPanel.tsx` (`GET /api/cameras/<id>/alerts`, `POST /api/alerts/<id>/acknowledge`), `components/cameras/CameraCard.tsx`, `components/training/FrameTimeline.tsx`, `hooks/useFrameExtraction.ts` (`POST /api/v1/videos/<id>/finalize-extraction`), `hooks/useTraining.ts` + `services/trainingService.ts` (`GET /api/training/jobs/<id>/status|progress`, `POST /api/training/models/<id>/activate`, `GET/POST /api/training/videos` — só `listModels` é usado vivo por `CameraModelAssignment`), `hooks/useOperationDirty.ts`, `hooks/useModuleClasses.ts`.

---

## (d) O que o novo front precisa replicar (lista de produto)

1. **Autenticação**: login e-mail/senha, criar conta, esqueci/redefinir senha por link com token; sessão persistida em storage; logout local; tratar 401 com redirect único (single-flight) e 429 com mensagem amigável.
2. **Pós-login por papel**: superadmin → `/admin`; demais → seleção de módulo (EPI sempre; Qualidade/Carregamento conforme `modules` do tenant); sidebar por módulo; itens Admin/Configurações só superadmin; "Treinamento" só se o tenant tem `epi|quality|counting`.
3. **Superadmin operando clientes**: "ver como" usuário (30 min, banner + sair), "assumir contexto" de tenant (30 min, banner danger, renovação proativa antes de expirar, reassumir após expirar), detecção de câmera cross-tenant (404 → inventário → banner/auto-assume).
4. **White-label**: branding por tenant (cores, nome, logo, favicon) aplicado antes da UI; tema claro/escuro do usuário.
5. **Dashboard EPI**: KPIs (câmeras ativas, conformidade 24 h c/ detalhamento por EPI, alertas hoje/hora, modelo ativo + mAP50) com polling 30 s; grade VMS estilo DVR (layouts 1x1…1+7, arrastar, presets, fullscreen, rótulos) persistida por usuário; widgets BI reordenáveis/ocultáveis (timeline, distribuição, top câmeras, últimos alertas, registro de eventos) por período 24h/7d/30d.
6. **Live view**: sempre obter a URL HLS do backend (`/stream/start`, token no path, TTL 1 h), renovar antes de expirar, recuperar de 410/404/425 re-assinando, parar de buscar segmentos em aba oculta, sessão única por câmera, fallback Safari, overlay de detecções por WebSocket com `subscribe_camera`.
7. **Câmeras**: lista + detalhe; onboarding em 4 passos com **probe** antes de salvar (sugere substream/codec); edição em 4 passos com salvar→testar (5 checks); testar conexão; iniciar/parar stream; arquivar/restaurar (nunca apagar); FPS/qualidade/substream de coleta com aviso de carga baseado em telemetria do site; modelo por módulo por câmera (admin); atalhos p/ operações e cenário.
8. **Triagem de canais**: ordenação por canal, rename inline, confirmar posição, ativar/arquivar em lote, preview ao vivo de uma câmera por vez, miniatura por snapshot sob demanda (refresh + poll) com fila de concorrência, totalizador de upload/egress.
9. **Monitoramento VMS**: abas por módulo, cards lazy (só visíveis pedem stream), drawer com feed/logs ao vivo/desempenho.
10. **Alertas**: histórico paginado com filtros (câmera, datas, tipo, status) via query string, deep-link do sino com destaque, reconhecer, ver snapshot presignado, exportar CSV; sino com pendentes (30 s).
11. **Treinamento**: galeria paginada (60) com facetas, filtros (status/curadoria/propostas pendentes/câmeras/origem), seleção múltipla, curadoria com desfazer, upload multipart de imagens; **estúdio keyboard-first** com autosave (debounce + flush + keepalive), fila congelada com reabastecimento, propostas de IA (aprovar/rejeitar), dúvida, zoom/pan, undo/redo, criar classe inline, guidelines; **classificação por recorte** (multilabel por tipo de EPI, fila por carência, prefetch keyset, persistência local anti-401, desfazer); **matriz de cobertura** com deep-links; modelos (ativar com gate campeão×desafiante, configurar cenário 6 passos, origem/simulado); modelos+escopo por câmera (permissão `training:approve`); treino ao vivo (iniciar/parar, status 3 s + socket, logs, sparklines, aviso GPU); classes do módulo (rename, cor, arquivar/restaurar, reordenar = tecla); propagação semeada e busca por conteúdo com **preflight de custo → confirmar → barra de progresso (4–5 s) → revisar/promover**.
12. **Investigação de eventos**: filtros (módulo, classes, câmeras, período, confiança), timeline por bucket, lista paginada com preview presignado.
13. **Verificação humana**: fila `needs_human` (15 s) com aprovar/rejeitar.
14. **Contagem**: iniciar/encerrar sessão por câmera, stats 3 s, totais finais; validação/aceite (relatório por período/baia/limiar, editar contagem manual, aceitar/rejeitar).
15. **Operações por câmera**: CRUD de operações por tipo (catálogo do módulo) com desenho de ROI/linha sobre o vídeo, status ao vivo via socket, exclusão com confirmação por nome.
16. **Cenário por câmera**: hoje quebrado — novo front deve usar `GET /api/v1/cameras/<id>/scenario` e `GET /api/v1/scenarios/operation-types`.
17. **Edge**: admin troca `deployment_mode` dos sites; dashboard integrado (curvas de treino + telemetria ao vivo); página oculta de observabilidade do Jetson (superadmin) com comandos assíncronos (query/snapshot/logtail → poll de comando), thresholds.
18. **Assistente (chat)** SSE com histórico local, escondido no estúdio.
19. **Carregamento (fueling)**: dashboard/baias/eventos com polling 30 s, demo mode superadmin, validação de contagem.
20. **Saúde**: rodapé DB/Redis/câmeras ativas (admin), atalho p/ observability (superadmin).
21. **Relatórios**: hoje inexistente — decidir se o novo front consome `/api/reports/*` ou mantém placeholder.
22. **Transversal**: toasts traduzidos/deduplicados, silenciar erros de polling em background, timeouts (15 s REST / 30 s download), polling com backoff e pausa em aba oculta.
