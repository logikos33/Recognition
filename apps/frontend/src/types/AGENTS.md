# Types — TypeScript Interfaces and Type Definitions

<!-- Parent: ../AGENTS.md -->

## Overview

Central TypeScript type definitions used throughout the frontend. All types are defined in `index.ts` and exported for use across components, hooks, and services.

**Directory**: `frontend/src/types/`

**Files**:
- `index.ts` — All TypeScript interfaces and type definitions

**Key principle**: TypeScript `strict: true` enforces type safety — no implicit `any`.

---

## Core Interfaces

### User

```typescript
export interface User {
  id: string
  email: string
  name: string
  role: 'admin' | 'operator'
}
```

Represents authenticated user. Stored in `localStorage` after login.

---

### Camera

```typescript
export interface Camera {
  id: string
  user_id?: string
  name: string
  location?: string
  description?: string
  manufacturer: string           // hikvision, dahua, intelbras, axis, samsung, generic
  host: string                   // IP address
  port: number                   // RTSP port (usually 554)
  username?: string
  channel: number
  subtype?: number
  rtsp_url_override?: string     // Custom RTSP path (if provided)
  is_active: boolean
  stream_status?: string         // online, offline, error, etc.
  last_seen?: string
  last_error?: string
  last_tested_at?: string
  updated_at?: string
  created_at: string
}
```

**Key fields**:
- `host` — Camera IP address
- `manufacturer` — Used to determine default RTSP path
- `rtsp_url_override` — If provided, overrides auto-generated path
- `stream_status` — Current streaming state
- `is_active` — Whether camera is enabled

---

### Video

```typescript
export interface Video {
  id: string
  user_id: string
  filename: string
  original_filename?: string
  file_size?: number
  duration_seconds?: number
  status: 'uploaded' | 'extracting' | 'extracted' | 'error'
  frame_count: number
  error_message?: string
  created_at: string
}
```

Video upload and processing status.

---

### Frame

```typescript
export interface Frame {
  id: string
  video_id: string
  frame_number: number
  filename: string
  timestamp_seconds?: number
  is_annotated: boolean
  created_at: string
}
```

Individual frame extracted from video.

---

### Annotation

```typescript
export interface Annotation {
  id: string
  frame_id: string
  class_id: number
  class_name?: string
  class_color?: string
  x_center: number
  y_center: number
  width: number
  height: number
}
```

Bounding box annotation on a frame (YOLO format: center coordinates + width/height).

---

### YoloClass

```typescript
export interface YoloClass {
  id: number
  name: string
  color: string
}
```

Detection class (object type) that YOLO can detect.

---

### TrainingJob

```typescript
export interface TrainingJob {
  id: string
  preset: string
  model_size: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
  progress: number
  current_epoch: number
  total_epochs: number
  metrics: Record<string, number>
  error_message?: string
  started_at?: string
  completed_at?: string
  created_at: string
}
```

YOLO model training job status and progress.

---

### TrainedModel

```typescript
export interface TrainedModel {
  id: string
  name: string
  model_path: string
  map50?: number
  precision?: number
  recall?: number
  is_active: boolean
  created_at: string
}
```

Deployed YOLO model with metrics.

---

### Alert

```typescript
export interface Alert {
  id: string
  camera_id: string
  timestamp: string
  violations: Array<{ class: string; confidence: number }>
  confidence: number
  evidence_key?: string
  acknowledged: boolean
}
```

Safety violation alert from a camera.

---

### Detection

```typescript
// From useMonitoringSocket hook
export interface Detection {
  class: string
  confidence: number
  bbox: [number, number, number, number]  // x, y, w, h
  is_violation?: boolean
}
```

Single detected object in a frame (from YOLO inference).

---

### DetectionEvent

```typescript
// From useMonitoringSocket hook
export interface DetectionEvent {
  camera_id: string
  timestamp: string
  detections: Detection[]
  has_violation: boolean
}
```

WebSocket event with all detections for a frame.

---

### AlertEvent

```typescript
// From useMonitoringSocket hook
export interface AlertEvent {
  id?: string
  camera_id: string
  violations: Detection[]
  created_at?: string
  tenant_id?: string
}
```

WebSocket event for safety violation alert.

---

## Generic Response Types

### ApiResponse

```typescript
export interface ApiResponse<T> {
  success: boolean
  message?: string
  data?: T
  error?: string
}
```

Wrapper for all API responses. Used when calling services:

```typescript
const res = await api.get<ApiResponse<{ cameras: Camera[] }>>('/cameras')
const cameras = res.data?.cameras ?? []
```

---

## Module Types

### Module (from useModules hook)

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

Feature module (e.g., EPI detection, fuel monitoring).

### ModuleClass (from moduleService)

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
```

Object class that a module can detect.

### ModuleStats (from moduleService)

```typescript
export interface ModuleStats {
  cameras_active: number
  cameras_total: number
  alerts_today: number
  alerts_week: number
}
```

KPI statistics for a module.

---

## Report Types

### HomeReports (from reportService)

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

Dashboard KPIs and chart data.

---

## Usage Rules

### 1. Import All Types from Central Location

```typescript
// ✅ CORRECT — import from types/index.ts
import type { Camera, User, Alert } from '@/types'

