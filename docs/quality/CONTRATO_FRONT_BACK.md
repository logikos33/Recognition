# Contrato Frontend — Backend: Matriz de Auditoria

> Gerado em: 2026-07-01
> Auditor: chore/audit-contract-frontback (leitura estatica de fontes)
> Escopo backend: `services/api/app/api/v1/**/routes.py` (32 arquivos)
> Escopo frontend: `apps/frontend/src/services/*.ts` + `pages/` + `components/` (raw fetch)

---

## Resumo Executivo

| Metrica | Valor |
|---------|-------|
| Endpoints backend mapeados | **246** |
| Endpoints com chamada frontend correspondente | **~42** |
| Endpoints sem UI alguma (nao surfaced) | **~204** |
| Chamadas frontend sem endpoint backend (UI orfa) | **3** |
| Violacoes raw `fetch()` fora do `api.ts` | **10** |
| Gaps criticos (P0) | **5** |

---

## 1. Tabela Completa de Endpoints Backend

### 1.1 Auth (`/api/auth`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 1 | POST | `/api/auth/register` | publico | nao surfaced (sem pagina de registro) |
| 2 | POST | `/api/auth/login` | publico | `api.post('/auth/login')` em hooks de auth |
| 3 | GET | `/api/auth/me` | JWT | provavelmente em `useAuth` (nao em services/) |

### 1.2 Cameras (`/api/cameras`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 4 | GET | `/api/cameras` | JWT | `cameraService.list()` |
| 5 | POST | `/api/cameras` | JWT | `cameraService.create()` |
| 6 | GET | `/api/cameras/<id>` | JWT | `cameraService.get(id)` |
| 7 | PUT | `/api/cameras/<id>` | JWT | `cameraService.update(id)` |
| 8 | DELETE | `/api/cameras/<id>` | JWT | `cameraService.delete(id)` |
| 9 | POST | `/api/cameras/<id>/stream/start` | JWT | `cameraService.start(id)` |
| 10 | POST | `/api/cameras/<id>/stream/stop` | JWT | `cameraService.stop(id)` |
| 11 | GET | `/api/cameras/<id>/stream/status` | JWT | NAO SURFACED |
| 12 | GET | `/api/cameras/<id>/stream/info` | JWT | NAO SURFACED |
| 13 | GET | `/api/cameras/<id>/stream/<filename>` | JWT | NAO SURFACED (HLS serve) |
| 14 | POST | `/api/cameras/probe` | JWT | NAO SURFACED |
| 15 | POST | `/api/cameras/<id>/test` | JWT | `cameraService.test(id)` |
| 16 | GET | `/api/cameras/<id>/model` | JWT | NAO SURFACED (legacy) |
| 17 | PUT | `/api/cameras/<id>/model` | JWT | NAO SURFACED (legacy) |
| 18 | GET | `/api/cameras/<id>/models` | JWT | `countingService.getCameraModels(id)` |
| 19 | PUT | `/api/cameras/<id>/models` | JWT | `countingService.setCameraModel(id)` |
| 20 | GET | `/api/cameras/<id>/available-models` | JWT | NAO SURFACED |
| 21 | GET | `/api/cameras/<id>/effective-model` | JWT | NAO SURFACED |
| 22 | PATCH | `/api/cameras/<id>/module` | JWT | NAO SURFACED |
| 23 | PUT | `/api/cameras/<id>/schedule` | JWT | NAO SURFACED |
| 24 | GET | `/api/cameras/<id>/module/current` | JWT | NAO SURFACED |
| 25 | GET | `/api/cameras/<id>/retention` | JWT | NAO SURFACED |
| 26 | PUT | `/api/cameras/<id>/retention` | JWT | NAO SURFACED |

### 1.3 Alerts (`/api/alerts`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 27 | GET | `/api/alerts` | JWT | `api.get('/alerts?...')` em AlertsHistoryPage |
| 28 | GET | `/api/alerts/export` | JWT | `fetch(${apiBase}/api/alerts/export)` — raw fetch |
| 29 | POST | `/api/alerts/<id>/acknowledge` | JWT | `api.post('/alerts/${id}/acknowledge')` em AlertsHistoryPage |
| 30 | GET | `/api/alerts/<id>/snapshot` | JWT | `api.get('/alerts/${id}/snapshot')` em AlertsHistoryPage |
| 31 | GET | `/api/alerts/stats` | JWT | NAO SURFACED |

