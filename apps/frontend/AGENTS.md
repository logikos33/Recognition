<!-- Parent: ../CLAUDE.md -->
<!-- Generated: 2026-04-09 -->

# Frontend — EPI Monitor V2 React SPA

**Purpose**: React 18 TypeScript Single Page Application for EPI monitoring. Runs via `npm run dev` (Vite) or `npm run build` → dist/ (production). Connects to backend API via centralized `src/services/api.ts`. Real-time updates via WebSocket (socket.io-client).

**Tech Stack**: React 18, TypeScript, Vite, React Router, socket.io-client, hls.js

**Deployment**: Vite static build served by Flask (see `/app/__init__.py` `_register_frontend_serving`) or nginx.

---

## Directory Structure

```
frontend/
├── src/
│   ├── App.tsx                   # Root component, max 100 lines
│   ├── AppRoutes.tsx             # Route definitions (Router setup)
│   ├── main.tsx                  # Vite entry point
│   ├── index.css                 # Global styles
│   ├── components/               # Reusable components
│   │   ├── annotation/           # AnnotationInterface.jsx (FROZEN — never modify)
│   │   ├── monitoring/           # CameraGrid, HLSPlayerComponent
│   │   ├── training/             # FrameQueue, ProgressBar
│   │   ├── upload/               # VideoUpload, UploadProgress
│   │   ├── rules/                # RuleBuilder, RuleList
│   │   ├── dashboard/            # KPIChart, SessionsTable
│   │   ├── shared/               # Button, Modal, NavBar, ErrorBoundary
│   │   └── layout/               # Layout, Sidebar
│   ├── hooks/                    # Custom hooks (state management)
│   │   ├── useAuth.ts            # User state, login/logout, token management
│   │   ├── usePolling.ts         # Exponential backoff polling (REQUIRED)
│   │   ├── useSocket.ts          # WebSocket connection lifecycle
│   │   ├── useCameraStream.ts    # HLS player state
│   │   ├── useTraining.ts        # Training job state
│   │   └── useApi.ts             # API call wrapper with error handling
│   ├── pages/                    # Page components (one per route)
│   │   ├── LoginPage.tsx
│   │   ├── DashboardPage.tsx
│   │   ├── CamerasPage.tsx
│   │   ├── TrainingPage.tsx
│   │   ├── AnnotationPage.tsx    # Calls AnnotationInterface
│   │   ├── RulesPage.tsx
│   │   ├── ReportsPage.tsx
│   │   └── 404.tsx
│   ├── services/                 # API client and external integrations
│   │   ├── api.ts                # REST client (Authorization header injection)
│   │   ├── websocket.ts          # Socket.io connection management
│   │   ├── storage.ts            # localStorage wrapper (tokens, preferences)
│   │   ├── formatters.ts         # Date, time, number formatting
│   │   └── errorHandler.ts       # Centralized error handling
│   ├── types/                    # TypeScript interfaces
│   │   ├── camera.ts             # Camera, Detection, StreamStatus
│   │   ├── video.ts              # Video, Frame, Quality metrics
│   │   ├── training.ts           # TrainingJob, ModelVersion
│   │   ├── user.ts               # User, JwtPayload
│   │   ├── rules.ts              # Rule, RuleTemplate
│   │   └── api.ts                # ApiResponse, ApiError
│   └── stores/                   # Context API (only when needed, avoid Redux)
│       ├── AuthContext.tsx
│       └── NotificationContext.tsx
├── dist/                         # Build output (npm run build)
├── public/                       # Static files
├── package.json                  # Dependencies, scripts
├── tsconfig.json                 # strict: true (REQUIRED)
├── tsconfig.node.json            # Vite config TypeScript
├── vite.config.ts                # server.usePolling: true (path with spaces)
├── index.html                    # Entry HTML
├── serve.py                      # Local dev server (Python, serve dist/)
├── nginx.conf                    # Production nginx config
├── Dockerfile.frontend           # Build image
├── nixpacks.toml                 # Railway build config
├── railway.toml                  # Railway deploy config
└── .env.local                    # Environment (gitignored)
```

---

## Key Files Reference

