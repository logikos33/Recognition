# CONTRATO FRONT↔BACK — Recognition EPI Monitor V2
**Data:** 2026-06-21  
**Fonte front:** `apps/frontend/src/services/*.ts` + raw `fetch()` em páginas/componentes  
**Fonte back:** `services/api/app/api/v1/**/routes.py`  
**Envelope padrão esperado:** `{ status: "success"|"error", data: {...} }`

---

## 1. Serviços `api.ts`-wrapped (via wrapper — OK por padrão)

| Frontend (`services/*.ts`) | Método+Path | Backend existe? | Envelope bate? | Observação |
|---------------------------|-------------|-----------------|----------------|-----------|
| `cameraService.ts` `GET /cameras` | GET `/api/cameras` | ✅ (`cameras/routes.py`) | ✅ | OK |
| `cameraService.ts` `GET /cameras/:id` | GET `/api/cameras/:id` | ✅ | ✅ | OK |
| `cameraService.ts` `POST /cameras` | POST `/api/cameras` | ✅ | ✅ | OK |
| `cameraService.ts` `PUT /cameras/:id` | PUT `/api/cameras/:id` | ✅ | ✅ | OK |
| `cameraService.ts` `DELETE /cameras/:id` | DELETE `/api/cameras/:id` | ✅ | ✅ | OK |
| `cameraService.ts` `POST /cameras/:id/test` | POST `/api/cameras/:id/test` | ✅ | ✅ | OK |
| `cameraService.ts` `POST /cameras/:id/stream/start` | POST `/api/cameras/:id/stream/start` | ✅ | ✅ | OK |
| `cameraService.ts` `POST /cameras/:id/stream/stop` | POST `/api/cameras/:id/stream/stop` | ✅ | ✅ | OK |
| `reportService.ts` `GET /reports/home` | GET `/api/reports/home` | ✅ (`reports/routes.py`) | ✅ | OK |
| `moduleService.ts` `GET /modules/` | GET `/api/modules/` | ✅ (`modules/routes.py`) | ✅ | OK |
| `moduleService.ts` `GET /modules/:code` | GET `/api/modules/:code` | ✅ | ✅ | OK |
| `moduleService.ts` `GET /modules/:code/classes` | GET `/api/modules/:code/classes` | ✅ | ✅ | OK |
| `moduleService.ts` `GET /modules/:code/stats` | GET `/api/modules/:code/stats` | ✅ | ✅ | OK |
| `edgeService.ts` `GET /v1/edge/overview` | GET `/api/v1/edge/overview` | ✅ (`edge/routes.py`) | ✅ | OK |
| `edgeService.ts` `GET /v1/edge/sites/health` | GET `/api/v1/edge/sites/health` | ✅ | ✅ | OK |
| `trainingService.ts` `GET /training/jobs` | GET `/api/training/jobs` | ✅ (`training/routes.py`) | ✅ | OK |
| `trainingService.ts` `POST /training/jobs` | POST `/api/training/jobs` | ✅ | ✅ | OK |
| `trainingService.ts` `GET /training/jobs/:id/status` | GET `/api/training/jobs/:id/status` | ⚠️ verificar — pode ser `/progress` | ⚠️ | Verificar path |
| `trainingService.ts` `GET /training/jobs/:id/progress` | GET `/api/training/jobs/:id/progress` | ✅ | ✅ | OK |
| `trainingService.ts` `GET /training/models` | GET `/api/training/models` | ✅ | ✅ | OK |
| `trainingService.ts` `POST /training/models/:id/activate` | POST `/api/training/models/:id/activate` | ✅ | ✅ | OK |
| `trainingService.ts` `GET /training/videos` | GET `/api/training/videos` | ✅ (`videos/routes.py`) | ✅ | OK |

---

## 2. Raw `fetch()` bypassing `api.ts` — DIVERGÊNCIAS

### 2-A · `AnnotationInterface.jsx` (arquivo PROTEGIDO — needs-human)

| Linha | URL chamada | Backend existe? | Auth header? | Divergência |
|-------|-------------|-----------------|--------------|-------------|
| `:99` | `${API_BASE}/training/videos/${videoId}/frames` GET | ✅ | ✅ (manual) | Raw fetch — migrar para `api.ts` em PR próprio com backup |
| `:123` | `${API_BASE}/modules/epi/classes` GET | ✅ | ✅ (manual) | Raw fetch — idem |
| `:150` | `${API_BASE}/training/frames/${frameId}/annotations` GET | ✅ | ✅ (manual) | Raw fetch — idem |
| `:178` | `${API_BASE}/training/frames/${frameId}/annotations` POST | ✅ | ✅ (manual) | Raw fetch — idem |
| `:419` | `${API_BASE}/classes` GET | ❌ **ROTA NÃO EXISTE** — a rota é `/api/v1/quality/classes` | ❌ | **Bug real** — chamada falha silenciosamente |

**Ação:** PR próprio `quality/item-fetch-annotation-interface`, backup obrigatório, **needs-human** (não auto-merge).

### 2-B · `ChatFAB.tsx:56`

| URL | Backend | Auth | Divergência |
|-----|---------|------|-------------|
| `/api/chat` POST | ✅ (`chat/routes.py` blueprint prefix `/api/chat`) | ❌ **SEM Auth header** — `fetch('/api/chat', { method: 'POST', ... })` sem `Authorization` | P1 — requisição não-autenticada chega ao backend e falha com 401 |

**Ação:** Migrar para `api.ts` (que injeta token automaticamente). PR `quality/item-fetch-chatfab`.

### 2-C · `modules/quality/tablet/` (3 arquivos)