### 1.4 Training (`/api/training/...`, `/api/classes`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 32 | GET | `/api/training/videos` | JWT | `trainingService.listVideos()` |
| 33 | POST | `/api/training/videos` | JWT | `trainingService.uploadVideo()` (raw fetch) |
| 34 | GET | `/api/training/videos/<id>/frames` | JWT | raw fetch em AnnotationPage.tsx e AnnotationInterface.jsx |
| 35 | GET | `/api/training/frames/<id>/image` | JWT | NAO SURFACED em service (AnnotationInterface usa diretamente) |
| 36 | GET | `/api/training/frames/<id>/annotations` | JWT | raw fetch em AnnotationInterface.jsx |
| 37 | POST | `/api/training/frames/<id>/annotations` | JWT | raw fetch em AnnotationInterface.jsx |
| 38 | GET | `/api/classes` | JWT | raw fetch em AnnotationInterface.jsx |
| 39 | POST | `/api/classes` | JWT | raw fetch em AnnotationInterface.jsx |
| 40 | POST | `/api/training/jobs` | JWT | `trainingService.createJob()` |
| 41 | GET | `/api/training/jobs` | JWT | `trainingService.listJobs()` |
| 42 | GET | `/api/training/jobs/<id>/status` | JWT | `trainingService.getJobStatus(id)` |
| 43 | GET | `/api/training/models` | JWT | `trainingService.listModels()` |
| 44 | POST | `/api/training/models/<id>/activate` | JWT | `trainingService.activateModel(id)` |
| 45 | POST | `/api/training/frames/<id>/validate` | JWT | raw fetch em AnnotationPage.tsx |
| 46 | GET | `/api/training/videos/<id>/validation-stats` | JWT | raw fetch em AnnotationPage.tsx e TrainingPage.tsx |
| 47 | GET | `/api/training/jobs/<id>/progress` | JWT | `trainingService.getJobProgress(id)` |
| 48 | GET | `/api/cameras/<id>/alerts` | JWT | NAO SURFACED (duplicado em training/routes.py) |

### 1.5 Dashboard (`/api/v1/dashboard`, `/api/v1/reports`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 49 | GET | `/api/v1/dashboard/stats` | JWT | NAO SURFACED (reportService usa `/reports/home`) |
| 50 | GET | `/api/v1/dashboard/detections` | JWT | NAO SURFACED |
| 51 | GET | `/api/v1/reports/export` | JWT | `fetch(${apiBase}/v1/reports/export)` em DashboardPage — PATH BUG (falta `/api`) |

### 1.6 Modules (`/api/modules`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 52 | GET | `/api/modules/` | JWT | `moduleService.list()` |
| 53 | GET | `/api/modules/<code>` | JWT | `moduleService.get(code)` |
| 54 | GET | `/api/modules/<code>/classes` | JWT | `moduleService.getClasses(code)` |
| 55 | GET | `/api/modules/<code>/stats` | JWT | `moduleService.getStats(code)` |
| 56 | PATCH | `/api/modules/<code>/classes/<id>` | JWT | NAO SURFACED |

### 1.7 Reports (`/api/reports`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 57 | GET | `/api/reports/home` | JWT | `reportService.getHomeReports()` |
| 58 | GET | `/api/reports/compliance` | JWT | NAO SURFACED |

### 1.8 Alert Rules (`/api/rules`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 59 | GET | `/api/rules` | JWT | NAO SURFACED |
| 60 | POST | `/api/rules` | JWT | NAO SURFACED |
| 61 | GET | `/api/rules/<id>` | JWT | NAO SURFACED |
| 62 | PUT | `/api/rules/<id>` | JWT | NAO SURFACED |
| 63 | DELETE | `/api/rules/<id>` | JWT | NAO SURFACED |
| 64 | POST | `/api/rules/<id>/toggle` | JWT | NAO SURFACED |

### 1.9 Verification (`/api/verification`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 65 | GET | `/api/verification/queue` | JWT | NAO SURFACED |
| 66 | GET | `/api/verification/queue/count` | JWT | NAO SURFACED |
| 67 | POST | `/api/verification/<id>/review` | JWT | NAO SURFACED |

### 1.10 Videos (`/api/v1/videos`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 68 | POST | `/api/v1/videos/upload` | JWT | NAO SURFACED (trainingService usa `/training/videos` diferente) |
| 69 | POST | `/api/v1/videos/upload-url` | JWT | NAO SURFACED |
| 70 | POST | `/api/v1/videos/<id>/extract` | JWT | NAO SURFACED |
| 71 | GET | `/api/v1/videos/<id>/status` | JWT | NAO SURFACED |
| 72 | DELETE | `/api/v1/videos/<id>` | JWT | NAO SURFACED |
| 73 | POST | `/api/v1/videos/<id>/upload-complete` | JWT | NAO SURFACED |
| 74 | POST | `/api/v1/videos/<id>/retry-extraction` | JWT | NAO SURFACED |
| 75 | GET | `/api/v1/videos/<id>/download-url` | JWT | NAO SURFACED |
| 76 | POST | `/api/v1/videos/<id>/frames/upload` | JWT | NAO SURFACED |
| 77 | POST | `/api/v1/videos/<id>/finalize-extraction` | JWT | NAO SURFACED |
| 78 | GET | `/api/v1/videos/<id>/blob` | JWT | NAO SURFACED |
| 79 | POST | `/api/v1/videos/<id>/server-extract` | JWT | NAO SURFACED |
| 80 | GET | `/api/v1/videos/storage` | JWT | NAO SURFACED |
| 81 | POST | `/api/v1/videos/images/upload` | JWT | NAO SURFACED |

