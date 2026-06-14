# Services — API Client and Business Logic Layer

<!-- Parent: ../AGENTS.md -->

## Overview

Service layer that encapsulates HTTP communication and domain-specific operations. All HTTP requests flow through `api.ts`, which manages token injection, timeouts, and error handling.

**Directory**: `frontend/src/services/`

**Files**:
- `api.ts` — Centralized HTTP client (THE entry point for all fetch calls)
- `cameraService.ts` — Camera CRUD and streaming operations
- `moduleService.ts` — Module system (features, statistics)
- `reportService.ts` — Dashboard reports and KPIs

---

## api.ts — Centralized HTTP Client

### Purpose
**Single point of entry** for all HTTP requests. Handles token injection, timeout enforcement, and standardized error responses.

### Constants

```typescript
export const TOKEN_KEY = 'token'  // localStorage key for JWT
```

### Token Management Functions

```typescript
export const getToken = (): string | null        // read from localStorage
export const setToken = (t: string) => void      // write to localStorage
export const removeToken = () => void            // clear token + user from localStorage
```

### Key Rules

1. **NEVER hardcode token key** — always use `TOKEN_KEY` constant
2. **Token ALWAYS via `getToken()`** — never `localStorage.getItem('token')` directly
3. **Token set ONLY via `setToken()`** — called from `useAuth` after login/register
4. **Token removed ONLY via `removeToken()`** — called from `useAuth.logout()`

### Request Function

```typescript
async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T>
```

**Implementation**:
- Injects `Authorization: Bearer {token}` header (if token exists)
- Sets `Content-Type: application/json`
- 15-second timeout via AbortController
- Throws error if response not OK (via `res.ok` check)

**Base URL**:
- Development: `/api` (proxied by Vite)
- Production: `${VITE_API_URL}/api` (env var from Railway)

### API Methods

```typescript
export const api = {
  get:    <T>(path: string)              => request<T>('GET', path),
  post:   <T>(path: string, body?)       => request<T>('POST', path, body),
  put:    <T>(path: string, body?)       => request<T>('PUT', path, body),
  delete: <T>(path: string)              => request<T>('DELETE', path),
}
```

### Response Format

The API returns responses in this format:
```typescript
{
  success: boolean
  message?: string
  data?: T          // The actual payload — access via res.data
  error?: string
}
```

**Critical**: Always access the payload via `res.data`, not directly from `res`.

### Usage Pattern

```typescript
import { api, getToken, setToken, removeToken } from '@/services/api'

// Login — set token
const res = await api.post<{ data: { token: string; user: User } }>('/auth/login', {
  email, password
})
setToken(res.data.token)

// List cameras — token auto-injected
const res = await api.get<{ data: { cameras: Camera[] } }>('/cameras')
const cameras = res.data.cameras

// Logout — remove token
removeToken()

// Check token
if (getToken()) {
  // User is logged in
}
```

### Error Handling

- **Network timeout** (15s): AbortError thrown
- **HTTP error** (4xx, 5xx): Error thrown with `data.error` message
- **JSON parse error**: Error thrown during `res.json()`
- **No token**: Authorization header omitted (public endpoints work)

**Never** use try/catch at the api level — handle errors in services or components.

---

## cameraService.ts

### Purpose
Camera CRUD operations and stream control. Manages form↔API payload translation (e.g., `ip` → `host`).

### Interfaces

```typescript
export interface CameraFormData {
  name: string
  ip: string
  port: number
  username: string
  password: string
  path: string                 // RTSP path override
  manufacturer: string         // hikvision, dahua, intelbras, axis, samsung, generic
  location?: string
}

export interface TestResult {
  camera_id: string
  success: boolean
  error: string | null
  suggestion: string | null
  checks: {
    url_format: TestCheck
    host_reachable: TestCheck
    port_open: TestCheck
    rtsp_response: TestCheck
    stream_available: TestCheck
  }
}
```

### API Methods

```typescript
export const cameraService = {
  // Retrieve all cameras for current user
  list(): Promise<Camera[]>

  // Get single camera by ID
  get(id: string): Promise<Camera>

  // Create new camera (returns full Camera object)
  create(data: CameraFormData): Promise<Camera>

  // Update camera (returns full Camera object)
  update(id: string, data: Partial<CameraFormData>): Promise<Camera>

  // Delete camera
  delete(id: string): Promise<void>

  // Test RTSP connectivity and permissions
  test(id: string): Promise<TestResult>

  // Start HLS stream + YOLO inference
  start(id: string): Promise<void>

  // Stop stream
  stop(id: string): Promise<void>
}
```

### Key Details

#### Form to API Mapping

When calling `create()` or `update()`, form fields are mapped to API fields:

| Form Field | API Field | Notes |
|-----------|-----------|-------|
| `ip` | `host` | IP address of camera |
| `path` | `rtsp_url_override` | Optional RTSP path override |
| `manufacturer` | `manufacturer` | Used to generate default path |
| `port` | `port` | RTSP port (usually 554) |
| `username` | `username` | Optional auth username |
| `password` | `password` | Optional auth password |
| `name` | `name` | Display name |
| `location` | `location` | Physical location |

#### RTSP URL Generation

```typescript
export function buildRtspPreview(data: Partial<CameraFormData>): string
```

Builds preview URL for user display (never makes HTTP request):
- If `path` provided: returns path as-is
- Otherwise: constructs `rtsp://[user]:*****@[ip]:[port][default_path]`
- Passwords always masked as `****` in preview

#### Default RTSP Paths by Manufacturer