| File | Purpose | Critical Rules |
|------|---------|-----------------|
| `src/App.tsx` | Root component | Max 100 lines, routes in AppRoutes.tsx, global layout |
| `src/AppRoutes.tsx` | Route definitions | All `<Route>` definitions, lazy load pages |
| `src/services/api.ts` | REST client | Centralized, auto Authorization header, error handling |
| `src/hooks/useAuth.ts` | Auth state | Token in localStorage key `token`, `getToken()` exported |
| `src/hooks/usePolling.ts` | Polling hook | REQUIRED for all polling, exponential backoff |
| `src/pages/` | Page components | Each route gets one page, max 300 lines |
| `src/components/` | Reusable components | Max 200 lines, split if larger |
| `src/types/` | TypeScript interfaces | One file per domain, no `any` implicitly |
| `tsconfig.json` | TypeScript config | `strict: true` (zero implicit any) |
| `vite.config.ts` | Vite config | `server.usePolling: true` for path with spaces |

---

## Core Patterns

### 1. Centralized API Client
```typescript
// src/services/api.ts
const api = {
  async request(method: string, path: string, data?: unknown) {
    const token = getToken()
    const response = await fetch(BASE_URL + path, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      },
      body: data ? JSON.stringify(data) : undefined
    })
    if (!response.ok) throw new ApiError(...)
    return response.json()
  },
  get: (path: string) => api.request('GET', path),
  post: (path: string, data: unknown) => api.request('POST', path, data),
  put: (path: string, data: unknown) => api.request('PUT', path, data),
  delete: (path: string) => api.request('DELETE', path)
}

export const getToken = () => localStorage.getItem('token')
export const setToken = (token: string) => localStorage.setItem('token', token)
```

**Benefit**: Single point for auth header injection, error handling.

### 2. Custom Hooks (State Management)
```typescript
// src/hooks/useAuth.ts
export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(false)

  const login = async (email: string, password: string) => {
    setLoading(true)
    try {
      const { user, token } = await api.post('/api/v1/auth/login', { email, password })
      setToken(token)
      setUser(user)
    } finally {
      setLoading(false)
    }
  }

  return { user, login, logout }
}
```

**Benefit**: Component-level state, no Redux, reusable across pages.

### 3. Polling with Exponential Backoff
```typescript
// src/hooks/usePolling.ts
export function usePolling(
  fn: () => Promise<void>,
  interval: number,
  options?: { maxInterval?: number, enabled?: boolean }
) {
  useEffect(() => {
    if (options?.enabled === false) return
    
    let timeoutId: NodeJS.Timeout
    let backoffInterval = interval
    
    const poll = async () => {
      try {
        await fn()
        backoffInterval = interval // reset on success
      } catch (error) {
        backoffInterval = Math.min(backoffInterval * 1.5, options?.maxInterval ?? 60000)
      } finally {
        timeoutId = setTimeout(poll, backoffInterval)
      }
    }
    
    poll()
    return () => clearTimeout(timeoutId)
  }, [fn, interval, options])
}

// Usage in component
usePolling(async () => {
  const cameras = await api.get('/api/v1/cameras')
  setCameras(cameras)
}, 5000)
```

**Mandatory**: Never use raw `setInterval` — always use this hook.

### 4. WebSocket Connection
```typescript
// src/hooks/useSocket.ts
export function useSocket() {
  const [socket, setSocket] = useState<Socket | null>(null)

  useEffect(() => {
    const io = require('socket.io-client')
    const s = io(BASE_URL, {
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5
    })

    s.on('detection', (data: Detection) => {
      // Handle detection
    })

    setSocket(s)
    return () => s.disconnect()
  }, [])

  return socket
}
```

**Benefit**: Auto-reconnect with exponential backoff.

### 5. Component Size Limits
```typescript
// ✅ GOOD — under 200 lines, single responsibility
export function CameraCard({ camera }: Props) {
  const [loading, setLoading] = useState(false)
  const handleDelete = async () => { ... }
  return (
    <div>
      <h3>{camera.name}</h3>
      <button onClick={handleDelete}>Delete</button>
    </div>
  )
}

// ❌ BAD — over 200 lines, mix of concerns
export function CamerasPage() {
  // 100 lines of CRUD + 100 lines of display + 50 lines of filtering
}

// ✅ REFACTORED
export function CamerasPage() {
  const { cameras, deleteCamera } = useCameras()
  return (
    <div>
      {cameras.map(cam => <CameraCard key={cam.id} camera={cam} onDelete={deleteCamera} />)}
    </div>
  )
}
```