> Nota: `trainingService.uploadVideo()` chama `POST /api/training/videos` (blueprint training).
> Os endpoints acima em `/api/v1/videos` formam um pipeline paralelo mais avancado
> (upload R2 + extracao Celery) completamente sem UI correspondente.

### 1.11 Admin (`/api/v1/admin`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 82 | GET | `/api/v1/admin/dashboard` | superadmin | NAO SURFACED |
| 83 | GET | `/api/v1/admin/tenants` | superadmin | NAO SURFACED |
| 84 | POST | `/api/v1/admin/tenants` | superadmin | NAO SURFACED |
| 85 | GET | `/api/v1/admin/tenants/<id>` | superadmin | NAO SURFACED |
| 86 | PATCH | `/api/v1/admin/tenants/<id>` | superadmin | NAO SURFACED |
| 87 | POST | `/api/v1/admin/tenants/<id>/suspend` | superadmin | NAO SURFACED |
| 88 | POST | `/api/v1/admin/tenants/<id>/reactivate` | superadmin | NAO SURFACED |
| 89 | GET | `/api/v1/admin/tenants/<id>/overview` | superadmin | NAO SURFACED |
| 90 | GET | `/api/v1/admin/tenants/<id>/plan-history` | superadmin | NAO SURFACED |
| 91 | GET | `/api/v1/admin/users` | superadmin | NAO SURFACED |
| 92 | POST | `/api/v1/admin/users` | superadmin | NAO SURFACED |
| 93 | GET | `/api/v1/admin/users/<id>` | superadmin | NAO SURFACED |
| 94 | PATCH | `/api/v1/admin/users/<id>` | superadmin | NAO SURFACED |
| 95 | POST | `/api/v1/admin/users/<id>/deactivate` | superadmin | NAO SURFACED |
| 96 | POST | `/api/v1/admin/users/<id>/reactivate` | superadmin | NAO SURFACED |
| 97 | POST | `/api/v1/admin/users/<id>/force-password-reset` | superadmin | NAO SURFACED |
| 98 | GET | `/api/v1/admin/users/<id>/sessions` | superadmin | NAO SURFACED |
| 99 | DELETE | `/api/v1/admin/users/<id>/sessions` | superadmin | NAO SURFACED |
| 100 | GET | `/api/v1/admin/permissions/matrix` | superadmin | NAO SURFACED |
| 101 | GET | `/api/v1/admin/training-approvals` | superadmin | NAO SURFACED |
| 102 | GET | `/api/v1/admin/training-approvals/<id>` | superadmin | NAO SURFACED |
| 103 | POST | `/api/v1/admin/training-approvals/<id>/approve` | superadmin | NAO SURFACED |
| 104 | POST | `/api/v1/admin/training-approvals/<id>/reject` | superadmin | NAO SURFACED |
| 105 | GET | `/api/v1/admin/workers` | superadmin | NAO SURFACED |
| 106 | GET | `/api/v1/admin/workers/<schema>` | superadmin | NAO SURFACED |
| 107 | POST | `/api/v1/admin/workers/<schema>/restart` | superadmin | NAO SURFACED |
| 108 | GET | `/api/v1/admin/workers/<schema>/metrics` | superadmin | NAO SURFACED |
| 109 | POST | `/api/v1/admin/workers/heartbeat` | X-Worker-Secret | NAO SURFACED (worker interno) |
| 110 | GET | `/api/v1/admin/plans` | superadmin | NAO SURFACED |
| 111 | POST | `/api/v1/admin/plans` | superadmin | NAO SURFACED |
| 112 | PATCH | `/api/v1/admin/plans/<id>` | superadmin | NAO SURFACED |
| 113 | GET | `/api/v1/admin/plans/<id>/tenants` | superadmin | NAO SURFACED |
| 114 | GET | `/api/v1/admin/feature-flags` | superadmin | NAO SURFACED |
| 115 | PATCH | `/api/v1/admin/feature-flags/<key>` | superadmin | NAO SURFACED |
| 116 | GET | `/api/v1/admin/feature-flags/tenant/<id>` | superadmin | NAO SURFACED |
| 117 | PATCH | `/api/v1/admin/feature-flags/tenant/<id>` | superadmin | NAO SURFACED |
| 118 | GET | `/api/v1/admin/tickets` | superadmin | NAO SURFACED |
| 119 | GET | `/api/v1/admin/tickets/stats` | superadmin | NAO SURFACED |
| 120 | GET | `/api/v1/admin/tickets/<id>` | superadmin | NAO SURFACED |
| 121 | POST | `/api/v1/admin/tickets/<id>/reply` | superadmin | NAO SURFACED |
| 122 | PATCH | `/api/v1/admin/tickets/<id>` | superadmin | NAO SURFACED |
| 123 | GET | `/api/v1/admin/audit-log` | superadmin | `adminService.ts:242` raw fetch |
| 124 | GET | `/api/v1/admin/audit-log/export` | superadmin | NAO SURFACED |
| 125 | GET | `/api/v1/admin/announcements` | superadmin | NAO SURFACED |
| 126 | POST | `/api/v1/admin/announcements` | superadmin | NAO SURFACED |
| 127 | PATCH | `/api/v1/admin/announcements/<id>` | superadmin | NAO SURFACED |
| 128 | DELETE | `/api/v1/admin/announcements/<id>` | superadmin | NAO SURFACED |
| 129 | GET | `/api/v1/admin/health/platform` | superadmin | NAO SURFACED |
| 130 | GET | `/api/v1/admin/health/metrics` | superadmin | NAO SURFACED |
| 131 | GET | `/api/v1/announcements` | JWT | NAO SURFACED |
| 132 | POST | `/api/v1/announcements/<id>/read` | JWT | NAO SURFACED |