| Arquivo:Linha | URL | Backend existe? | Auth? | Divergência |
|--------------|-----|-----------------|-------|-------------|
| `TabletTransition.tsx:24` | `${API_URL}/api/v1/quality/gate/pieces/${piece.id}/release` POST | ✅ (`quality/routes.py:1688`) | ⚠️ manual | Raw fetch — migrar para `api.ts` |
| `TabletIdentified.tsx:25` | `${API_URL}/api/v1/quality/gate/pieces/${piece.id}/inspect` POST | ✅ (`quality/routes.py:1615`) | ⚠️ manual | Raw fetch — migrar para `api.ts` |
| `TabletResultNOK.tsx:30` | `${API_URL}/api/v1/quality/gate/rework/start` POST | ❌ **ROTA NÃO EXISTE** — verificar se foi renomeada | ❌ | **Bug real** — verificar rota atual |
| `TabletResultNOK.tsx:52` | verificar conteúdo | ? | ? | Verificar URL |

**Ação:** PR `quality/item-fetch-quality-tablet` — migrar os válidos + verificar/corrigir `rework/start`.

### 2-D · `DashboardPage.tsx:69`

| URL | Backend | Auth? | Divergência |
|-----|---------|-------|-------------|
| `${apiBase}/v1/reports/export?days=30` GET | ⚠️ verificar — prefix pode ser `/api` | ✅ (manual) | Raw fetch; verificar URL completa vs rota backend |

**Ação:** PR `quality/item-fetch-dashboard`.

### 2-E · `AlertsHistoryPage.tsx:74`

| URL | Backend | Auth? | Divergência |
|-----|---------|-------|-------------|
| `${apiBase}/api/alerts/export?...` GET | ✅ (`alerts/routes.py`) | ✅ (manual) | Raw fetch — migrar para `api.ts` |

**Ação:** Incluir no PR de alerts ou PR próprio.

### 2-F · `AnnotationPage.tsx:73,76,95`

| Linha | URL | Backend | Auth? | Divergência |
|-------|-----|---------|-------|-------------|
| `:73` | `/api/training/videos/${videoId}/frames` GET | ✅ | ⚠️ manual | Raw fetch |
| `:76` | `/api/training/videos/${videoId}/validation-stats` GET | ✅ | ⚠️ manual | Raw fetch |
| `:95` | `/api/training/frames/${frameId}/validate` POST | ✅ | ⚠️ manual | Raw fetch |

**Ação:** PR `quality/item-fetch-annotation-page`.

### 2-G · `trainingService.ts:59`

| URL | Backend | Auth? | Divergência |
|-----|---------|-------|-------------|
| `${apiBase}/api/training/videos` POST (multipart) | ✅ | ✅ (manual) | Raw fetch necessário para multipart? Verificar se `api.ts` suporta FormData. Se sim, migrar; se não, documentar como exceção legítima. |

**Ação:** Verificar `api.ts` para FormData support; migrar ou documentar.

### 2-H · `AdminBrandingEditorPage.tsx:77`

| URL | Divergência |
|-----|-------------|
| `fetch(overrides.brand.logoUrl).then(r => r.blob())` | Fetch legítimo — busca blob de URL externa (logo da marca). **Não migrar para `api.ts`** — é uma chamada externa, não para o backend da aplicação. |

**Ação:** Nenhuma — exceção legítima. Documentar no código com comentário.

### 2-I · `pages/TrainingPage.tsx:170`

| URL | Backend | Auth? | Divergência |
|-----|---------|-------|-------------|
| `/api/training/videos/${v.id}/validation-stats` GET | ✅ | ⚠️ manual | Raw fetch — migrar para `api.ts` |

**Ação:** Incluir no PR de AnnotationPage (mesmo padrão) ou PR próprio.

### 2-J · `adminService.ts:242`

| URL | Backend | Auth? | Divergência |
|-----|---------|-------|-------------|
| `${base}/v1/admin/audit-log/export?${qs}` GET | ⚠️ verificar path completo | ✅ (manual, cabeçalho construído) | Raw fetch para export; verificar se `api.ts` suporta streaming/blob response. Se sim, migrar. |

**Ação:** Verificar; migrar ou documentar.

---

## 3. Divergências priorizadas para execução

| # | Item | Severidade | Tipo |
|---|------|-----------|------|
| D1 | `AnnotationInterface.jsx:419` — `/classes` não existe (deveria ser `/api/v1/quality/classes`) | P0-BUG | Rota errada → erro silencioso |
| D2 | `TabletResultNOK.tsx:30` — `rework/start` não existe | P1-BUG | Rota inexistente |
| D3 | `ChatFAB.tsx:56` — sem Auth header | P1 | Migrar para `api.ts` |
| D4 | `AnnotationPage.tsx` — 3 raw fetch sem wrapper | P2 | Migrar para `api.ts` |
| D5 | `modules/quality/tablet/` — 3 raw fetch | P2 | Migrar + verificar D2 |
| D6 | `DashboardPage.tsx` / `AlertsHistoryPage.tsx` — raw fetch export | P2 | Migrar para `api.ts` |
| D7 | `trainingService.ts:59` — raw fetch multipart | P2 | Avaliar se legítimo |
| D8 | `adminService.ts:242` — raw fetch export | P2 | Avaliar se legítimo |
| D9 | `AnnotationInterface.jsx` — 4 raw fetch (arquivo protegido) | P2 | needs-human |
| D10 | `trainingService.ts` `GET /training/jobs/:id/status` | ⚠️ | Verificar se rota existe |
| OK | `AdminBrandingEditorPage.tsx:77` — fetch externo (logo blob) | OK | Exceção legítima, documentar |
