# Fluxos do front atual — módulos (`apps/frontend/src/modules/**`)

> Fonte: worktree `origin/develop @ 98bff30e`. Tudo lido do código real (front + `services/api`), nada de docs antigas.
> Convenções: `api.get('/v1/admin/x')` ⇒ `GET /api/v1/admin/x` (`services/api.ts:105-107` prefixa `/api`); `qualityService` usa `BASE='/v1/quality'` (`modules/quality/services/qualityService.ts:22`). Caminhos de arquivo abaixo são relativos a `apps/frontend/src/` salvo quando começam com `services/api/`.

---

## Fluxos do front atual — módulos (modules/)

### 0. Fundamentos comuns aos dois módulos

| Tema | Como é feito (arquivo:linha) |
|---|---|
| Autenticação/gating base | `App.tsx:52-64` — sem `token`+`user` no localStorage só renderiza `/forgot-password`, `/reset-password` e `Login` (catch-all). **Toda rota de módulo, inclusive `/tablet/:station` e `/quality/andon/:id`, exige sessão logada no browser** (os comentários "rota pública sem JWT" em `AppRoutes.tsx:32,164` e `QualityLayout.tsx:84` não refletem o gate real). |
| Identidade em memória | `hooks/useAuth.ts:24-27` lê `localStorage.user`; `isSuperAdmin = role==='superadmin'` (L32), `isAdmin` (L33), `hasModule(m)=user.modules.includes(m)` (L34-35), `can(perm)` (L38-42, superadmin sempre true). Nenhum request — tudo do payload do login. |
| Cliente HTTP | `services/api.ts:128-201`: JSON, `Authorization: Bearer`, timeout 15 s, `FormData` sem content-type; 401 fora de `/auth/*` → restaura impersonation/contexto ou `removeToken()` + `/login` (L147-180, single-flight L120). `downloadBlob` (L215-228, 30 s) e `fetchRaw` (L235-242). Erro ≠401 dispara `showErrorToast` (L184-186). |
| Envelope | Front lê sempre `res.data` (`R<T>` em `modules/admin/types/admin.ts:284` está tipado como `{status,data}` — stale, backend devolve `{success,message,data}` em `services/api/app/core/responses.py`; só `.data` é consumido, então funciona). |
| Storage local (chaves) | `token`, `user` (`api.ts:8,26-30`); `impersonation_backup`, `impersonation` (L43-44); `tenant_context_backup`, `tenant_context` (L72-73); sessionStorage `impersonation_expired`, `tenant_context_expired`, `tenant_context_expired_meta` (L45,74,81); `recognition-app` (zustand persist `stores/appStore.ts:23-24`, `selectedModule`); `obs.refreshInterval`/`obs.window` (`modules/admin/pages/observability/AdminObservabilityPage.tsx:53-63`); `quality_dashboard_mode` (`modules/quality/pages/QualityDashboard.tsx:8`). `removeToken()` apaga todas as chaves de impersonation/contexto (L28-38). |
| Sockets (namespaces) | `/admin` — `modules/admin/hooks/useAdminWebSocket.ts:23` (events `worker_status`,`training_approval`,`ticket_created`,`announcement`) — **hook não é usado por nenhuma tela e o backend não emite nada em `/admin`** (`services/api/app/core/socket_bridge.py:181-236` só emite em `/monitor`, `/training`, `/quality`). `/quality` — `modules/quality/hooks/useQualityWebSocket.ts:36` (`quality_inspection`, `quality_cep_alert`; **não usado por nenhuma tela**) e `modules/quality/tablet/useTabletWebSocket.ts:46` (`quality_gate_result`, `quality_station_state`, `quality_piece_identified`; usado pelo TabletKiosk). Base do socket: `VITE_WS_URL || VITE_API_URL || origin` (`useTabletWebSocket.ts:41-44`, `useQualityWebSocket.ts:32-34`). Sem `auth` no handshake do `/quality`; `/admin` manda `auth:{token}` (L24). |
| Env vars | `VITE_API_URL` (api.ts:105; `qualityService.ts:183-184`; `QualityPiecesPage.tsx:12`, `QualityReworkPage.tsx:13`, `QualityReportsPage.tsx:146` — estes três usam fallback `http://localhost:5001`), `VITE_WS_URL` (sockets acima). |

---

### (a) Rotas / telas por módulo

#### Admin — `/admin/*` (`AppRoutes.tsx:120-128` → `AdminRoute` → `AdminLayout`)

Gating da árvore inteira: `components/guards/AdminRoute.tsx:9-17` (`isSuperAdmin` senão `Navigate /`) + novamente em `modules/admin/AdminLayout.tsx:90,126`. Sidebar/rotas em `AdminLayout.tsx:175-228` (nav) e `244-271` (Routes). A cada troca de rota o layout chama `GET /api/v1/admin/dashboard` só para os badges (L98-105).