### 1.12 Notifications (`/api/v1/notifications`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 133 | GET | `/api/v1/notifications/channels` | JWT | NAO SURFACED |
| 134 | POST | `/api/v1/notifications/channels` | JWT admin | NAO SURFACED |
| 135 | PATCH | `/api/v1/notifications/channels/<id>` | JWT admin | NAO SURFACED |
| 136 | DELETE | `/api/v1/notifications/channels/<id>` | JWT admin | NAO SURFACED |

### 1.13 Scenarios (`/api/v1`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 137 | GET | `/api/v1/cameras/<id>/scenario` | JWT | NAO SURFACED (ScenarioEditor existe mas sem chamada de service) |
| 138 | GET | `/api/v1/scenarios/operation-types` | JWT | NAO SURFACED |

### 1.14 Models Rollout (`/api/v1/models`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 139 | GET | `/api/v1/models/active` | JWT | NAO SURFACED |
| 140 | POST | `/api/v1/models/<id>/pin` | JWT admin | NAO SURFACED |

### 1.15 Operations (`/api/cameras/<id>/operations`, `/api/operations/<id>`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 141 | GET | `/api/modules/<id>/operation-types` | JWT | NAO SURFACED |
| 142 | GET | `/api/cameras/<id>/operations` | JWT | NAO SURFACED |
| 143 | POST | `/api/cameras/<id>/operations` | JWT | NAO SURFACED |
| 144 | PUT | `/api/operations/<id>` | JWT | NAO SURFACED |
| 145 | DELETE | `/api/operations/<id>` | JWT | NAO SURFACED |
| 146 | GET | `/api/operations/<id>/results` | JWT | NAO SURFACED |
| 147 | POST | `/api/operations/<id>/test` | JWT | NAO SURFACED |

### 1.16 Quality (`/api/v1/quality`)

> 50 endpoints — todos sem chamada de frontend correspondente em `services/`.

| # | Metodo | Caminho |
|---|--------|---------|
| 148 | GET | `/api/v1/quality/classes` |
| 149 | GET | `/api/v1/quality/defect-categories` |
| 150 | GET | `/api/v1/quality/cameras` |
| 151 | GET | `/api/v1/quality/cameras/available` |
| 152 | POST | `/api/v1/quality/cameras/<id>/assign` |
| 153 | DELETE | `/api/v1/quality/cameras/<id>/unassign` |
| 154 | PATCH | `/api/v1/quality/cameras/<id>/config` |
| 155 | POST | `/api/v1/quality/cameras/<id>/toggle-setup-mode` |
| 156 | GET | `/api/v1/quality/inspections` |
| 157 | GET | `/api/v1/quality/inspections/summary` |
| 158 | GET | `/api/v1/quality/inspections/<id>` |
| 159 | GET | `/api/v1/quality/inspections/<id>/clip-url` |
| 160 | GET | `/api/v1/quality/inspections/<id>/evidence-url` |
| 161 | PATCH | `/api/v1/quality/inspections/<id>/feedback` |
| 162 | GET | `/api/v1/quality/andon/<camera_id>` |
| 163 | POST | `/api/v1/quality/inspections/<id>/prepare-annotation` |
| 164 | GET | `/api/v1/quality/inspections/<id>/annotation-frames` |
| 165 | GET | `/api/v1/quality/annotation-frames/<id>/url` |
| 166 | PUT | `/api/v1/quality/annotation-frames/<id>/annotations` |
| 167 | GET | `/api/v1/quality/inspections/<id>/annotation-progress` |
| 168 | POST | `/api/v1/quality/inspections/<id>/create-training-job` |
| 169 | POST | `/api/v1/quality/training/jobs` |
| 170 | GET | `/api/v1/quality/training/jobs` |
| 171 | GET | `/api/v1/quality/training/jobs/<id>` |
| 172 | GET | `/api/v1/quality/training/jobs/<id>/progress` |
| 173 | POST | `/api/v1/quality/training/models/<id>/activate` |
| 174 | GET | `/api/v1/quality/reference-snapshots/<camera_id>` |
| 175 | GET | `/api/v1/quality/cep/<camera_id>` |
| 176 | GET | `/api/v1/quality/reports/shift` |
| 177 | GET | `/api/v1/quality/reports/shift/pdf` |
| 178 | GET | `/api/v1/quality/gate/pieces` |
| 179 | POST | `/api/v1/quality/gate/pieces` |
| 180 | GET | `/api/v1/quality/gate/pieces/<id>` |
| 181 | POST | `/api/v1/quality/gate/pieces/<id>/identify` |
| 182 | POST | `/api/v1/quality/gate/pieces/<id>/inspect` |
| 183 | POST | `/api/v1/quality/gate/pieces/<id>/result` |
| 184 | POST | `/api/v1/quality/gate/pieces/<id>/false-positive` |
| 185 | POST | `/api/v1/quality/gate/pieces/<id>/release-to-bench-b` |
| 186 | GET | `/api/v1/quality/gate/reworks` |
| 187 | POST | `/api/v1/quality/gate/reworks` |
| 188 | PATCH | `/api/v1/quality/gate/reworks/<id>/complete` |
| 189 | GET | `/api/v1/quality/gate/stations` |
| 190 | POST | `/api/v1/quality/gate/stations` |
| 191 | GET | `/api/v1/quality/gate/stations/<code>` |
| 192 | PUT | `/api/v1/quality/gate/stations/<code>` |
| 193 | GET | `/api/v1/quality/gate/stats/overview` |
| 194 | GET | `/api/v1/quality/gate/stats/rework` |
| 195 | GET | `/api/v1/quality/dashboard/summary` |
| 196 | GET | `/api/v1/quality/dashboard/stations` |
| 197 | POST | `/api/v1/quality/demo/seed` |

