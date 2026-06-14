# Hooks — Custom React Hooks Layer

<!-- Parent: ../AGENTS.md -->

## Overview

Custom React hooks that encapsulate stateful logic and side effects. All hooks follow React 18 best practices with proper cleanup, dependency arrays, and TypeScript strict mode.

**Directory**: `frontend/src/hooks/`

**Files**:
- `useAuth.ts` — Authentication state management
- `usePolling.ts` — Data polling with exponential backoff (REQUIRED for all polling)
- `useMonitoringSocket.ts` — Real-time WebSocket for detections and alerts
- `useModules.ts` — Module system state (feature flags, statistics)

---

## useAuth.ts

### Purpose
Centralized authentication state and operations. Persists user data to `localStorage` for reload survival.

### Key Patterns

```typescript
export interface User {
  id: string
  email: string
  name: string
  role: 'admin' | 'operator'
}

export function useAuth() {
  // Returns: { user, isAuthenticated, login, logout, register }
}
```

### Return Value

| Property | Type | Notes |
|----------|------|-------|
| `user` | `User \| null` | Current authenticated user, persisted in localStorage |
| `isAuthenticated` | `boolean` | `true` if token exists AND user is set |
| `login(email, password)` | Promise | Calls `/auth/login`, stores token + user, redirects to `/` |
| `logout()` | void | Clears token + user, redirects to `/` (NO external API call) |
| `register(name, email, password)` | Promise | Calls `/auth/register`, stores token + user |

### Critical Implementation Details

1. **Token retrieval**: Uses `getToken()` from `services/api.ts` — never directly access `localStorage`
2. **Token storage**: Uses `setToken()` from `services/api.ts` — maintains the `TOKEN_KEY` constant
3. **Logout inline**: Does NOT call `api.logout()` — logout is self-contained (V1 lesson: API logout endpoint may not exist)
4. **Window reload**: After login/register, redirects via `window.location.href = '/'` to force fresh mount and localStorage re-read
5. **localStorage key**: User stored as `JSON.stringify(user)` under key `'user'`, token under key `'token'`

### Usage Example

```typescript
import { useAuth } from '@/hooks/useAuth'

function LoginComponent() {
  const { login, isAuthenticated } = useAuth()

  const handleLogin = async (email: string, password: string) => {
    const user = await login(email, password)
    // Page redirects automatically
  }

  return isAuthenticated ? <Dashboard /> : <LoginForm onSubmit={handleLogin} />
}
```

---

## usePolling.ts

### Purpose
**REQUIRED** for all polling operations. Implements exponential backoff to prevent backend flooding when API is down.

### Key Pattern: Exponential Backoff

- **Success**: Reset to base interval
- **Failure 1**: 2× interval
- **Failure 2**: 4× interval
- **Failure N**: min(base × 2^(N−1), maxInterval)

### Signature

```typescript
export function usePolling(
  fn: () => Promise<void>,
  interval = 5000,  // base interval ms
  options?: { maxInterval?: number; enabled?: boolean }
)
```

### Parameters

| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `fn` | `() => Promise<void>` | — | Async function to poll (should not throw; catch errors internally) |
| `interval` | `number` | `5000` | Base interval in ms (multiplied by backoff factor on each failure) |
| `options.maxInterval` | `number` | `60000` | Max backoff cap (prevents unlimited exponential growth) |
| `options.enabled` | `boolean` | `true` | Pause polling when `false` |

### Behavior

- If `fn()` succeeds: next poll scheduled at base interval, failure counter reset to 0
- If `fn()` throws: failure counter increments, next poll delayed by exponential backoff
- If `enabled=false`: polling paused and cleanup scheduled
- On unmount: all timers cancelled via cleanup function

### Usage Example

```typescript
import { usePolling } from '@/hooks/usePolling'

function CameraStatus({ cameraId }: { cameraId: string }) {
  const [status, setStatus] = useState('unknown')

  usePolling(
    async () => {
      const result = await cameraService.getStatus(cameraId)
      setStatus(result.status)
    },
    5000,
    { maxInterval: 60000, enabled: !!cameraId }
  )

  return <div>{status}</div>
}
```

### Critical Rules

1. **NEVER use raw `setInterval` or `setTimeout` for polling** — use this hook instead
2. **Errors must be caught internally** — `fn()` should not throw; wrap in try/catch
3. **Avoid `async`/`await` in `fn()`** — return a promise, don't use async directly in arrow function body
4. **Dependencies matter**: If `interval` or `maxInterval` changes, polling restarts from scratch
5. **Cleanup automatic**: Timers are cleared on unmount or when `enabled=false`

---

## useMonitoringSocket.ts

### Purpose
Real-time WebSocket connection for camera detections and alerts. Manages socket.io connection, camera subscriptions, and automatic reconnection.

### Interfaces

```typescript
export interface Detection {
  class: string
  confidence: number
  bbox: [number, number, number, number]  // x, y, w, h
  is_violation?: boolean
}

export interface DetectionEvent {
  camera_id: string
  timestamp: string
  detections: Detection[]
  has_violation: boolean
}

export interface AlertEvent {
  id?: string
  camera_id: string
  violations: Detection[]
  created_at?: string
  tenant_id?: string
}
```

### Signature

```typescript
export function useMonitoringSocket({
  wsUrl: string,          // base WS URL (e.g., 'http://localhost:5001')
  token: string,          // JWT token for authentication
  enabled?: boolean       // pause socket when false
})
```

### Return Value