```typescript
hikvision:  '/Streaming/Channels/101'
dahua:      '/cam/realmonitor?channel=1&subtype=0'
intelbras:  '/cam/realmonitor?channel=1&subtype=1'
axis:       '/axis-media/media.amp'
samsung:    '/profile1/media.smp'
generic:    '/stream'
```

### Usage Example

```typescript
import { cameraService, buildRtspPreview } from '@/services/cameraService'

async function addCamera(formData: CameraFormData) {
  // Show RTSP preview before submitting
  const preview = buildRtspPreview(formData)
  console.log('Will create:', preview)

  // Create camera
  const camera = await cameraService.create(formData)
  console.log('Created:', camera.id)

  // Test connectivity
  const testResult = await cameraService.test(camera.id)
  if (testResult.success) {
    // Start stream
    await cameraService.start(camera.id)
  }
}
```

### Error Handling

All methods throw on error. Catch at component level:

```typescript
try {
  const result = await cameraService.test(cameraId)
} catch (error) {
  setError(error instanceof Error ? error.message : 'Test failed')
}
```

---

## moduleService.ts

### Purpose
Manage module system (feature flags, classes, statistics per module).

### Interfaces

```typescript
export interface ModuleClass {
  id: string
  module_code: string
  class_id: number
  class_name: string
  display_name: string
  icon: string
  is_violation: boolean
  color: string
}

export interface ModuleStats {
  cameras_active: number
  cameras_total: number
  alerts_today: number
  alerts_week: number
}
```

### API Methods

```typescript
export const moduleService = {
  // List all modules
  list(): Promise<any[]>

  // Get module details by code
  get(moduleCode: string): Promise<any>

  // Get classes (objects) for a module
  getClasses(moduleCode: string): Promise<ModuleClass[]>

  // Get statistics for a module
  getStats(moduleCode: string): Promise<ModuleStats>
}
```

### Key Details

- **Module code**: String identifier (e.g., `'epi'`, `'fuel'`, `'safety'`)
- **Classes**: Objects that module can detect (helmet, vest, etc.)
- **Stats**: Real-time counts for module (active cameras, alerts)
- **Return on error**: Empty defaults instead of null (e.g., empty array for `list()`)

### Usage Example

```typescript
import { moduleService } from '@/services/moduleService'

async function loadEpiModule() {
  const modules = await moduleService.list()
  const epi = modules.find(m => m.module_code === 'epi')

  if (epi) {
    const classes = await moduleService.getClasses('epi')
    const stats = await moduleService.getStats('epi')
    console.log(`EPI: ${stats.cameras_active} cameras, ${stats.alerts_today} alerts`)
  }
}
```

---

## reportService.ts

### Purpose
Retrieve dashboard reports and KPIs.

### Interfaces

```typescript
export interface HomeReports {
  cards: {
    alerts_today: number
    alerts_week: number
    cameras_active: number
    cameras_total: number
    processings_today: number
    objects_identified: number
  }
  chart: {
    alerts_by_hour: Array<{ hour: string; count: number }>
  }
}
```

### API Methods

```typescript
export const reportService = {
  // Get home dashboard reports
  getHomeReports(): Promise<HomeReports>
}
```

### Key Details

- **Empty default**: Returns all zeros if API fails (never throws)
- **Chart data**: `alerts_by_hour` is array of `{ hour, count }` for chart rendering
- **Cards**: High-level KPIs for the dashboard

### Usage Example

```typescript
import { reportService } from '@/services/reportService'

async function loadDashboard() {
  const reports = await reportService.getHomeReports()
  return (
    <>
      <KpiCard label="Today" value={reports.cards.alerts_today} />
      <AlertsChart data={reports.chart.alerts_by_hour} />
    </>
  )
}
```

---

## Common Patterns

### Authentication Required Requests

```typescript
import { api, getToken } from '@/services/api'

function MyComponent() {
  useEffect(() => {
    const token = getToken()
    if (!token) {
      // Redirect to login
      return
    }

    // API calls auto-include Authorization header
    cameraService.list().then(setData)
  }, [])
}
```

### Error Handling in Components

```typescript
const [error, setError] = useState<string | null>(null)
const [loading, setLoading] = useState(false)

async function handleCreate(data: CameraFormData) {
  try {
    setLoading(true)
    setError(null)
    const camera = await cameraService.create(data)
    // Success
  } catch (err) {
    setError(err instanceof Error ? err.message : 'Unknown error')
  } finally {
    setLoading(false)
  }
}
```

### Timeout Handling

All requests timeout after 15 seconds. For long operations:

```typescript
try {
  await cameraService.start(cameraId)
} catch (err) {
  if (err instanceof Error && err.name === 'AbortError') {
    setError('Stream start timeout — check camera connectivity')
  } else {
    setError(err instanceof Error ? err.message : 'Failed to start stream')
  }
}
```

---

## Testing Services

**Important**: Services are tested via integration tests against a mock API or real backend.

```typescript
import { api } from '@/services/api'

vi.mock('@/services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

it('lists cameras', async () => {
  vi.mocked(api.get).mockResolvedValue({
    data: { cameras: [mockCamera] }
  })

  const cameras = await cameraService.list()
  expect(cameras).toHaveLength(1)
})
```

---

## Environment Variables

### Development
```bash
# vite.config.ts proxy redirects /api to localhost:5001
VITE_API_URL=  # empty (uses proxy)
VITE_WS_URL=   # empty (uses location.hostname)
```

### Production (Railway)
```bash
VITE_API_URL=https://your-app.railway.app
VITE_WS_URL=https://your-app.railway.app
```

---

*Last updated: April 2026 — EPI Monitor V2*