> Excecao: `TabletTransition.tsx`, `TabletIdentified.tsx`, `TabletResultNOK.tsx` fazem raw fetch
> direto para alguns destes endpoints sem passar pelo `api.ts` — ver Secao 3.

### 1.17 Health

| # | Metodo | Caminho | Chamada Frontend |
|---|--------|---------|-----------------|
| 198 | GET | `/health` (alias `/api/v1/health`) | NAO SURFACED (smoke tests apenas) |
| 199 | GET | `/api/v1/health/metrics` | NAO SURFACED |

### 1.18 Streams

| # | Metodo | Caminho | Chamada Frontend |
|---|--------|---------|-----------------|
| 200 | GET | `/api/streams/status` | NAO SURFACED |

### 1.19 Edge (`/api/v1/edge`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 201 | POST | `/api/v1/edge/heartbeat` | device RS256 | NAO SURFACED (edge-agent) |
| 202 | GET | `/api/v1/edge/sites/health` | JWT admin | `edgeService.getSitesHealth()` |
| 203 | GET | `/api/v1/edge/overview` | JWT admin | `edgeService.getOverview()` |
| 204 | POST | `/api/v1/edge/sites` | JWT admin | NAO SURFACED |
| 205 | GET | `/api/v1/edge/sites` | JWT admin | NAO SURFACED |
| 206 | GET | `/api/v1/edge/sites/<id>` | JWT admin | NAO SURFACED |
| 207 | PATCH | `/api/v1/edge/sites/<id>` | JWT admin | NAO SURFACED |
| 208 | POST | `/api/v1/edge/sites/<id>/enrollment-tokens` | JWT admin | NAO SURFACED |
| 209 | GET | `/api/v1/edge/sites/<id>/enrollment-tokens` | JWT admin | NAO SURFACED |
| 210 | POST | `/api/v1/edge/enrollment-tokens/<id>/revoke` | JWT admin | NAO SURFACED |
| 211 | POST | `/api/v1/edge/enroll` | publico | NAO SURFACED (edge-agent) |
| 212 | GET | `/api/v1/edge/sites/<id>/heartbeats` | JWT admin | `edgeService.getSiteHeartbeats(id)` |
| 213 | GET | `/api/v1/edge/sites/<id>/heartbeat-summary` | JWT admin | `edgeService.getHeartbeatSummary(id)` |
| 214 | GET | `/api/v1/edge/sites/<id>/devices` | JWT admin | NAO SURFACED |
| 215 | POST | `/api/v1/edge/devices/<id>/revoke` | JWT admin | NAO SURFACED |

### 1.20 Edge Commands e Events

| # | Metodo | Caminho | Chamada Frontend |
|---|--------|---------|-----------------|
| 216 | POST | `/api/v1/edge/commands` | NAO SURFACED |
| 217 | GET | `/api/v1/edge/commands/pending` | NAO SURFACED (edge-agent poll) |
| 218 | PATCH | `/api/v1/edge/commands/<id>` | NAO SURFACED |
| 219 | GET | `/api/v1/edge/commands` | NAO SURFACED |
| 220 | POST | `/api/v1/edge/events/ingest` | NAO SURFACED (edge-agent) |
| 221 | GET | `/api/v1/edge/events` | NAO SURFACED |

### 1.21 Site Gateways

| # | Metodo | Caminho | Chamada Frontend |
|---|--------|---------|-----------------|
| 222 | GET | `/api/v1/site-gateways/<site_id>` | NAO SURFACED |
| 223 | PUT | `/api/v1/site-gateways/<site_id>` | NAO SURFACED |
| 224 | PATCH | `/api/v1/site-gateways/<site_id>/status` | NAO SURFACED |

