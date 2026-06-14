# AGENT.md — apps/frontend

**Aplicação:** Frontend SPA — Dashboard de monitoramento EPI
**Stack:** React 18 + TypeScript + Vite
**URL produção:** `https://frontend-production-bf96.up.railway.app`

---

## Propósito

SPA React para operadores monitorarem câmeras ao vivo, consultarem histórico de alertas, configurarem câmeras e regras de alerta, e acompanharem KPIs de compliance EPI. Suporta dual mode: cloud (Railway) ou LAN (mirror API do edge-sync-agent) via `useDualMode.ts`.

---

## Stack

| Componente | Versão / Detalhe |
|-----------|-----------------|
| Framework | React 18 |
| Linguagem | TypeScript (strict: true) |
| Build | Vite |
| WebSocket | socket.io-client |
| HLS player | hls.js |
| HTTP client | fetch wrapper em `src/services/api.ts` |
| Auth | JWT em localStorage, injetado automaticamente |

---

## Estrutura de Diretórios

```
apps/frontend/
├── src/
│   ├── App.tsx                          # Auth gate + BrowserRouter (≤ 100 linhas)
│   ├── AppRoutes.tsx                    # Todas as rotas da aplicação
│   ├── main.tsx                         # Entry point Vite
│   ├── components/
│   │   ├── annotation/
│   │   │   └── AnnotationInterface.jsx  # UI de anotação (modificar com backup)
│   │   └── shared/
│   │       ├── ErrorBoundary.tsx
│   │       ├── LoadingSpinner.tsx
│   │       └── StatusBadge.tsx
│   ├── hooks/
│   │   ├── useAuth.ts                   # Auth hook: login, logout, user state, JWT
│   │   ├── usePolling.ts                # Hook genérico para polling periódico
│   │   ├── useModules.ts                # Hook para módulos do tenant
│   │   ├── useMonitoringSocket.ts       # WebSocket: detecções em tempo real
│   │   └── useDualMode.ts              # Detecta cloud vs edge LAN (Fase 7)
│   ├── modules/
│   │   ├── epi/                         # Componentes específicos do módulo EPI
│   │   └── fueling/                     # Componentes do módulo Fueling
│   ├── pages/
│   │   ├── HomePage.tsx                 # Dashboard global (reports + module cards)
│   │   ├── CamerasPage.tsx              # Lista e gerenciamento de câmeras
│   │   ├── MonitoringPage.tsx           # Live view com overlay de bounding boxes
│   │   ├── AlertsHistoryPage.tsx        # Histórico filtrado de alertas
│   │   ├── epi/
│   │   │   ├── EpiDashboard.tsx
│   │   │   ├── EpiCameras.tsx
│   │   │   └── EpiAlerts.tsx
│   │   └── fueling/
│   │       └── FuelingPlaceholder.tsx
│   ├── services/
│   │   ├── api.ts                       # Fetch wrapper com JWT auto-injection
│   │   ├── moduleService.ts
│   │   └── reportService.ts
│   ├── stores/                          # Estado global (Zustand ou Context)
│   ├── types/                           # Interfaces TypeScript
│   └── utils/
├── public/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
├── AGENT.md                             # Este arquivo
└── Dockerfile
```

---

## API Client: `src/services/api.ts`

Wrapper sobre `fetch` que injeta automaticamente o JWT de localStorage:

```typescript
// Uso em qualquer componente/hook:
import { api } from '../services/api'

// GET com tipagem
const res = await api.get<{ status: string; data: Camera[] }>('/api/cameras')
const cameras = res.data   // acessa envelope {status, data}

// POST
const res = await api.post<{ status: string; data: Alert }>('/api/alerts', body)
```

**Comportamento:**
- Lê `localStorage.getItem('token')` e injeta em `Authorization: Bearer <token>`
- Em 401: chama `logout()` e redireciona para `/login`
- Não faz retry automático (retries são responsabilidade do chamador)
- Base URL: `VITE_API_URL` (padrão: `http://localhost:5001`)

---

## Auth: `src/hooks/useAuth.ts`

```typescript
const { user, token, login, logout, isAuthenticated } = useAuth()
```