| Rota | Componente | Gating | Endpoints (método path) | Sockets | Storage |
|---|---|---|---|---|---|
| `/admin` | `pages/AdminDashboard.tsx` | superadmin | `GET /api/v1/admin/dashboard` (poll 30 s — `hooks/useAdminDashboard.ts:5-23`) | — | — |
| `/admin/tenants` | `pages/AdminTenantsPage.tsx` | superadmin | `GET /api/v1/admin/tenants` (L35), `GET /api/v1/admin/modules/catalog` (L43), `GET /api/v1/admin/tenant-context/tenants` (L46 via `services/tenantContext.ts:60`), `POST /api/v1/admin/tenants` (L65), `POST /api/v1/admin/tenant-context/tenants/<id>/assume` (L55 → `tenantContext.ts:84`) | — | grava `tenant_context_backup`, `tenant_context`, troca `token`/`user` (`tenantContext.ts:90-104`) |
| `/admin/tenants/:id` | `pages/AdminTenantDetailPage.tsx` (abas L87-96) | superadmin | `GET /api/v1/admin/tenants/<id>` (L44), `POST …/suspend` (L56), `POST …/reactivate` (L67), `PATCH /api/v1/admin/tenants/<id>` (módulos L418; políticas L495-500), `POST /api/v1/admin/users` (L262), `POST /api/v1/admin/users/<id>/deactivate|reactivate` (L275-277), `POST /api/v1/admin/users/<id>/impersonate` (L247 → `services/impersonation.ts:57`), `GET/PATCH /api/v1/admin/feature-flags/tenant/<id>` (L624,637), `GET /api/v1/admin/tenants/<id>/plan-history` (L653), `GET /api/v1/admin/modules/catalog` (L409), IntegrationsPanel c/ `?tenant_id=` (L196), UserPermissionsDrawer (L374) | — | impersonation: `impersonation_backup`, `impersonation` (`impersonation.ts:63-76`) |
| `/admin/users` | `pages/AdminUsersPage.tsx` + `components/CreateUserWizard.tsx` | superadmin | `GET /api/v1/admin/users?search&role&page` (L26), `POST …/deactivate|reactivate` (L37), `POST …/reset-password` (L45); wizard: `GET /api/v1/admin/tenants` (W:100), `GET /api/v1/admin/tenants/<id>` + `GET /api/admin/roles?tenant_id=` (W:112-113), `POST /api/v1/admin/users` (W:147), `PUT /api/admin/users/<id>/role` (W:157) | — | — |
| `/admin/roles` | `pages/AdminRolesPage.tsx` | superadmin (backend: `admin`) | `GET /api/admin/roles` (L196, **sem tenant_id**), `POST /api/admin/roles` (L73), `PUT /api/admin/roles/<id>` (L71), `DELETE /api/admin/roles/<id>` (L215), `GET /api/v1/admin/permissions/registry` (via `hooks/usePermissions.ts:15-17`, cache de módulo) | — | — |
| `/admin/training-approvals` | `pages/AdminTrainingApprovalsPage.tsx` | superadmin | `GET /api/v1/admin/training-approvals?status&page` (L17), `POST …/<id>/approve` (L28, `prompt()` notas), `POST …/<id>/reject` (L37, `prompt()` motivo) | — | — |
| `/admin/workers` | `pages/AdminWorkersPage.tsx` → `observability/WorkersPanel.tsx` | superadmin | `GET /api/v1/admin/workers` (poll 10 s, WP:36,47), `POST /api/v1/admin/workers/<schema>/restart` (WP:53, ConfirmDialog) | — | — |
| `/admin/plans` | `pages/AdminPlansPage.tsx` | superadmin | `GET /api/v1/admin/plans` + `GET /api/v1/admin/modules-registry` (L90), `POST /api/v1/admin/plans` (L225), `PATCH /api/v1/admin/plans/<id>` (L228) | — | — |
| `/admin/retention` | `pages/AdminRetentionPage.tsx` | superadmin | `GET /api/v1/admin/tenants` (L88), `PATCH /api/v1/admin/tenants/<id>` `{video_retention_days}` (L141) | — | — |
| `/admin/feature-flags` (label do menu: "Permissões", L208) | `pages/AdminFeatureFlagsPage.tsx` | superadmin | `GET /api/v1/admin/feature-flags` (L13), `PATCH /api/v1/admin/feature-flags/<key>` `{value}` (L22) | — | — |
| `/admin/tickets` | `pages/AdminTicketsPage.tsx` + `components/TicketRow.tsx` | superadmin | `GET /api/v1/admin/tickets?status&priority&page` (L18). **Clique na linha navega para `/admin/tickets/:id` (TicketRow:14) — rota inexistente → catch-all `/admin`** | — | — |
| `/admin/audit-log` | `pages/AdminAuditLogPage.tsx` | superadmin | `GET /api/v1/admin/audit-log?action&date_from&date_to&page` (L21), `GET /api/v1/admin/audit-log/export?action` via `downloadBlob` → CSV (L37-41) | — | — |
| `/admin/announcements` | `pages/AdminAnnouncementsPage.tsx` | superadmin | `GET /api/v1/admin/announcements` (L22), `POST` (L33), `DELETE …/<id>` (L42, `confirm()`) | — | — |
| `/admin/observability` (`?tab=overview|infra|edge|workers|streams`) e alias `/admin/health` (L259) | `pages/observability/AdminObservabilityPage.tsx` + panels | superadmin | `GET /api/v1/admin/observability/summary` (L278, `usePolling`), `…/timeseries?scope&metric&window&tenant_id&queue` (TimeseriesChart:60), `…/edge-fleet` + `GET /api/v1/edge/overview` (EdgeFleetPanel:391-393; fallback `GET /api/v1/edge/sites/health` L401; drill-down `GET /api/v1/edge/sites/<id>/heartbeats` e `…/heartbeat-summary` L425-426), `…/streams` (StreamsPanel:82), `POST …/observability/collect` (L308), workers idem acima | — | `obs.refreshInterval` (0=pausado/10s/30s/1m/5m), `obs.window` (1h/6h/24h/7d) |
| `/admin/settings` | `pages/AdminSettingsPage.tsx` | superadmin | `GET /api/v1/admin/permissions/registry` (usePermissions) → matriz read-only; "Recognition 2.0" hardcoded (L32) | — | — |
| `/admin/integrations` (`?type=r2|vast_ai|generic_gpu|notification|byo_db`) | `pages/AdminIntegrationsPage.tsx` | superadmin (client L118-121; backend `_require_superadmin`) | `GET /api/v1/admin/integrations/` (L139), `PUT /api/v1/admin/integrations/<type>` `{label,config,secret?}` (L214), `POST …/<type>/test` (L230) | — | — |
| `/admin/versions` | `pages/AdminVersionsPage.tsx` | superadmin | `GET /api/v1/admin/versions` (L28), `POST /api/v1/admin/versions` (L56), `POST …/<id>/rollback` `{confirm:true}` (L43, `window.confirm`) | — | — |
| `/admin/changelog` | `pages/AdminChangelogPage.tsx` | superadmin | `GET /api/v1/admin/changelog?category&importance&affected_area&page&per_page=20` (L49), `POST /api/v1/admin/changelog` (L74) | — | — |
| `/admin/branding/tenants` | `pages/AdminBrandingTenantsPage.tsx` | superadmin | `GET /api/v1/admin/tenants` + N× `GET /api/v1/admin/tenants/<id>/branding` (L23-35, allSettled) | — | — |
| `/admin/branding/tenants/:id` | `pages/AdminBrandingEditorPage.tsx` (+`TenantBrandingEditor`, `SurfacesEditorSection`, `BrandingPreview`) | superadmin | `GET /api/v1/admin/tenants/<id>` + `GET …/branding` (L95-96), `PUT …/branding` (L107 salvar; L119 reset p/ default), `POST …/branding/logo` FormData `{file,kind:'logo'|'favicon'}` (L132,149) | — | preview injeta CSS vars em `#recognition-tenant-theme` (L162-179) |
| `/admin/branding/default`, `/admin/branding/sandbox` | `AdminBrandingDefaultPage.tsx`, `AdminBrandingSandboxPage.tsx` | superadmin | nenhum (tokens estáticos / sandbox local L20-30) | — | — |
| `/admin/demo-videos` | `pages/DemoVideosPage.tsx` | superadmin (L40-43) | `GET /api/admin/demo-videos` (L59), `POST /api/admin/demo-videos/upload` FormData `video` (L91-97), `DELETE /api/admin/demo-videos/<id>` (L77) | — | — |
| `/admin/test-console` | `pages/AdminTestConsolePage.tsx` | superadmin | `GET /api/v1/admin/test-console/status` (L100; poll 3 s enquanto `running` L148-161), `POST …/start` (L175), `POST …/stop` (L196), `GET /api/training/models` (L110 → `adminService.ts:489`), `GET /api/training/scenarios/<model_id>/config` (L210), `GET /api/v1/admin/integrations` (L122) | — | — |
| `/admin/inventory` | `pages/AdminInventoryPage.tsx` | superadmin | `GET /api/v1/admin/inventory?tenant_id&brand&probe_status` (L154), `POST /api/v1/admin/cameras/<id>/probe` (L187), `POST /api/v1/admin/cameras/probe-batch` `{camera_ids}` (L226), `POST /api/v1/admin/cameras/import` `{cameras:[…]}` (L281, CSV parseado no client L255-280) | — | — |
| **sem rota** | `pages/DemoEventsPage.tsx` (não importado em `AdminLayout.tsx` nem `AppRoutes.tsx`) | guard L75-90 | `GET /api/v1/admin/tenants` (L100), `GET /api/v1/admin/demo-events?tenant_id` (L112), `POST …/demo-events/seed` `{tenant_id,module_code,count}` (L131), `DELETE …/demo-events?tenant_id&module_code` (L148) | — | — |
| fora de `modules/` mas sob `AdminRoute` | `/design-system` (`AppRoutes.tsx:129-136`), `/monitoring` (`EdgeMonitoringGate` L48-56) | superadmin | — | — | — |