// ❌ WRONG — defining types in component
interface Camera { ... }
```

### 2. Use Strict Mode (No Implicit Any)

In `tsconfig.json`, ensure:
```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true
  }
}
```

All function parameters and variables must have explicit types:

```typescript
// ✅ CORRECT
function setCameras(cameras: Camera[]): void { ... }

// ❌ WRONG — no type annotation
function setCameras(cameras) { ... }
```

### 3. Use `export type` for Re-exports

When re-exporting from other modules:

```typescript
// In types/index.ts
export type { Detection, DetectionEvent } from '@/hooks/useMonitoringSocket'
export type { ModuleClass, ModuleStats } from '@/services/moduleService'
```

### 4. Optional vs Required Fields

Use `?` for optional fields:

```typescript
interface Camera {
  id: string              // Required
  name: string            // Required
  location?: string       // Optional
  description?: string    // Optional
}
```

### 5. Union Types for Status Fields

```typescript
// Good
status: 'online' | 'offline' | 'error'
role: 'admin' | 'operator'

// Better (if many values)
enum StreamStatus {
  ONLINE = 'online',
  OFFLINE = 'offline',
  ERROR = 'error',
}
```

---

## Component Usage Examples

### Receiving Props

```typescript
import type { Camera } from '@/types'

interface CameraCardProps {
  camera: Camera
  onDelete?: (id: string) => void
}

export function CameraCard({ camera, onDelete }: CameraCardProps) {
  return (
    <div>
      <h3>{camera.name}</h3>
      <p>{camera.manufacturer} @ {camera.host}</p>
    </div>
  )
}
```

### State Management

```typescript
import type { Camera } from '@/types'

function CameraManager() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    cameraService.list()
      .then(setCameras)
      .catch(err => setError(err.message))
  }, [])

  return (
    <>
      {cameras.map(cam => <CameraCard key={cam.id} camera={cam} />)}
      {error && <ErrorMessage message={error} />}
    </>
  )
}
```

### API Response Handling

```typescript
import type { ApiResponse, Camera } from '@/types'

async function loadCamera(id: string): Promise<Camera | null> {
  try {
    const res = await api.get<ApiResponse<Camera>>(`/cameras/${id}`)
    return res.data || null
  } catch (error) {
    console.error('Failed to load camera:', error)
    return null
  }
}
```

---

## Common Type Patterns

### Optional Properties with Defaults

```typescript
interface ComponentProps {
  title: string
  subtitle?: string
  maxItems?: number
}

function MyComponent({ title, subtitle = '', maxItems = 10 }: ComponentProps) {
  // ...
}
```

### Discriminated Unions

```typescript
type Result<T> =
  | { success: true; data: T }
  | { success: false; error: string }

function handleResult<T>(result: Result<T>) {
  if (result.success) {
    console.log(result.data)  // TypeScript knows data exists
  } else {
    console.error(result.error)  // TypeScript knows error exists
  }
}
```

### Readonly Collections

```typescript
interface Config {
  readonly supportedManufacturers: string[]
  readonly maxCameras: number
}

// TypeScript prevents:
config.maxCameras = 20  // Error
config.supportedManufacturers.push('new')  // Error
```

---

## Testing with Types

```typescript
import type { Camera } from '@/types'

const mockCamera: Camera = {
  id: 'cam-1',
  name: 'Test Camera',
  manufacturer: 'hikvision',
  host: '192.168.1.100',
  port: 554,
  channel: 1,
  is_active: true,
  created_at: new Date().toISOString(),
}
```

---

## Extending Types

If you need to extend a type for internal use:

```typescript
// ✅ CORRECT — use intersection
type CameraWithStatus = Camera & { localStatus: 'loading' | 'error' }

// ❌ WRONG — don't redefine
interface CameraWithStatus {
  id: string
  name: string
  // ... duplicate everything
}
```

---

## Type Guard Functions

When working with union types, use type guards:

```typescript
function isCameraActive(camera: Camera): boolean {
  return camera.is_active && camera.stream_status === 'online'
}

// Usage
cameras.filter(isCameraActive).forEach(startMonitoring)
```

---

## Performance Considerations

- TypeScript types are **erased at compile time** — zero runtime overhead
- Type checking happens at build time, not runtime
- No need for runtime validation — trust the compiler

---

## Consistency Rules

1. **Field naming**: Use snake_case (matches API schema)
2. **Boolean fields**: Prefix with `is_` (e.g., `is_active`, `is_annotated`)
3. **Status fields**: Use string literals or enums, not arbitrary values
4. **ID fields**: Always string (can represent UUID or numeric ID)
5. **Timestamps**: Always ISO 8601 strings (e.g., `created_at: string`)
6. **Optional fields**: Only when genuinely optional (not "sometimes present")

---

*Last updated: April 2026 — EPI Monitor V2*