```typescript
{
  connected: boolean              // true if socket connected
  detections: Record<string, Detection[]>  // keyed by camera_id
  alerts: AlertEvent[]            // last 100 alerts
  subscribeCamera(cameraId)        // emit 'subscribe_camera' event
  unsubscribeCamera(cameraId)      // emit 'unsubscribe_camera' event
  clearAlerts()                    // reset alerts array to []
}
```

### Connection Details

- **Namespace**: `/monitor` (e.g., `http://localhost:5001/monitor`)
- **Authentication**: Sends token in query string `?token=...`
- **Transport**: WebSocket only (`transports: ['websocket']`)
- **Auto-reconnect**: Built-in socket.io with exponential backoff (1s–10s)
- **Re-subscribe on reconnect**: Automatically re-emits all subscribed camera IDs after disconnect

### Socket Events

**Emitted by hook**:
- `subscribe_camera`: `{ camera_id: string }` — subscribe to detections for a camera
- `unsubscribe_camera`: `{ camera_id: string }` — stop receiving detections

**Received from server**:
- `detection`: `DetectionEvent` — new detections frame
- `alert`: `AlertEvent` — alert triggered

### Usage Example

```typescript
import { useMonitoringSocket } from '@/hooks/useMonitoringSocket'
import { getToken } from '@/services/api'

function MonitoringDashboard() {
  const { connected, detections, alerts, subscribeCamera } = useMonitoringSocket({
    wsUrl: 'http://localhost:5001',
    token: getToken() || '',
    enabled: true,
  })

  useEffect(() => {
    subscribeCamera('cam-1')
    return () => unsubscribeCamera('cam-1')
  }, [subscribeCamera])

  return (
    <div>
      <p>Connected: {connected ? 'yes' : 'no'}</p>
      {detections['cam-1']?.map(det => (
        <div key={`${det.class}-${det.confidence}`}>
          {det.class}: {(det.confidence * 100).toFixed(1)}%
        </div>
      ))}
    </div>
  )
}
```

### Critical Rules

1. **Token required**: Always provide valid JWT token
2. **Re-subscribe after disconnect**: Hook handles this automatically
3. **Alerts limited to 100**: Oldest alerts are dropped when new ones arrive
4. **Detections per camera**: Access via `detections[camera_id]`
5. **Manual subscription**: Not automatic — call `subscribeCamera()` for each camera
6. **Cleanup on unmount**: Socket disconnected automatically

---

## useModules.ts

### Purpose
Manage module system state (feature flags, statistics per module).

### Interfaces

```typescript
export interface Module {
  id: string
  module_code: string
  enabled: boolean
  cameras_count: number
  alerts_today: number
  config: Record<string, unknown>
}
```

### Return Value

```typescript
{
  modules: Module[]
  loading: boolean
  error: string | null
  hasModule(code: string): boolean      // is module enabled?
  getModule(code: string): Module | undefined
  refresh(): Promise<void>              // reload from API
}
```

### Signature

```typescript
export function useModules() {
  // Loads on mount, returns { modules, loading, error, hasModule, getModule, refresh }
}
```

### Usage Example

```typescript
import { useModules } from '@/hooks/useModules'

function FeatureGate() {
  const { hasModule, loading } = useModules()

  if (loading) return <LoadingSpinner />
  if (!hasModule('epi')) return <div>EPI module not available</div>

  return <EpiDashboard />
}
```

### Key Details

1. **Loads on mount**: `useEffect([])` triggers initial load
2. **Feature flags**: Use `hasModule(code)` to check if feature is enabled
3. **Error handling**: Errors stored in `error` state, not thrown
4. **Manual refresh**: Call `refresh()` to reload from API
5. **Module lookup**: `getModule(code)` returns full module object or `undefined`

---

## Common Patterns

### Using useAuth + usePolling Together

```typescript
function CameraMonitor() {
  const { user, isAuthenticated } = useAuth()
  const [status, setStatus] = useState('loading')

  usePolling(
    async () => {
      if (!isAuthenticated) return
      const result = await cameraService.getStatus(cameraId)
      setStatus(result.status)
    },
    5000,
    { enabled: isAuthenticated }
  )

  return isAuthenticated ? <div>{status}</div> : <LoginPage />
}
```

### Using useMonitoringSocket + useAuth

```typescript
function MonitoringPage() {
  const { isAuthenticated } = useAuth()
  const { connected, detections } = useMonitoringSocket({
    wsUrl: import.meta.env.VITE_WS_URL || 'http://localhost:5001',
    token: getToken() || '',
    enabled: isAuthenticated,
  })

  return isAuthenticated ? <Dashboard detections={detections} /> : null
}
```

---

## Testing Hooks

**Note**: Hooks are tested via component integration tests, not unit tests. Use `render()` from `@testing-library/react` and `waitFor()` for assertions.

Example:
```typescript
import { render, screen, waitFor } from '@testing-library/react'

it('loads user on mount', async () => {
  const { result } = renderHook(() => useAuth())
  await waitFor(() => expect(result.current.user).toBeDefined())
})
```

---

## Performance Considerations

- **usePolling**: Only runs when `enabled=true`; timers cleaned up on unmount
- **useMonitoringSocket**: Single socket instance per hook; reconnection handled by socket.io
- **useAuth**: Reads from localStorage on every call to `getToken()` (fast, no network)
- **useModules**: Loads once on mount; call `refresh()` manually to reload

---

## Error Handling

All hooks handle errors gracefully:
- **useAuth**: Errors thrown to caller (login/register fail)
- **usePolling**: Errors caught internally; backoff applied
- **useMonitoringSocket**: Errors logged, socket reconnects automatically
- **useModules**: Errors stored in `error` state, not thrown

---

*Last updated: April 2026 — EPI Monitor V2*