Métodos de `adminService.ts` **sem consumidor** no front (definidos, nunca chamados): `getTenantOverview`(L96), `getUser`(125), `forcePasswordReset`(145), `getUserSessions`(153), `getPermissionMatrix`(160), `getMyPermissions`(186), `getTrainingApproval`(202), `getWorkerDetail`(219), `getWorkerMetrics`(227), `getPlan`(237), `getPlanTenants`(250), `getTicket`(284), `replyTicket`(289), `updateTicket`(295), `getTicketStats`(298), `updateAnnouncement`(333), `getPlatformHealth`(341), `getVersion`(384), `getUserCustomRole`(434), `get/setCameraRetention`(443-449), `get/setTenantRetention`(451-457).

#### Qualidade — `/quality/*` (`AppRoutes.tsx:151-158` → `QualityLayout`)

Gating: `modules/quality/QualityLayout.tsx:43-54` — `hasModule('quality')` senão `navigate('/modules')`; `setSelectedModule('quality')` (L48). Submenu L31-40; rotas L77-92; index → `cameras`. Backend: todos os handlers chamam `_require_jwt()` (`services/api/app/api/v1/quality/routes.py:47-55`), que só extrai `tenant_schema`/`modules` do JWT (o helper `_require_quality_module` L63-65 existe; uso por rota não verificado aqui).