### 1.22 Counting (`/api/counting`)

| # | Metodo | Caminho | Role | Chamada Frontend |
|---|--------|---------|------|-----------------|
| 225 | POST | `/api/counting/sessions` | JWT | NAO SURFACED |
| 226 | GET | `/api/counting/sessions` | JWT | NAO SURFACED |
| 227 | DELETE | `/api/counting/sessions/<id>` | JWT | NAO SURFACED |
| 228 | GET | `/api/counting/sessions/<id>/stats` | JWT | NAO SURFACED |
| 229 | PATCH | `/api/counting/sessions/<id>/plate` | JWT | countingService.updateSession chama path errado — MISMATCH |
| 230 | GET | `/api/counting/sessions/plates` | JWT | NAO SURFACED |

### 1.23 Branding

| # | Metodo | Caminho | Chamada Frontend |
|---|--------|---------|-----------------|
| 231 | GET | `/api/v1/tenant/branding` | NAO SURFACED |
| 232 | GET | `/api/v1/admin/branding/tenants` | NAO SURFACED |
| 233 | GET | `/api/v1/admin/branding/tenant/<id>` | NAO SURFACED |
| 234 | PUT | `/api/v1/admin/branding` | NAO SURFACED |
| 235 | POST | `/api/v1/admin/branding/logo` | NAO SURFACED |

### 1.24 Chat, Devices, Retention, Events, Feedback

| # | Metodo | Caminho | Chamada Frontend |
|---|--------|---------|-----------------|
| 236 | POST | `/api/chat` | `fetch('/api/chat', ...)` em ChatFAB.tsx — raw fetch sem auth |
| 237 | GET | `/api/chat/health` | NAO SURFACED |
| 238 | POST | `/api/devices/claim-codes` | NAO SURFACED |
| 239 | POST | `/api/devices/claim` | NAO SURFACED |
| 240 | GET | `/api/v1/tenant/retention` | NAO SURFACED |
| 241 | PUT | `/api/v1/tenant/retention` | NAO SURFACED |
| 242 | GET | `/api/v1/events/search` | NAO SURFACED |
| 243 | GET | `/api/v1/events/timeline` | NAO SURFACED |
| 244 | POST | `/api/v1/feedback` | NAO SURFACED |
| 245 | GET | `/api/v1/feedback` | NAO SURFACED |
| 246 | GET | `/api/v1/feedback/summary` | NAO SURFACED |

---

## 2. Tabela de Chamadas Frontend

### 2.1 Via api.ts wrapper (correto)

| Arquivo | Caminho chamado | Metodo | Endpoint backend | Status |
|---------|----------------|--------|-----------------|--------|
| `cameraService.ts` | `/cameras` | GET | `GET /api/cameras` | OK |
| `cameraService.ts` | `/cameras` | POST | `POST /api/cameras` | OK |
| `cameraService.ts` | `/cameras/${id}` | GET | `GET /api/cameras/<id>` | OK |
| `cameraService.ts` | `/cameras/${id}` | PUT | `PUT /api/cameras/<id>` | OK |
| `cameraService.ts` | `/cameras/${id}` | DELETE | `DELETE /api/cameras/<id>` | OK |
| `cameraService.ts` | `/cameras/${id}/test` | POST | `POST /api/cameras/<id>/test` | OK |
| `cameraService.ts` | `/cameras/${id}/stream/start` | POST | `POST /api/cameras/<id>/stream/start` | OK |
| `cameraService.ts` | `/cameras/${id}/stream/stop` | POST | `POST /api/cameras/<id>/stream/stop` | OK |
| `countingService.ts` | `/counting/sessions/${id}` | PATCH | NAO EXISTE — backend tem PATCH `.../plate` | ORFAO P0 |
| `countingService.ts` | `/counting/sessions/validation-report` | GET | NAO EXISTE | ORFAO P0 |
| `countingService.ts` | `/cameras/${id}/models` | GET | `GET /api/cameras/<id>/models` | OK |
| `countingService.ts` | `/cameras/${id}/models` | PUT | `PUT /api/cameras/<id>/models` | OK |
| `moduleService.ts` | `/modules/` | GET | `GET /api/modules/` | OK |
| `moduleService.ts` | `/modules/${code}` | GET | `GET /api/modules/<code>` | OK |
| `moduleService.ts` | `/modules/${code}/classes` | GET | `GET /api/modules/<code>/classes` | OK |
| `moduleService.ts` | `/modules/${code}/stats` | GET | `GET /api/modules/<code>/stats` | OK |
| `reportService.ts` | `/reports/home` | GET | `GET /api/reports/home` | OK |
| `trainingService.ts` | `/training/jobs` | GET | `GET /api/training/jobs` | OK |
| `trainingService.ts` | `/training/jobs` | POST | `POST /api/training/jobs` | OK |
| `trainingService.ts` | `/training/jobs/${id}/status` | GET | `GET /api/training/jobs/<id>/status` | OK |
| `trainingService.ts` | `/training/jobs/${id}/progress` | GET | `GET /api/training/jobs/<id>/progress` | OK |
| `trainingService.ts` | `/training/models` | GET | `GET /api/training/models` | OK |
| `trainingService.ts` | `/training/models/${id}/activate` | POST | `POST /api/training/models/<id>/activate` | OK |
| `trainingService.ts` | `/training/videos` | GET | `GET /api/training/videos` | OK |
| `edgeService.ts` | `/v1/edge/overview` | GET | `GET /api/v1/edge/overview` | OK |
| `edgeService.ts` | `/v1/edge/sites/health` | GET | `GET /api/v1/edge/sites/health` | OK |
| `edgeService.ts` | `/v1/edge/sites/${id}/heartbeats` | GET | `GET /api/v1/edge/sites/<id>/heartbeats` | OK |
| `edgeService.ts` | `/v1/edge/sites/${id}/heartbeat-summary` | GET | `GET /api/v1/edge/sites/<id>/heartbeat-summary` | OK |
| `AlertsHistoryPage.tsx` | `/alerts?...` | GET | `GET /api/alerts` | OK |
| `AlertsHistoryPage.tsx` | `/alerts/${id}/acknowledge` | POST | `POST /api/alerts/<id>/acknowledge` | OK |
| `AlertsHistoryPage.tsx` | `/alerts/${id}/snapshot` | GET | `GET /api/alerts/<id>/snapshot` | OK |

