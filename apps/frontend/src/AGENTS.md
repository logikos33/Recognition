<!-- Parent: ../AGENTS.md -->

# frontend/src — Agent Guide

**Generated**: 2026-04-09

This directory contains the **React 18 + TypeScript SPA** for EPI Monitor V2. It is a single-page application with client-side routing, WebSocket real-time detections, and HLS video streaming.

**Architecture**: Custom hooks (state management) → Service layer (API calls) → Components (presentation)

---

## Directory Structure

```
src/
├── App.tsx                    # Main routing + auth gate (MAX 100 lines)
├── AppRoutes.tsx              # Route definitions (extracted from App.tsx)
├── main.tsx                   # React DOM entry point
├── index.css                  # Global styles
├── components/                # Reusable React components
│   ├── annotation/            # FROZEN: AnnotationInterface.jsx
│   ├── cameras/               # Camera CRUD components
│   ├── monitoring/            # HLS player + detection overlay
│   ├── shared/                # ErrorBoundary, LoadingSpinner, etc.
│   └── training/              # Training UI components
├── hooks/                     # Custom React hooks (state management)
│   ├── useAuth.ts             # Login/logout/register + localStorage
│   ├── usePolling.ts          # Exponential backoff polling (REQUIRED)
│   ├── useMonitoringSocket.ts # WebSocket connection + subscriptions
│   └── useModules.ts          # Feature flags / module management
├── services/                  # API client layer + domain services
│   ├── api.ts                 # HTTP client (auth header injection)
│   ├── cameraService.ts       # Camera CRUD + test
│   ├── moduleService.ts       # Module enable/disable
│   └── reportService.ts       # Excel export
├── pages/                     # Route-level page components
│   ├── Login.tsx              # Auth page
│   ├── HomePage.tsx           # Dashboard home
│   ├── DashboardPage.tsx      # KPIs dashboard
│   ├── CamerasPage.tsx        # Camera management
│   ├── MonitoringPage.tsx     # HLS monitoring
│   ├── AlertsHistoryPage.tsx  # Alert history
│   ├── AnnotationPage.tsx     # Video annotation
│   ├── TrainingPage.tsx       # Model training
│   ├── epi/                   # EPI-specific modules
│   │   ├── EpiDashboard.tsx
│   │   ├── EpiCameras.tsx
│   │   └── EpiAlerts.tsx
│   └── fueling/               # Fueling module (placeholder)
└── types/                     # TypeScript interfaces
    └── index.ts               # Shared types (User, Camera, Alert, etc.)
```

---

## Core Patterns

### 1. HTTP Client Layer (services/api.ts)

**Pattern**: Centralized fetch wrapper with automatic auth header injection.

```typescript
// ✅ Always use api.* methods
const res = await api.get<ApiResponse<Camera[]>>('/cameras')

// ❌ Never use fetch directly
const res = await fetch(...)
```

**Key facts:**
- `TOKEN_KEY = 'token'` — single source of truth for token storage
- `getToken()` — always call this to get current token
- `setToken(t)` — always call this after login
- `removeToken()` — always call this on logout
- All requests auto-add `Authorization: Bearer <token>` header
- 15-second timeout on every request (AbortController)
- Response format: `{ success: true, data: {...} }` or error thrown

**Usage pattern:**
```typescript
const res = await api.get<ApiResponse<any>>('/cameras')
const data = res.data as Camera[]  // Access via res.data
```

---

### 2. Auth Hook (hooks/useAuth.ts)

**Pattern**: Custom hook that manages login state + localStorage persistence.

```typescript
const { user, isAuthenticated, login, logout, register } = useAuth()

// Login
await login(email, password)  // setToken() + localStorage + reload

// Logout
logout()  // removeToken() + localStorage.clear() + reload

// Check auth
if (!isAuthenticated) return <Login />
```

**Key facts:**
- `user` is initialized from localStorage on mount (survives page reload)
- `login()` calls `setToken()` internally and reloads page
- `logout()` is **inline** — never calls external `api.logout()`
- After login, page reloads so new App instance reads fresh token from localStorage

---

### 3. Polling Hook (hooks/usePolling.ts) — REQUIRED

**Pattern**: Exponential backoff polling for any data that needs to refresh.

```typescript
// ✅ CORRECT: use usePolling hook
usePolling(
  async () => {
    const res = await api.get('/cameras')
    setCameras(res.data)
  },
  5000,  // base interval 5s
  { maxInterval: 60000, enabled: true }
)

// ❌ WRONG: raw setInterval (floods backend when it crashes)
setInterval(() => { ... }, 5000)
```