| Rota | Componente | Gating | Endpoints | Sockets | Storage |
|---|---|---|---|---|---|
| `/quality/cameras` (default) | `pages/QualityCamerasPage.tsx` | módulo `quality` | `GET /api/v1/quality/cameras` + `GET /api/v1/quality/cameras/available` (L20-23), `POST …/cameras/<id>/assign` (L37), `DELETE …/cameras/<id>/unassign` (L45), `PATCH …/cameras/<id>/config` `{production_order,product_type}` (L64) | — | — |
| `/quality/dashboard` | `pages/QualityDashboard.tsx` (pro) / `QualityDashboardDemo.tsx` (mock) | módulo | `GET /api/v1/quality/dashboard/summary` (poll 15 s) e `GET /api/v1/quality/dashboard/stations` (poll 5 s), backoff ×2 até 60 s (`hooks/useQualityDashboard.ts:5-7,33-71`) | — | `quality_dashboard_mode` = `pro|demo` (L8-25) |
| `/quality/inspections` | `pages/QualityInspectionsPage.tsx` | módulo | **nenhum — lista 100 % mock** (`makeInspections()` L28-86, 200 itens gerados; filtros/paginação/feedback só em memória; `?camera_id` lido da URL L99-100). Clique → `/quality/inspections/<id>` (L286) | — | — |
| `/quality/inspections/:id` | `pages/QualityInspectionDetail.tsx` | módulo | `GET /api/v1/quality/inspections/<id>` + `GET /api/v1/quality/classes` (L33-35), `GET …/inspections/<id>/evidence-url` (`hooks/useClipPlayer.ts:69`, renova `expires_in-120s`), `GET …/clip-url` (L27, idem), `PATCH …/inspections/<id>/feedback` `{status,notes}` (L49), `POST …/inspections/<id>/prepare-annotation` (L59) → navega p/ `…/annotate` | — | — |
| `/quality/inspections/:inspectionId/annotate` | `pages/QualityAnnotationWorkspace.tsx` + `hooks/useQualityAnnotation.ts` + `components/AnnotationCanvas.tsx` | módulo | `GET /api/v1/quality/classes` (L38), `GET …/inspections/<id>/annotation-frames` (hook L61), `GET …/annotation-frames/<frameId>/url` (L46), `PUT …/annotation-frames/<frameId>/annotations` `{annotations:[bbox normalizada]}` (hook L84 auto-save ao trocar frame; L127 "pular" = salva `[]`), `GET …/inspections/<id>/annotation-progress` (L54, a cada troca de frame), `POST /api/v1/quality/training/jobs` (L62 → `/quality/training`) | — | atalhos teclado A/←, D/→, S, Del/Backspace, Esc (hook L239-251) |
| `/quality/training` | `pages/TrainingPage.tsx` (**fora de modules/**, compartilhada com EPI; `QualityLayout.tsx:20,83`) | módulo | endpoints do treino genérico (`/api/training/*`) — fora do escopo deste doc. `modules/quality/pages/QualityTrainingPage.tsx` (jobs 5 s + ativar modelo) **não é roteada** | — | — |
| `/quality/andon/:cameraId` | `pages/QualityAndonDisplay.tsx` | módulo + sessão (apesar do comentário "sem JWT") | `GET /api/v1/quality/andon/<cameraId>` (L21; poll 15 s L38-42). Backend: sem JWT, só `verify_andon_access(remote_addr)` (routes.py:703-710) | — | — |
| `/quality/pieces` | `pages/QualityPiecesPage.tsx` | módulo | `GET /api/v1/quality/gate/pieces?page&per_page&status&date&work_order` (L84-90), `GET …/gate/pieces/<id>` (L114), `<img src="${VITE_API_URL}/api/v1/quality/gate/photos/<path>">` (L378) | — | — |
| `/quality/rework` | `pages/QualityReworkPage.tsx` | módulo | `GET /api/v1/quality/gate/reworks?page&per_page&validation_type&date&operator_id` + `GET …/gate/stats/rework` (L78-79), fotos `…/gate/photos/<path>` (L428,452) | — | — |
| `/quality/reports` | `pages/QualityReportsPage.tsx` | módulo | `GET …/gate/pieces?status=approved&per_page=200&date_from&date_to&work_order&wiser_exported` (L73-81), `POST …/gate/pieces/<id>/export-wiser` (L99), `POST …/gate/export-wiser/batch` `{piece_ids}` (L126), `<a href="${VITE_API_URL}/api/v1/quality/gate/pieces/export?…&token=<JWT>" download>` (L136-150) | — | — |
| `/quality/config` | `pages/QualityConfigPage.tsx` | módulo | `GET …/gate/stations` (L76), `PATCH …/gate/config` (L93), `PATCH …/gate/stations/<code>` (L121), `POST …/gate/stations` `{name,station_code,tower_controller_type,is_active}` (L144) | — | — |
| `/tablet/:station` (`AppRoutes.tsx:165-172`, **fora do QualityLayout**, sem checagem de módulo) | `tablet/TabletKiosk.tsx` + telas `TabletIdle/Identified/Validating/ResultOK/ResultNOK/Transition/Approved` | sessão logada (App.tsx) | `POST /api/v1/quality/gate/pieces/<id>/inspect` `{station}` (TabletIdentified:25), `POST …/gate/reworks` `{piece_id,validation_type,station}` (TabletResultNOK:30), `POST …/gate/pieces/<id>/false-positive` `{inspection_id: result.camera_id}` (NOK:48), `POST …/gate/pieces/<id>/release-to-bench-b` (TabletTransition:24), foto `…/gate/photos/<path>` (NOK:59-61) | `/quality`: `quality_gate_result`, `quality_station_state` (filtra `station_code`), `quality_piece_identified` (`useTabletWebSocket.ts:70-88`) | — |

Métodos de `qualityService.ts` **sem consumidor vivo**: `getDefectCategories`(30), `toggleSetupMode`(53), `getInspections`(58), `getSummary`(96, só em `hooks/useShiftMetrics.ts` morto), `getTrainingJobs`/`getTrainingJob`/`activateModel` (133-140, só em `QualityTrainingPage` não roteada), `getReferenceSnapshots`(142), `getCepData`(149), `getShiftReport`/`getShiftReportPdfUrl`(159-187). Componentes mortos: `CepChart`, `DefectPareto`, `ShiftMetricsBar`, `useShiftMetrics`, `useQualityWebSocket`, `QualityTrainingPage`.

---

### (b) Fluxos em passos

#### B1. Criação de tenant + senha temporária
1. `AdminTenantsPage` abre modal (L160-205); slug normalizado `lower + [^a-z0-9-]→'-'` (L171); módulos vêm de `GET /api/v1/admin/modules/catalog` com fallback estático (L13-15,43).
2. `POST /api/v1/admin/tenants` `{name,slug,plan,modules_enabled}` (`adminService.ts:79-83`). Backend (`services/api/app/api/v1/admin/routes.py:300-362`): valida slug, cria tenant + schema (`create_tenant_schema(slug)`), cria admin `admin@<slug>.epimonitor.local` com `temp_password=token_urlsafe(12)`, retorna `{tenant,admin_email,temp_password}`.
3. Front mostra `alert()` com admin_email + temp_password (L66) — **exibida uma única vez** — e recarrega lista.

#### B2. Criação de usuário (wizard 3 passos) e reset de senha
1. `CreateUserWizard` (abre em `/admin/users`): passo Dados — email regex, role de sistema, tenant via select com busca (`GET /api/v1/admin/tenants`, W:100).
2. Passo Acesso — `GET /api/v1/admin/tenants/<id>` + `GET /api/admin/roles?tenant_id=<id>` (W:108-119); role customizada opcional; `access_expires_at` opcional.
3. `POST /api/v1/admin/users` `{email,role,tenant_id,access_expires_at?}` → `{user,temp_password,first_access_token|null}` (backend L818-900: token de 1º acesso no Redis TTL 48 h). Se role customizada: `PUT /api/admin/users/<id>/role` best-effort (W:155-164, toast de aviso em falha).
4. Passo Credenciais — senha/token mascarados com revelar/copiar (W:166-190).
5. Reset: `POST /api/v1/admin/users/<id>/reset-password` → modal com `temp_password` + copiar (AdminUsersPage L42-58,134-157). Variante simples na aba Usuários do tenant: `POST /api/v1/admin/users` + `alert()` (TenantDetail L259-270).

#### B3. Impersonation "ver como" (WS6)
1. Aba Usuários do tenant → botão "Ver como" só p/ `role!=='superadmin' && is_active` (TenantDetail L348-357) → `ConfirmDialog` (L381-390).
2. `services/impersonation.ts:56-78`: `POST /api/v1/admin/users/<id>/impersonate` → `{token,user,expires_in_minutes}` (backend TTL 30 min, `impersonation_routes.py:52`, nega aninhamento/alvo inativo, audita). Salva `impersonation_backup={token,user}` e `impersonation={target_name,target_email,tenant_id,started_at}`; troca `token`/`user`; `window.location.href='/'`.
3. Banner global (`components/ImpersonationBanner.tsx`, montado em `components/layout/GlobalBanners.tsx:51`) mostra alvo; "Sair" → `POST /api/v1/impersonation/stop` best-effort + `restoreImpersonationBackup('/admin/tenants')` (`impersonation.ts:84-92`, `api.ts:51-65`).
4. Expiração: qualquer 401 com backup presente → `sessionStorage.impersonation_expired=1` + restaura backup + redirect `/admin/tenants` (`api.ts:158-163`); banner lê a flag pós-reload (ImpersonationBanner L27-29).

#### B4. Contexto de tenant assumido ("assumir contexto") — superadmin
1. `AdminTenantsPage`: botão só p/ tenants em `GET /api/v1/admin/tenant-context/tenants` (L45-49; endpoint 404 p/ não-superadmin).
2. `assumeTenantContext` (`tenantContext.ts:83-105`): `POST /api/v1/admin/tenant-context/tenants/<id>/assume` → `{token,tenant,user,expires_in_minutes}` (TTL `TENANT_CONTEXT_TTL_MINUTES`=30, `core/tenant_context.py:69`). Backup em `tenant_context_backup`, meta em `tenant_context` `{tenant_id,tenant_name,tenant_slug,started_at}`; troca `token`/`user`; reload `/`.
3. `TenantContextBanner` (GlobalBanners:52) agenda renovação proativa: decodifica `exp` do JWT (L137-149), `POST /api/v1/admin/tenant-context/renew` 5 min antes (L168-173,200-230), retry 30 s em falha transitória, catch-up em `visibilitychange` (L232-240). "Sair" = só restauração local, sem endpoint (L112-115).
4. Expiração (401): guarda meta em `sessionStorage.tenant_context_expired_meta`, flag `tenant_context_expired`, restaura backup → `/admin/tenants` (`api.ts:169-176`); banner oferece "Reassumir" (`TenantContextBanner.tsx:61-86`). Impersonation e contexto são mutuamente exclusivos (backend recusa aninhar — `api.ts:67-71`).

#### B5. Permissões, roles customizadas e overrides (WS7)
- Registry canônico: `GET /api/v1/admin/permissions/registry` → `{permissions:[{key,label,description,group,default_roles}],roles}`, cache em módulo (`hooks/usePermissions.ts:6-20`); alimenta `AdminSettingsPage` (matriz), `AdminRolesPage` (grupos de checkboxes L25-40) e `UserPermissionsDrawer`.
- Roles customizadas (`AdminRolesPage`): `GET /api/admin/roles` (L196, sem `tenant_id` → backend `_resolve_tenant_id` cai no tenant do JWT, `roles/routes.py:39-53` — para superadmin sem contexto assumido: indeterminado qual tenant), `POST/PUT/DELETE /api/admin/roles[/<id>]` com `{name,permissions:{key:bool}}`.
- Drawer por usuário (`UserPermissionsDrawer.tsx`): carrega `GET /api/v1/admin/users/<id>/permissions` + `GET /api/admin/roles?tenant_id` (L76-78); salvar = `PATCH /api/v1/admin/users/<id>` `{role}` (L130) + `PUT /api/admin/users/<id>/role` `{custom_role_id}` (L134) + `PUT /api/v1/admin/users/<id>/permissions` `{overrides:[{permission_key,allow}],remove:[…]}` (L152); aviso "vale no próximo login" + `DELETE /api/v1/admin/users/<id>/sessions` (L169).

#### B6. Planos, módulos do tenant, políticas, retenção, flags
- Planos: `GET /api/v1/admin/plans` + `GET /api/v1/admin/modules-registry` (AdminPlansPage L90); modal cria/edita com payload `{name,modules_allowed,max_cameras,max_users,video_retention_days,api_rate_per_minute,requires_training_approval,price_per_camera,module_features,active}` (+`slug` só na criação, L212-229); desativar plano com tenants → ConfirmDialog (L495-505).
- Módulos do tenant: toggle → `PATCH /api/v1/admin/tenants/<id>` `{modules_enabled}` (TenantDetail L412-423).
- Políticas de plataforma (aba Configurações): `PATCH /api/v1/admin/tenants/<id>` `{max_seats,single_session,rate_limit_per_minute,default_retention_days}` (L495-500); backend aceita também `plan,active,requires_training_approval,internal_notes,mrr_per_camera,contract_cameras,max_cameras,video_retention_days` (`admin/routes.py:466-473`).
- Retenção de vídeo por tenant (`AdminRetentionPage`): tiers 1/7/30/90 → `PATCH /api/v1/admin/tenants/<id>` `{video_retention_days}` (L141). Os endpoints de retenção por câmera (`/api/cameras/<id>/retention`, `/api/cameras/tenant/retention`) estão no service mas sem tela.
- Flags globais: `GET /api/v1/admin/feature-flags` + `PATCH …/<flag_key>` `{value}`; por tenant: `GET/PATCH /api/v1/admin/feature-flags/tenant/<id>` `{key,value}` (TenantDetail L619-646).

#### B7. Tickets, anúncios, aprovações de treino, workers, auditoria
- Tickets: só listagem com filtros `status/priority/page` (20/pág) — detalhe/reply/stats sem tela (ver C).
- Anúncios: CRUD parcial (`list/create/delete`); `update` sem tela. Lado cliente (`GET /api/v1/announcements`, `POST …/<id>/read`) **não tem consumidor** no front; `components/AnnouncementBanner.tsx` não é usado.
- Aprovações de treino: lista + aprovar/rejeitar com `prompt()` nativo (L26-39).
- Workers: `WorkersPanel` poll 10 s + restart com ConfirmDialog/Toast.
- Auditoria: lista paginada + export CSV (blob → `<a download>` L37-41; backend `Content-Disposition` L2262-2320).

#### B8. Branding (white-label)
1. `/admin/branding/tenants`: lista tenants e faz 1 `GET …/branding` por tenant (L23-35) → cards c/ preview.
2. Editor: carrega tenant + branding (L95-96), converte para `TenantThemeOverrides` (`brandingToOverrides` L33-54); salva formato FLAT `{product_name,color_primary,color_secondary,logo_url,favicon_url,color_bg_*,color_text_*,color_border}` via `PUT` (L57-72,107); reset = `PUT` com defaults (L119); upload logo/favicon `POST …/branding/logo` multipart `{file,kind}` (L132,149; backend valida MIME, grava `branding/<tenant>/<kind><ext>` no storage e persiste `<kind>_url`, `branding_routes.py:147-200`); "Preview" injeta CSS vars no `<style id="recognition-tenant-theme">` (L162-179). Consumo do branding pelo cliente é fora de modules (`theme/ThemeProvider.tsx:7`).

#### B9. Integrações (task-056/058)
- Página global e painel por tenant usam o mesmo contrato: `GET /api/v1/admin/integrations/[?tenant_id=]`, `PUT …/<type>` `{label,config,secret?}` (secret vazio = manter), `POST …/<type>/test` → `{ok,error}`, `DELETE …/<type>` (só no painel, com ConfirmDialog). Display do segredo `••••last4`, nunca plaintext.
- Tipos: `r2, vast_ai, generic_gpu, notification, byo_db` (AdminIntegrationsPage L45-99). **Divergência**: campos de config do `r2` na página (`endpoint,bucket`) ≠ painel (`account_id,access_key_id,bucket,endpoint` — IntegrationsPanel L47-56).
- Backend: superadmin p/ tudo (+`?tenant_id=`), admin de tenant só `byo_db` do próprio tenant (`integration_routes.py:83-117`); listagem é superadmin-only (L126-131).

#### B10. Versões / changelog / introspecção
- Versões: lista (expansível), criar `{version,version_type,title,description}`, rollback `{confirm:true}` com `window.confirm` (L36-50).
- Changelog: lista com filtros aplicados por botão (L62-67) + criar entrada.
- Introspecção: `GET /api/v1/admin/introspection` existe no backend (`admin`), **sem tela** no front.

#### B11. Console de teste (task-056/WS5)
1. Mount: `GET …/test-console/status`, `GET /api/training/models` (lista do tenant do JWT; `.catch(()=>[])`), `GET /api/v1/admin/integrations` (L131-135).
2. Config: câmeras 1–28, modelo (`pretrained` ou id real), FPS padrão 1–30 e opcional por câmera, cenário (classes EPI, limiar, descrição); "Carregar cenário do modelo" → `GET /api/training/scenarios/<id>/config` (L207-237).
3. `POST …/start` `{camera_count,model_id,scenario_config,default_fps,camera_fps?}` (L175-184) → backend valida e tenta harness, senão modo `stub` (`routes_test_console.py:147-195`); status retorna `{status,session_id,config,metrics,log_lines[-50:],vast_ai_configured}` (L81-103). Poll 3 s enquanto `running` (L148-161); `POST …/stop` (L196). Endpoints `harness/*`, `evidence`, `seed`, `models` (`test_console_routes.py`, `jwt+admin`) **não são usados pelo front**.

#### B12. Observabilidade
- Seletor global de intervalo (0/10s/30s/1m/5m, localStorage) e janela (1h/6h/24h/7d); `refreshMs=0` ⇒ nenhum request automático (`usePolling(..., {enabled: refreshMs>0})` em todos os panels). "Coletar agora" → `POST …/observability/collect` → toast `points_recorded` (L304-316). Frota edge agrupa por tenant; drill-down por site abre heartbeats + summary (EdgeFleetPanel L420-437). Streams: 1 request agregada (StreamsPanel L82). Infra: derivado do `summary` (DB/Redis/R2/filas) + TimeseriesChart por fila.

#### B13. Inventário de câmeras (onboarding em lote)
1. `GET /api/v1/admin/inventory?tenant_id&brand&probe_status` (L144-161) → tabela com seleção.
2. Probe individual `POST …/cameras/<id>/probe` (L184-207) e em lote `POST …/cameras/probe-batch` `{camera_ids}` (L219-250; backend max 5 simultâneos).
3. Importar CSV: parse client-side (`name,brand,ip,port,username,module,tenant_id` L62-131,255-280) → `POST …/cameras/import` `{cameras:[{name,brand,ip,port,username,module,tenant_id,manufacturer}]}` → `{created,errors[{row,reason}]}` (207 se houver erros, backend L2720).

#### B14. Demo videos / demo events
- Vídeos demo (`/admin/demo-videos`): lista, upload MP4 multipart `video` (valida `file.type.includes('mp4')`), delete com `confirm()`.
- Eventos demo (`DemoEventsPage`, **sem rota**): seed/remover por tenant+módulo.

#### B15. Qualidade — câmeras do módulo
Atribuir/remover câmera ao módulo e editar `production_order`/`product_type` (PATCH config). `toggle-setup-mode`, `model_quality_id` e `reference-snapshots` não têm UI.

#### B16. Qualidade — dashboard pro/demo
Modo persistido em `quality_dashboard_mode`; pro = dois pollings independentes (15 s summary / 5 s stations) com backoff; demo = mock 100 % local com feed simulado (`QualityDashboardDemo.tsx:72-83`).

#### B17. Qualidade — inspeções → detalhe → anotação → treino
1. Lista: **mock** (sem API). 2. Detalhe: `GET inspection` + classes; URLs assinadas de evidência/clipe renovadas automaticamente (`expires_in-120s`); feedback `confirmed|rejected` + notas; "Anotar frames" → `POST prepare-annotation` → `/annotate`. 3. Workspace: frames + URL por frame + canvas bbox normalizada, auto-save ao trocar frame (PUT), pular = PUT `[]`, progresso a cada troca; "Criar job de treino" → `POST /api/v1/quality/training/jobs` → `/quality/training` (que renderiza a `TrainingPage` genérica). 4. Ativação de modelo de qualidade (`POST …/training/models/<id>/activate {camera_id}`) só na `QualityTrainingPage` não roteada.

#### B18. Qualidade — Andon e CEP
- Andon: poll 15 s `GET /api/v1/quality/andon/<cameraId>`; flash vermelho quando `last_result` vira `nok` (L18-35). Backend valida IP interno, ignora JWT.
- CEP: `GET /api/v1/quality/cep/<cameraId>` e `CepChart` existem, **sem tela** que os use.

#### B19. Qualidade — Quality Gate (RVB): peças, retrabalhos, relatórios, config
- Peças: lista paginada (filtros `status,date,work_order`) + drill-down `GET …/pieces/<id>` com histórico/validações/retrabalhos e foto. Backend só aplica `status` e `work_order`; `total` = tamanho da página (`quality/routes.py:1570-1580`), logo a paginação do front (`totalPages`) é indeterminada/errada.
- Retrabalhos: lista (`validation_type,date,operator_id` — backend só `piece_id,validation_type` L1735-1738) + `stats/rework`; modal foto antes/depois. `PATCH …/reworks/<id>/complete` sem tela.
- Relatórios: peças aprovadas agrupadas por OP, export Wiser individual/lote, CSV (ver C).
- Config: lista estações; cria estação `{name,station_code,tower_controller_type,is_active}` (backend persiste só `station_code,name,description,camera_ids`, L1845-1853); edita estação (PATCH — ver C); config global (PATCH — ver C; seção nunca renderiza porque `editConfig` começa `null` e não há GET, `QualityConfigPage.tsx:56,404`).

#### B20. Qualidade — Tablet kiosk (bancadas A/B)
1. `/tablet/:station` (`bench_a|bench-a|bench_b`, hífen→underscore L40-42). Conecta socket `/quality`; view derivada de `quality_station_state.current_piece.status` (L51-74: `idle/identified/validating_v*/waiting_bench_b(só bench_a)/rework_v*/approved/rejected`), `quality_piece_identified` força `identified` (L88-91), `quality_gate_result` força `ok|nok` (L77-85).
2. Identified → "Iniciar inspeção" `POST …/pieces/<id>/inspect {station}`. NOK → "Corrigir" `POST …/reworks {piece_id,validation_type,station}` (volta p/ validating) ou "Falso positivo" `POST …/pieces/<id>/false-positive {inspection_id: result.camera_id}`. OK → auto-avança 3 s (`TabletResultOK.tsx:19-22`). Transition (bench_a) → `POST …/release-to-bench-b`. Approved = tela final.
3. **Quebra**: worker publica `quality:gate_result:<schema>:<piece>` e `quality:inspection_result:<schema>` (`infrastructure/queue/tasks/quality_inference.py:660-668`); o bridge não tem ramo para `quality:gate_result:*` e emite `quality_inspection_result` (`socket_bridge.py:215-217`), evento que o tablet **não escuta** — `quality_gate_result` nunca chega; a tela OK nunca aparece e a NOK aparece só via `station_state` (status `rework_v*`) com `result=null` (sem foto/detecções).

---

### (c) Fluxos SEM endpoint claro / quebrados

Conferido contra `docs/migration/inventory/consumers.md` (seção "SEM regra") + `consumers.json.frontend_unmatched` + `endpoints.json`.

| # | Chamada do front (arquivo:linha) | Método path resolvido | Status no backend | Tela impactada / efeito |
|---|---|---|---|---|
| 1 | `modules/quality/pages/QualityConfigPage.tsx:93` | `PATCH /api/v1/quality/gate/config` | 405 — não existe rota `gate/config` em nenhum método | `/quality/config` — seção "configurações globais" (OCR/thresholds) nunca renderiza (estado inicia `null`, sem GET) e salvar falharia. |
| 2 | `QualityConfigPage.tsx:121` | `PATCH /api/v1/quality/gate/stations/<code>` | 405 — backend é `PUT` (`quality/routes.py:1861`) e só persiste `name,description,camera_ids,current_piece_id` | `/quality/config` — editar estação falha; `tower_controller_type`/`is_active` nem seriam gravados. |
| 3 | `QualityPiecesPage.tsx:378`, `QualityReworkPage.tsx:428,452`, `tablet/TabletResultNOK.tsx:61` | `GET /api/v1/quality/gate/photos/<path>` | 404 — rota inexistente; `<img>` sem Authorization | Fotos de defeito/retrabalho nunca carregam em Peças, Retrabalho e Tablet NOK. |
| 4 | `QualityReportsPage.tsx:99` | `POST /api/v1/quality/gate/pieces/<id>/export-wiser` | 405 (casa em `GET …/pieces/<piece_id>`); não há export Wiser na API (só `retry_failed_wiser_exports` Celery, `quality_inference.py:680`) | `/quality/reports` — exportação individual sempre erro. |
| 5 | `QualityReportsPage.tsx:126` | `POST /api/v1/quality/gate/export-wiser/batch` | 405/404 | `/quality/reports` — lote sempre erro. |
| 6 | `QualityReportsPage.tsx:136-150` (template, não pego pelo matcher) | `GET /api/v1/quality/gate/pieces/export?…&token=<JWT>` | casa em `GET …/gate/pieces/<piece_id>` com `piece_id='export'` → 404/erro; **JWT na query string** | "Baixar CSV" não funciona e vaza token em URL/histórico. |
| 7 | `QualityReportsPage.tsx:73-81`, `QualityPiecesPage.tsx:84-87`, `QualityReworkPage.tsx:72-74` | filtros `date,date_from,date_to,wiser_exported,operator_id` | backend ignora (só `status,work_order` / `piece_id,validation_type`); `total=len(página)` | Filtros silenciosamente sem efeito; paginação/"N peças" indeterminados. |
| 8 | `tablet/useTabletWebSocket.ts:70` | socket `/quality` evento `quality_gate_result` | nunca emitido (`socket_bridge.py` sem ramo `quality:gate_result:*`; emite `quality_inspection_result`) | Tablet: tela OK nunca aparece; NOK sem foto/detecções. |
| 9 | `modules/admin/components/TicketRow.tsx:14` | navegação `/admin/tickets/:id` | rota não existe em `AdminLayout.tsx:244-271` → redirect `/admin` | Detalhe/resposta de ticket inacessível apesar de `GET/PATCH …/tickets/<id>`, `POST …/reply`, `GET …/tickets/stats` existirem. |
| 10 | `modules/admin/hooks/useAdminWebSocket.ts:23` | socket `/admin` | nenhum emit no backend | Hook morto (sem consumidor); sem impacto visível. |
| 11 | `modules/quality/pages/QualityInspectionsPage.tsx` | — (mock) | `GET /api/v1/quality/inspections` existe (`routes.py:348`) mas não é chamado | Lista de inspeções é fictícia em produção; feedback da lista não persiste. |
| 12 | `modules/admin/pages/AdminTestConsolePage.tsx:110` | `GET /api/training/models` | `jwt` — usa `tenant_schema` do token; superadmin fora de contexto assumido: indeterminado (ADR-0017 — sem fallback de tenant → provável erro, engolido por `.catch(()=>[])`) | Dropdown de modelos vazio a menos que esteja em contexto de tenant. |
| 13 | `modules/admin/pages/AdminRolesPage.tsx:196` | `GET /api/admin/roles` sem `tenant_id` | superadmin → tenant do JWT (`roles/routes.py:47-53`) | Qual tenant é listado p/ superadmin sem contexto: indeterminado (depende do claim `tenant_id` do superadmin). |
| 14 | `hooks/useScenario.ts:25` (fora de modules — referência cruzada do consumers.md) | `GET /api/cameras/<id>/scenario` | 404 (backend só tem `/api/v1/…` ou outro prefixo; ver domínio cameras) | Não afeta telas de `modules/`. |
| 15 | `AppRoutes.tsx:165-172` + `App.tsx:54-64` | rota `/tablet/:station` e `/quality/andon/:id` | exigem browser logado; gate routes exigem JWT (`_require_jwt`) | Contradiz o desenho "sem JWT, por IP": o kiosk/andon precisam de uma sessão logada no dispositivo. |
| 16 | `modules/admin/pages/DemoEventsPage.tsx` | endpoints `demo-events` existem | página não roteada | Funcionalidade inacessível. |
| 17 | `modules/admin/pages/AdminIntegrationsPage.tsx:45-56` vs `components/IntegrationsPanel.tsx:47-56` | `PUT /api/v1/admin/integrations/r2` | mesmo endpoint, `config` com chaves diferentes | Salvar R2 pela página global pode sobrescrever config parcial (sem `account_id/access_key_id`). |

Endpoints do domínio **sem tela** (SEM-CONSUMIDOR em `classification.json`, relevantes ao novo front): `GET /api/v1/admin/introspection`, `GET /api/v1/admin/health/metrics`, `GET/PUT /api/v1/admin/software-channels[/<channel>]`, `test-console/{harness/*,evidence,seed,models}`, `GET /api/v1/announcements` + `POST …/<id>/read`, `POST /api/v1/quality/gate/pieces`, `…/pieces/<id>/identify`, `…/pieces/<id>/result`, `PATCH …/reworks/<id>/complete`, `GET …/gate/stations/<code>`, `GET …/gate/stats/overview`, `POST …/inspections/<id>/create-training-job`, `GET …/reports/shift/pdf`, `GET …/training/jobs/<id>/progress`, `POST /api/v1/quality/demo/seed`; e os legados de branding `PUT /api/v1/admin/branding`, `POST /api/v1/admin/branding/logo`, `GET /api/v1/admin/branding/tenant[s]`.

---

### (d) O que o novo front precisa replicar (produto, pt-BR)

**Transversal**
- Gate de rota por papel (`superadmin` → `/admin/*`; redirect raiz superadmin→`/admin`, demais→`/modules`) e por módulo habilitado do tenant (`quality`), ambos derivados do payload do login (`role`, `modules`, `permissions`) — sem chamada extra.
- Sessão: token em storage, 401 → logout; **exceto** quando há "ver como"/"contexto assumido" ativo: restaurar sessão original, sinalizar expiração e oferecer "Reassumir".
- Dois modos temporários de superadmin, mutuamente exclusivos, com banner global persistente: **Ver como usuário** (30 min, auditado, `POST …/impersonate` + `POST /api/v1/impersonation/stop`) e **Assumir contexto de tenant** (30 min, renovação proativa 5 min antes via `/renew`, retry 30 s, catch-up ao voltar à aba).
- Envelope `{success,message,data}`; erros com toast; downloads autenticados (CSV) via blob, nunca token em query string.

**Admin (superadmin)**
- Dashboard de plataforma com métricas (tenants ativos, usuários, câmeras online, alertas 24 h, aprovações pendentes, tickets abertos, MRR) + workers online/fallback/offline + eventos críticos recentes, atualizado a 30 s; badges de aprovações/tickets no menu.
- Tenants: listar/buscar, criar (nome, slug, plano, módulos do catálogo) com exibição única de `admin_email`+`temp_password`; detalhe com abas Visão geral, Usuários (criar, ativar/desativar, permissões, ver como), Worker, Módulos (toggle), Configurações (assentos, sessão única, rate limit, retenção padrão), Armazenamento & Integrações por tenant, Feature flags do tenant, Histórico de plano; suspender (com motivo)/reativar.
- Usuários globais: busca/filtro por role/paginação 20; wizard 3 passos (dados → acesso com módulos do tenant, role customizada, expiração → credenciais mascaradas com copiar); reset de senha com senha temporária exibida uma vez; ativar/desativar.
- Permissões: matriz a partir do registry; roles customizadas por tenant (CRUD, checkboxes por grupo); gaveta por usuário com role base, role customizada e overrides tri-state (herdar/permitir/negar) + encerrar sessões.
- Planos (CRUD c/ módulos permitidos, limites, preço por câmera, features por módulo, aprovação de treino obrigatória, ativo) e retenção de vídeo por tenant (tiers 1/7/30/90).
- Feature flags globais e por tenant.
- Aprovações de treinamento (lista por status, aprovar com notas, rejeitar com motivo).
- Tickets: lista com filtros **e** detalhe/resposta/estatísticas (hoje inacessível).
- Comunicados (criar/arquivar; e exibição ao cliente com "lido", hoje sem UI).
- Auditoria com filtros e export CSV.
- Observabilidade com abas (visão geral, infra, frota edge com drill-down de heartbeats, workers com restart, streams agregado), intervalo de polling global persistido (incl. "pausado"), janela histórica, "coletar agora".
- White-label por tenant: lista com previews, editor (cores primária/acento, superfícies, nome do produto, logo e favicon com upload), preview ao vivo, reset; sandbox de paleta.
- Integrações de plataforma e por tenant (R2, Vast.ai, GPU genérico, notificação, BYO-DB): salvar sem reexibir segredo (`••••last4`), testar conexão, remover; deep-link `?type=`.
- Versões/Registry (criar, rollback com confirmação) e Changelog (filtros, criar).
- Console de teste E2E: nº de câmeras simuladas, FPS padrão/por câmera, modelo real do tenant, cenário (classes/limiar/ROI) carregável do modelo, start/stop, métricas e log ao vivo (poll 3 s), aviso de Vast.ai não configurado.
- Inventário de câmeras: filtros, probe individual/lote, importação CSV com relatório de erros por linha.
- Vídeos demo (upload MP4/remover) e eventos demo por tenant/módulo.
- Workers on-premise (lista + restart).

**Qualidade (tenant com módulo `quality`)**
- Câmeras do módulo: atribuir/remover, editar OP e tipo de peça (e, a completar: modo setup, modelo ativo, snapshots de referência).
- Dashboard ao vivo (totais + estações) com polling curto e backoff; modo demo opcional.
- Inspeções: lista **real** com filtros (câmera, resultado, feedback, turno, OP, datas) e paginação; detalhe com evidência e clipe assinados (renovação automática), feedback confirmar/rejeitar com notas; preparar anotação.
- Workspace de anotação: frames NOK, bbox normalizada por classe, auto-save por frame, pular, atalhos de teclado, progresso; criar job de treino; acompanhar jobs e ativar modelo por câmera.
- Andon (monitor de chão, polling 15 s, flash em NOK) e CEP (gráfico de controle por câmera).
- Quality Gate RVB: histórico de peças com drill-down (validações, retrabalhos, foto), retrabalhos com métricas e fotos antes/depois, relatórios por OP com status/export Wiser e CSV, configuração de estações e parâmetros globais (OCR, thresholds V1/V2/V3, frames, confiança mínima) — **tudo dependente de endpoints a criar/alinhar no backend (ver C)**.
- Tablet kiosk por bancada: máquina de estados dirigida por eventos de socket (estado da bancada, peça identificada, resultado OK/NOK), ações iniciar inspeção / corrigir / falso positivo / liberar para bancada B, auto-avanço no OK — com evento de resultado **corretamente** entregue pelo backend e autenticação adequada ao dispositivo (sessão ou allowlist de IP).