### 6. Error Handling
```typescript
// src/services/errorHandler.ts
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string
  ) {
    super(message)
  }
}

// In component
try {
  await api.post('/api/v1/cameras', data)
} catch (error) {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      // Handle auth error
      logout()
    } else {
      // Show user message
      toast.error(error.message)
    }
  }
}
```

### 7. TypeScript Strict Mode
```typescript
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true
  }
}

// ✅ CORRECT — types explicit
function handleClick(e: React.MouseEvent<HTMLButtonElement>): void {
  const target = e.currentTarget as HTMLButtonElement
  console.log(target.id)
}

// ❌ WRONG — implicit any
function handleClick(e) { // error: no implicit any
  console.log(e.currentTarget.id)
}
```

---

## For AI Agents

### When adding a new page:

1. **Create component** in `src/pages/{FeatureName}Page.tsx`
   - Keep under 300 lines
   - Use custom hooks for state management
   - Import API functions from `src/services/api.ts`

2. **Add route** in `src/AppRoutes.tsx`
   - Lazy load: `const XyzPage = lazy(() => import(...))`
   - Wrap in `<Suspense fallback={<Loading />}`

3. **Create types** in `src/types/{feature}.ts`
   - Interface definitions matching API responses

4. **Create hooks** if complex state
   - One per concern: `useCamera.ts`, `useTraining.ts`
   - Export custom hooks, not raw useState

### When fetching data:

```typescript
// ✅ CORRECT — use api.ts client
const [cameras, setCameras] = useState<Camera[]>([])
usePolling(async () => {
  const data = await api.get('/api/v1/cameras')
  setCameras(data)
}, 5000)

// ❌ WRONG — fetch directly
const [cameras, setCameras] = useState([])
useEffect(() => {
  setInterval(() => {
    fetch('http://localhost:5001/api/v1/cameras')
      .then(r => r.json())
      .then(setCameras)
  }, 5000)
}, [])
```

### Common pitfalls:

- ❌ `setInterval` for polling → use `usePolling` hook
- ❌ Token in state → store in `localStorage` with `setToken()`
- ❌ `fetch()` directly → use `api.ts` client (auth header missing!)
- ❌ Component >200 lines → split into smaller components
- ❌ `App.tsx` >100 lines → move routes to `AppRoutes.tsx`
- ❌ `any` type → add proper TypeScript interface
- ❌ Modifying `AnnotationInterface.jsx` → FROZEN, never touch
- ❌ `console.log` in production code → remove or use structured logging

### Testing:

```typescript
// src/__tests__/services/api.test.ts
describe('api.ts', () => {
  it('adds Authorization header if token present', async () => {
    localStorage.setItem('token', 'test-token')
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true })
    })

    await api.get('/test')

    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          'Authorization': 'Bearer test-token'
        })
      })
    )
  })
})
```

### Build and serve:

```bash
# Development
npm run dev        # Vite on :3000

# Production
npm run build      # Creates dist/
python serve.py    # Serves dist/ on :5000
```

### Vite configuration quirk:

The project path has spaces (`EPI - CATH V2`), so `vite.config.ts` must include:

```typescript
export default defineConfig({
  server: {
    usePolling: true,           // Required for path with spaces
    cacheDir: '/tmp/vite-cache' // Optional, faster builds
  }
})
```

---

## Environment Variables

Create `.env.local` in frontend root:

```bash
VITE_API_URL=http://localhost:5001        # dev
VITE_API_URL=https://your-api.railway.app # production
```

Access in code:

```typescript
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5001'
```

---

## AnnotationInterface.jsx — FROZEN

**Never modify this component.** It has:
- Specific props contract
- Canvas-based annotation UI
- Integration with training pipeline
- The frontend team depends on its interface

If you need to integrate with it, adapt your code to its contract, don't change it.

---

## References

- **Vite docs**: https://vitejs.dev
- **React 18 docs**: https://react.dev
- **TypeScript strict mode**: https://www.typescriptlang.org/tsconfig#strict
- **socket.io-client docs**: https://socket.io/docs/v4/client-api/