**Behavior:**
- Success → reset to base interval
- Fail 1 → 2x interval (10s)
- Fail 2 → 4x interval (20s)
- Fail N → min(base * 2^N, maxInterval) — caps at 60s by default

---

### 4. WebSocket Hook (hooks/useMonitoringSocket.ts)

**Pattern**: Real-time detections via Socket.IO + automatic subscriptions.

```typescript
const { connected, detections, alerts, subscribeCamera, unsubscribeCamera } =
  useMonitoringSocket({
    wsUrl: 'https://api.example.com',
    token: getToken(),
    enabled: !!token
  })

// Subscribe to camera events
subscribeCamera('camera-1')

// Access detections
const boxes = detections['camera-1'] || []  // Detection[]
```

**Message types:**
- `detection` — real-time bounding boxes `{ camera_id, detections: [{class, confidence, bbox}] }`
- `alert` — violation alerts `{ camera_id, violations: [{class, confidence}] }`

**Auto-reconnection**: Built-in exponential backoff, max 10s between attempts.

---

### 5. Service Layer Pattern (services/*.ts)

**Pattern**: Domain-specific services that wrap api.* calls with type safety.

```typescript
// cameraService.ts example
export const cameraService = {
  async list(): Promise<Camera[]> {
    const res = await api.get<ApiResponse<ApiListResponse>>('/cameras')
    return res.data.cameras
  },

  async create(data: CameraFormData): Promise<Camera> {
    const res = await api.post<ApiResponse<Camera>>('/cameras', formToApiPayload(data))
    return res.data
  },

  async test(id: string): Promise<TestResult> {
    const res = await api.post<ApiResponse<TestResult>>(`/cameras/${id}/test`)
    return res.data
  },
}
```

**Key facts:**
- Form data → API payload mapping is centralized (e.g., 'ip' → 'host')
- All RTSP URL generation logic lives here (`buildRtspPreview`)
- Passwords **never** returned by API, so never expose them in frontend

---

## Components Structure

### Shared Components (components/shared/)

| Component | Purpose |
|-----------|---------|
| `ErrorBoundary` | Catches React errors, shows fallback UI with retry button |
| `LoadingSpinner` | Loading indicator (circular spinner) |
| `StatusBadge` | Color-coded status indicator (active/inactive/error) |

**ErrorBoundary usage:**
```typescript
<ErrorBoundary fallback={<CustomError />}>
  <MyComponent />
</ErrorBoundary>
```

---

### Monitoring Components (components/monitoring/)

#### CameraPlayer
- **Props**: `cameraId`, `hlsUrl`, `width`, `height`
- **Purpose**: HLS video player using hls.js
- **Features**:
  - Automatic hls.js initialization
  - Safari native HLS support fallback
  - Error state handling
  - Loading spinner
- **Muted by default** (autoPlay + muted + playsInline)

```typescript
<CameraPlayer
  cameraId="cam-1"
  hlsUrl="/api/cameras/cam-1/stream/stream.m3u8"
  width={640}
  height={360}
/>
```

#### DetectionOverlay
- **Props**: `detections[]`, `videoWidth`, `videoHeight`, `displayWidth`, `displayHeight`
- **Purpose**: Canvas overlay for real-time bounding boxes
- **CRITICAL RULES**:
  - All boxes must have `pointerEvents: 'none'`
  - **NEVER** add onClick handlers to boxes
  - Mouse events handled mathematically in container `handleMouseDown`
  - `handleFrameChange` must be `async` with `await`

---

### Camera Components (components/cameras/)

#### CameraCard
- **Props**: Camera object + action callbacks (edit, delete, test, start, stop)
- **Purpose**: Card component for camera display in list

#### CameraWizard
- **Props**: onComplete callback
- **Purpose**: Multi-step form for camera creation
- **Steps**:
  1. Manufacturer selection
  2. IP + port + credentials
  3. Stream test (calls `cameraService.test()`)
  4. Name + location (optional)

---

### Annotation Component (components/annotation/)

**FROZEN RULE**: `AnnotationInterface.jsx` is completely frozen.

- Never modify its code
- Never rename it
- Never move it
- Never add/remove props
- Any integration must adapt to its existing interface

**Pre-annotation Controls** (`PreAnnotationControls.tsx`):
- Quality filters
- Frame selection

---

## Pages Structure

### Authentication

#### Login.tsx
- Email + password fields
- Register toggle
- Calls `useAuth().login()` or `useAuth().register()`

### Dashboard Pages

#### HomePage.tsx
- System overview
- Quick stats
- Navigation

#### DashboardPage.tsx
- KPIs charts (Recharts)
- System metrics
- Health status