### 2.2 Raw `fetch()` fora do api.ts — violacoes de padrao

| Arquivo | Linha aprox | URL construida | Endpoint backend | Problema |
|---------|------------|---------------|-----------------|---------|
| `AlertsHistoryPage.tsx` | 74 | `${apiBase}/api/alerts/export?...` | `GET /api/alerts/export` | raw fetch; endpoint existe |
| `AnnotationInterface.jsx` | varios | `${API_BASE}/training/videos/${id}/frames` GET | `GET /api/training/videos/<id>/frames` | raw fetch; arquivo protegido |
| `AnnotationInterface.jsx` | 419 | `${API_BASE}/classes` GET | endpoint inexistente — deveria ser `/api/v1/quality/classes` | BUG P0: rota errada |
| `AnnotationPage.tsx` | 73 | `/api/training/videos/${id}/frames` | `GET /api/training/videos/<id>/frames` | raw fetch; URL relativa falha em producao |
| `AnnotationPage.tsx` | 76 | `/api/training/videos/${id}/validation-stats` | `GET /api/training/videos/<id>/validation-stats` | raw fetch; URL relativa |
| `AnnotationPage.tsx` | 95 | `/api/training/frames/${id}/validate` | `POST /api/training/frames/<id>/validate` | raw fetch; URL relativa |
| `TrainingPage.tsx` | 170 | `/api/training/videos/${id}/validation-stats` | `GET /api/training/videos/<id>/validation-stats` | raw fetch; URL relativa |
| `DashboardPage.tsx` | 69 | `${apiBase}/v1/reports/export?days=30` | `GET /api/v1/reports/export` | PATH BUG: falta `/api` — 404 em producao |
| `ChatFAB.tsx` | 56 | `/api/chat` | `POST /api/chat` | raw fetch sem Authorization header |
| `trainingService.ts` | 59 | `${apiBase}/api/training/videos` POST multipart | `POST /api/training/videos` | raw fetch em service (construcao dupla de /api) |
| `TabletTransition.tsx` | 24 | `${API_URL}/api/v1/quality/gate/pieces/${id}/release` POST | `/api/v1/quality/gate/pieces/<id>/release-to-bench-b` | path nao bate exatamente |
| `TabletIdentified.tsx` | 25 | `${API_URL}/api/v1/quality/gate/pieces/${id}/inspect` POST | `/api/v1/quality/gate/pieces/<id>/inspect` | raw fetch; endpoint existe |
| `TabletResultNOK.tsx` | 30 | `${API_URL}/api/v1/quality/gate/rework/start` POST | NAO EXISTE | BUG P1: rota inexistente |
| `adminService.ts` | 242 | `${base}/v1/admin/audit-log/export?${qs}` | `GET /api/v1/admin/audit-log/export` | PATH suspeito: verificar se falta `/api` |

---

## 3. Chamadas Frontend sem Backend (UI Orfa)

| ID | Servico/Arquivo | Chamada | Causa | Impacto |
|----|----------------|---------|-------|---------|
| O1 | `countingService.updateSession()` | `PATCH /api/counting/sessions/${id}` | Endpoint inexistente. Backend tem `PATCH .../plate` com shape diferente. | P0 — tela de sessoes quebrada em runtime |
| O2 | `countingService.getValidationReport()` | `GET /api/counting/sessions/validation-report` | Endpoint completamente ausente no backend. | P0 — relatorio de validacao nunca carrega |
| O3 | `DashboardPage.tsx:69` raw fetch | `${apiBase}/v1/reports/export?days=30` | Path sem `/api`. URL real: `.../v1/reports/export` — 404 em producao. | P0 — export de relatorio quebrado em producao |