- JWT armazenado em `localStorage` (chave `token`)
- `user` contém `{ id, email, tenant_id, tenant_schema, role }`
- `login(email, password)` chama `POST /api/auth/login` e persiste token
- `logout()` limpa localStorage e redireciona para `/login`
- `App.tsx` usa `isAuthenticated` como auth gate antes de renderizar rotas

---

## WebSocket: `src/hooks/useMonitoringSocket.ts`

```typescript
const { detections, connectionStatus } = useMonitoringSocket(cameraId)
```

- Conecta via `socket.io-client` em `VITE_API_URL`
- Assina room `tenant:{tenant_id}` automaticamente após conexão
- Recebe evento `detection` com payload `DetectionEvent` (camera_id, detections[], has_violation)
- Overlay de bounding boxes renderizado em `<canvas>` com `pointerEvents: 'none'`

---

## Dual Mode: `src/hooks/useDualMode.ts`

```typescript
const { apiBase, isEdgeMode } = useDualMode()
```

Lógica de fallback (Fase 7):
1. Tenta `GET ${VITE_API_URL}/health` — se responder em < 2s, usa cloud
2. Se timeout, tenta `GET http://edge.${SITE_CODE}.local:8080/health`
3. Se edge responder, `isEdgeMode=true` e `apiBase` aponta para mirror API LAN
4. Re-verifica a cada 30s para retorno automático ao cloud

`SITE_CODE` é lido do JWT do usuário (`tenant_schema`).

---

## Multi-módulo

Cada tenant tem acesso a módulos configurados em `tenant_modules`. O frontend:
- Lê módulos disponíveis via `useModules()` → `GET /api/modules`
- Renderiza módulos ativos no `HomePage` como cards
- `module_code` (`epi`, `fueling`) determina quais páginas e componentes são exibidos
- Rotas de módulo: `/epi/*`, `/fueling/*`

---

## Páginas Principais

| Página | Rota | Descrição |
|--------|------|-----------|
| `HomePage` | `/` | Dashboard com KPIs, module cards, relatório resumido |
| `MonitoringPage` | `/monitoring` | Live view de câmeras com overlay YOLO |
| `CamerasPage` | `/cameras` | CRUD de câmeras IP |
| `AlertsHistoryPage` | `/alerts` | Histórico filtrado (câmera, módulo, período, classe) |
| `EpiDashboard` | `/epi` | Dashboard específico do módulo EPI |
| `EpiCameras` | `/epi/cameras` | Câmeras do módulo EPI |
| `EpiAlerts` | `/epi/alerts` | Alertas do módulo EPI |

---

## Vite Config (Obrigatório)

```typescript
// vite.config.ts — necessário devido ao path com espaço no filesystem
server: {
  usePolling: true,
  cacheDir: '/tmp/vite-cache-epi'
}
```

---

## Variáveis de Ambiente

```bash
# .env.local (desenvolvimento)
VITE_API_URL=http://localhost:5001
VITE_WS_URL=http://localhost:5001

# Produção (Railway)
VITE_API_URL=https://api-v3-production-2b22.up.railway.app
VITE_WS_URL=https://api-v3-production-2b22.up.railway.app
```

---

## Comandos

```bash
cd apps/frontend
npm run dev           # porta 3000, proxy para VITE_API_URL
npm run build         # build de produção em dist/
npx tsc --noEmit      # type check sem emitir arquivos
npm run lint          # ESLint
```

---

## Restrições

- TypeScript strict: true — zero `any` implícito
- Bounding boxes: `pointerEvents: 'none'` no canvas de overlay, zero `onClick`
- Nunca usar `fetch()` diretamente — sempre via `api.ts` (garante JWT injection e tratamento de 401)
- `AnnotationInterface.jsx` — modificar apenas com backup; testar exaustivamente

---

## Componente de Anotação

`src/components/annotation/AnnotationInterface.jsx` é o componente mais complexo da aplicação. Gerencia canvas de anotação, criação de bounding boxes, labels YOLO e export. Modificações devem:
1. Criar backup antes de alterar
2. Testar todos os fluxos de anotação (criar, editar, deletar bbox, export)
3. Verificar performance com imagens > 2MP