### Monitoring

#### MonitoringPage.tsx
- **Left sidebar**: Camera list + alerts panel
- **Main area**: HLS player + detection overlay
- **Query param**: `?camera=<id>` pre-selects camera
- Uses `useMonitoringSocket()` for real-time detections
- Auto-subscribes/unsubscribes from WebSocket on camera change

```typescript
// Camera selection via query params
const [searchParams] = useSearchParams()
const selectedId = searchParams.get('camera')
```

#### AlertsHistoryPage.tsx
- Paginated alert list
- Filtering + search
- Calls polling hook to fetch alerts periodically

### Annotation

#### AnnotationPage.tsx
- Video upload
- Frame extraction
- AnnotationInterface embedding
- Training label export

### Training

#### TrainingPage.tsx
- Model selection (preset + size)
- Training job submission
- Progress tracking via polling
- Job status display

---

## TypeScript Types (types/index.ts)

**All types are defined in one file** for discoverability.

### User
```typescript
interface User {
  id: string
  email: string
  name: string
  role: 'admin' | 'operator'
}
```

### Camera
```typescript
interface Camera {
  id: string
  user_id?: string
  name: string
  manufacturer: string
  host: string
  port: number
  username?: string
  channel: number
  rtsp_url_override?: string
  is_active: boolean
  stream_status?: string
  last_seen?: string
  last_error?: string
  created_at: string
}
```

### Detection (real-time)
```typescript
interface Detection {
  class: string
  confidence: number
  bbox: [number, number, number, number]  // x, y, w, h
  is_violation?: boolean
}

interface DetectionEvent {
  camera_id: string
  timestamp: string
  detections: Detection[]
  has_violation: boolean
}
```

### Alert
```typescript
interface Alert {
  id: string
  camera_id: string
  timestamp: string
  violations: Array<{ class: string; confidence: number }>
  confidence: number
  acknowledged: boolean
}
```

### API Response
```typescript
interface ApiResponse<T> {
  success: boolean
  message?: string
  data?: T
  error?: string
}
```

---

## Routing (AppRoutes.tsx)

All routes defined in one extracted component to keep App.tsx < 100 lines.

```typescript
<Routes>
  <Route path="/" element={<HomePage />} />
  <Route path="/dashboard" element={<DashboardPage />} />
  <Route path="/cameras" element={<CamerasPage />} />
  <Route path="/monitoring" element={<MonitoringPage />} />
  <Route path="/alerts" element={<AlertsHistoryPage />} />
  <Route path="/annotation" element={<AnnotationPage />} />
  <Route path="/training" element={<TrainingPage />} />
  <Route path="/epi/dashboard" element={<EpiDashboard />} />
  <Route path="/epi/cameras" element={<EpiCameras />} />
  <Route path="/epi/alerts" element={<EpiAlerts />} />
  <Route path="/fueling/*" element={<FuelingPlaceholder />} />
  <Route path="*" element={<Navigate to="/" replace />} />
</Routes>
```

Every route is wrapped in `<ErrorBoundary>` for graceful error handling.

---

## Common Patterns

### Loading State with Polling

```typescript
const [cameras, setCameras] = useState<Camera[]>([])
const [loading, setLoading] = useState(false)

usePolling(
  async () => {
    setLoading(true)
    try {
      const list = await cameraService.list()
      setCameras(list)
    } finally {
      setLoading(false)
    }
  },
  5000,
  { enabled: true }
)

return loading ? <LoadingSpinner /> : <div>{/* render cameras */}</div>
```

### Error Handling in Components

```typescript
const [error, setError] = useState<string | null>(null)

const handleAction = async () => {
  try {
    await cameraService.create(formData)
    // success
  } catch (err) {
    setError((err as Error).message)
  }
}

return error && <div style={{ color: '#dc2626' }}>{error}</div>
```

### Form Data Transformation

```typescript
// In cameraService.ts: isolate the form→API mapping
function formToApiPayload(data: Partial<CameraFormData>): Record<string, unknown> {
  const payload: Record<string, unknown> = {}
  if (data.name !== undefined) payload.name = data.name
  if (data.ip !== undefined) payload.host = data.ip  // ← mapping
  if (data.password !== undefined) payload.password = data.password
  return payload
}

// In component: always use the service
const camera = await cameraService.create(formData)
```

### Real-time Detection Overlay

```typescript
const { connected, detections } = useMonitoringSocket({ wsUrl, token, enabled: true })
const boxes = detections[activeCameraId] || []

return (
  <div style={{ position: 'relative' }}>
    <CameraPlayer hlsUrl={...} />
    <DetectionOverlay
      detections={boxes}
      videoWidth={640}
      videoHeight={360}
      displayWidth={640}
      displayHeight={360}
    />
  </div>
)
```