---

## 4. Endpoints Backend sem UI

### Grupo A: Funcionalidades com backend completo sem pagina/servico frontend

| Dominio | Endpoints | Impacto |
|---------|-----------|---------|
| Quality Gate (bancadas, pecas, retrabalhos) | 20+ | Modulo quality nao tem nenhuma pagina React em services/ |
| Quality Inspections (inspecoes, feedback, anotacao) | 15+ | Idem |
| Quality Training (jobs, modelos, CEP) | 8+ | Idem |
| Admin Panel (tenants, users, workers, plans) | 49 | Sem painel admin no frontend |
| Alert Rules CRUD | 6 | Sem pagina de configuracao de regras |
| Verification Queue | 3 | Sem fila de revisao humana |
| Scenarios / Operations | 9 | ScenarioEditor existe mas sem chamada de API |
| Videos `/api/v1/videos` | 14 | Pipeline R2 + Celery nunca chamado pelo frontend |
| Counting Sessions | 6 | countingService chama rotas inexistentes |
| Edge Management (sites, enrollment, devices) | 11 | edgeService so le; nao gerencia |
| Notifications Channels | 4 | Sem UI de configuracao |
| Events Timeline / Search | 2 | Sem pagina de eventos |
| Announcements (client side) | 2 | Sem banner de comunicados |
| Reports Compliance | 1 | Sem relatorio de compliance |
| Branding | 5 | Sem UI de customizacao por tenant |
| Chat Health, Devices, Feedback, Retention | 9 | Varios dominios sem UI |

---

## 5. Divergencias Priorizadas

| # | Item | Severidade | Tipo |
|---|------|-----------|------|
| D1 | `countingService.updateSession` — PATCH `/counting/sessions/{id}` nao existe | P0-BUG | UI orfa |
| D2 | `countingService.getValidationReport` — GET inexistente | P0-BUG | UI orfa |
| D3 | `DashboardPage.tsx:69` — path sem `/api` → 404 em producao | P0-BUG | Path errado |
| D4 | `AnnotationInterface.jsx:419` — `/classes` nao existe (deve ser `/api/v1/quality/classes`) | P0-BUG | Rota errada, erro silencioso |
| D5 | `TabletResultNOK.tsx:30` — `rework/start` nao existe | P1-BUG | Rota inexistente |
| D6 | `ChatFAB.tsx:56` — sem Authorization header | P1 | Migrar para `api.ts` |
| D7 | `AnnotationPage.tsx` — 3 raw fetch com URL relativa (falha em producao) | P1 | Migrar para `api.ts` |
| D8 | `TabletTransition.tsx:24` — path `/release` vs `/release-to-bench-b` | P1 | Verificar rota correta |
| D9 | `trainingService.ts:59` — raw fetch multipart | P2 | Avaliar se api.ts suporta FormData |
| D10 | `AdminService.ts:242` — raw fetch; verificar se falta `/api` no path | P2 | Avaliar path |
| D11 | `AlertsHistoryPage.tsx:74`, `AnnotationInterface.jsx` — raw fetch (arquivo protegido) | P2 | needs-human para AnnotationInterface |
| OK | `AdminBrandingEditorPage.tsx:77` — fetch externo (logo blob de URL externa) | OK | Excecao legitima — nao migrar |

---

## 6. Recomendacoes por Sprint

### Sprint imediata (P0 — bloqueia funcionalidade em producao)

1. `DashboardPage.tsx:69` — corrigir path: trocar `${apiBase}/v1/reports/export` por `api.get('/v1/reports/export')` — 1 linha
2. `AnnotationInterface.jsx:419` — corrigir `/classes` para `/v1/quality/classes` — arquivo protegido, backup obrigatorio
3. Criar endpoint `PATCH /api/counting/sessions/<id>` com campos genericos OU corrigir countingService para chamar `.../plate`
4. Criar endpoint `GET /api/counting/sessions/validation-report` no backend

### Sprint seguinte (P1 — feature incompleta)

5. Migrar `AnnotationPage.tsx` raw fetch para `api.ts` (3 chamadas)
6. Migrar `ChatFAB.tsx` para `api.ts`
7. Verificar e corrigir `TabletResultNOK.tsx:30` rota `rework/start`
8. Criar `qualityService.ts` cobrindo inspecoes, feedback, dashboard
9. Criar paginas Quality Cockpit consumindo os 50 endpoints ja existentes

### Sprint tecnica (P2 — debito)

10. Corrigir `trainingService.uploadVideo()` — usar api.ts wrapper ou documentar como excecao (FormData)
11. Criar `adminService.ts` (49 endpoints de superadmin)
12. Expor `ScenarioEditor` com chamadas para `/api/v1/cameras/<id>/scenario`
13. Criar service para Alert Rules (6 endpoints sem UI)
14. Criar service para Verification Queue (3 endpoints)

---

*Arquivo gerado por auditoria estatica de fontes — nao requer execucao. Validar contra banco real antes de criar endpoints.*