---

## Absolute Rules — NEVER Violate

### 1. Authentication

```typescript
// ✅ CORRECT: use getToken() from api.ts
const token = getToken()

// ❌ WRONG: hardcode or fetch from window
const token = window.__token__
```

```typescript
// ✅ CORRECT: setToken after login
setToken(response.token)

// ❌ WRONG: localStorage.setItem('token', ...)
localStorage.setItem('token', token)
```

### 2. Polling

```typescript
// ✅ CORRECT: use usePolling hook
usePolling(async () => { await fetchData() }, 5000)

// ❌ WRONG: raw setInterval
setInterval(() => { ... }, 5000)
```

### 3. Bounding Boxes

```typescript
// ✅ CORRECT: pointerEvents='none' on all boxes
<div style={{ pointerEvents: 'none' }}>
  <rect x={...} y={...} width={...} height={...} />
</div>

// ❌ WRONG: onClick on boxes
<rect onClick={handleBoxClick} {...} />
```

### 4. Components

```typescript
// ✅ CORRECT: AnnotationInterface stays frozen
// Just embed it, never touch its code
<AnnotationInterface {...props} />

// ❌ WRONG: modify AnnotationInterface.jsx
// (Never happens — it's read-only)
```

### 5. TypeScript

```typescript
// ✅ CORRECT: strict types, no implicit any
const res: ApiResponse<Camera> = await api.get('/camera')

// ❌ WRONG: implicit any
const res = await api.get('/camera')  // res: unknown
```

### 6. Logging

```typescript
// ✅ CORRECT: no console.log in production code
// Use error states instead

// ❌ WRONG: debug logs left in
console.log('camera:', camera)
```

### 7. Vite Configuration

```typescript
// vite.config.ts MUST have:
export default defineConfig({
  server: {
    usePolling: true,
    cacheDir: '/tmp/vite-cache-epi'  // Path has space in project
  }
})
```

---

## Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `VITE_API_URL` | Base URL for API calls | `https://api.example.com` |
| `VITE_WS_URL` | Base URL for WebSocket | `https://api.example.com` |

In development:
```bash
# .env.local
VITE_API_URL=http://localhost:5001
VITE_WS_URL=http://localhost:5001
```

In production:
```bash
# .env.production
VITE_API_URL=https://api.railway.app
VITE_WS_URL=https://api.railway.app
```

If not set, defaults to current origin (for vite proxy to work).

---

## Testing & Validation

### Type Check
```bash
tsc --noEmit
```

### Linting
```bash
eslint src/
```

### Dev Server
```bash
npm run dev
# Watches for changes, auto-reload
# Proxy: /api → http://localhost:5001/api
```

### Build
```bash
npm run build
# Output: dist/
# Optimized for production
```

---

## Common Issues

### "Token is missing" on every request
- Check: `getToken()` returns null
- Fix: Call `login()` first, verify token saved to localStorage

### WebSocket "Handshake failed" with 401
- Check: Token expired or invalid
- Fix: Call `logout()` then `login()` again

### HLS player black screen
- Check: `hlsUrl` is correct
- Check: Browser supports HLS (use hls.js)
- Fix: Check browser console for CORS errors

### "Cannot read property 'data'" after API call
- Check: Response structure: `{ success, data: {...} }`
- Fix: Access via `res.data`, not `res.result` or `res.payload`

### Polling never stops even after component unmounts
- Check: `usePolling` cleanup function running
- Fix: Verify `enabled` prop and useEffect dependencies

### Canvas overlay misaligned with video
- Check: Video dimensions match overlay `videoWidth/videoHeight`
- Fix: Ensure canvas wrapper has `position: 'relative'` and no scaling

---

## Checklist for Adding New Features

- [ ] Types defined in `types/index.ts`
- [ ] Service method in `services/*.ts`
- [ ] Page or component created
- [ ] Auth guard applied (check user in component)
- [ ] Error boundary wraps the route
- [ ] Polling hook used if data needs refresh
- [ ] WebSocket subscribed if real-time needed
- [ ] No console.log left in code
- [ ] No hardcoded API URLs
- [ ] TypeScript strict mode passes
- [ ] Component < 200 lines (split if larger)

---

## Related Documentation

- Parent: `/frontend/AGENTS.md` (project-level frontend guide)
- Backend: `/backend/AGENTS.md` (API + Worker services)
- Project: `/CLAUDE.md` (architecture & deployment)

