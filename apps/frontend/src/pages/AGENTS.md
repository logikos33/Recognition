# frontend/src/pages — Page Route Specialist

<!-- Parent: ../AGENTS.md -->

This directory contains page components — top-level route handlers for the SPA.

## Directory Structure

```
pages/
├── Login.tsx                        # Authentication form
├── HomePage.tsx                     # Dashboard / landing
├── CamerasPage.tsx                  # Camera management + grid
├── DashboardPage.tsx                # System stats overview
├── AlertsHistoryPage.tsx            # Paginated alerts + CSV export
├── TrainingPage.tsx                 # Model training interface
├── epi/                             # EPI monitoring module (Dashboard/Cameras/Alerts
│                                     #  + MonitoringPage demolidos 2026-08-30, ver
│                                     #  app/epi/{Dashboard,Cameras,Eventos,AoVivo}.tsx)
└── fueling/                         # Fueling bay monitoring module
    └── FuelingPlaceholder.tsx       # (reserved for future use)
```

## Page Guidelines

### Max 300 Lines Per File
- Single-responsibility: each page = one major feature
- If exceeding: split into child components in `components/`
- Example: DashboardPage uses stat-card child components

### Naming Convention
- Format: `{Feature}Page.tsx`
- Examples: `CamerasPage`, `AlertsHistoryPage`

### Architecture Pattern
```
Page Component (hooks, state management)
  └── Child Components (presentational)
      └── Shared Components (LoadingSpinner, StatusBadge, etc.)
```

## Page Details

### Login.tsx
- **Purpose**: JWT authentication form
- **Features**:
  - Email + password fields
  - Submit button with loading state
  - Error messages from API
  - Redirect to HomePage on success
- **Integration**: `useAuth()` hook
- **API**: POST `/api/auth/login`

### HomePage.tsx
- **Purpose**: Dashboard landing page
- **Features**:
  - Quick stats (cameras, videos, jobs)
  - Navigation cards to main features
  - Recent activity feed (optional)
- **Route**: `/` (root)

### CamerasPage.tsx
- **Purpose**: Camera management interface
- **Components Used**: CameraCard, CameraWizard
- **State**:
  - `cameras: Camera[]` — loaded from API
  - `loading: boolean` — API call status
  - `wizardOpen: boolean` — modal visibility
  - `editingCamera?: Camera` — for wizard mode
  - `gatewayStatus: string` — gateway connectivity
- **Actions**:
  - Load cameras on mount (`useEffect`)
  - Open wizard for create (clear editingCamera)
  - Open wizard for edit (set editingCamera)
  - Delete camera (inline + reload)
  - Refresh list (manual button + after wizard success)
- **API**:
  - GET `/api/cameras` → Camera[]
  - POST `/api/cameras` → new Camera
  - PUT `/api/cameras/{id}` → updated Camera
  - DELETE `/api/cameras/{id}`
- **Layout**: Header with button, grid of CameraCards or empty state
- **Styling**: Dark theme, responsive grid (`minmax(300px, 1fr)`)

### MonitoringPage.tsx — REMOVIDA (2026-08-30)
Demolida no lote 1 (PR-B); substituta é `app/epi/AoVivo.tsx` (rota `/novo/epi/live`).
Recuperação: `git show archive/front-antigo-epi-lote1-2026-08-30:apps/frontend/src/pages/MonitoringPage.tsx`.

### AnnotationPage.tsx — REMOVIDA (2026-08)
- Página morta (nenhuma rota apontava para ela) deletada junto com o
  anotador legado. A anotação hoje é o `AnnotationStudio` aberto pela
  galeria em `TrainingPage.tsx` (aba Imagens).

### DashboardPage.tsx
- **Purpose**: System statistics overview
- **State**:
  - `stats: DashboardStats | null` — aggregated metrics
  - `loading: boolean` — API call status
- **API**:
  - Primary: GET `/api/v1/dashboard/stats`
  - Fallback (old API): GET `/cameras`, `/training/videos`, `/training/jobs`
- **Stats Displayed**:
  - `cameras_total`, `videos_total`, `videos_extracted`
  - `frames_total`, `frames_annotated`
  - `jobs_total`, `jobs_running`
  - `models_total`, `models_active`
  - `alerts_24h`, `alerts_pending`
  - `class_distribution` — chart data
- **Handling Old API**: Graceful fallback with Promise.all + catch chain
- **Styling**: Stat cards in grid, color-coded metrics

### AlertsHistoryPage.tsx
- **Purpose**: Paginated alert history with filters
- **State**:
  - `data: AlertsResponse | null` — paginated alerts
  - `loading: boolean` — API call status
  - `exporting: boolean` — CSV export in progress
  - `ackingId: string | null` — acknowledging alert
  - `filters: {...}` — camera_id, date range, violation type, ack status, page
- **Features**:
  - Pagination (previous/next buttons, jump to page)
  - Filters: camera, date range, violation class, acknowledged status
  - Acknowledge button (mark as reviewed)
  - CSV export button (downloads all results)
- **API**:
  - GET `/api/v1/alerts/history?camera_id=...&page=1&per_page=20`
  - POST `/api/v1/alerts/{id}/acknowledge`
  - GET `/api/v1/alerts/export?...` → CSV file
- **Styling**: Table rows, filter form above, action buttons

### TrainingPage.tsx
- **Purpose**: Model training interface
- **Features**:
  - Select dataset for training
  - Configuration options (epochs, learning rate, etc.)
  - Progress bar for active training
  - Model versioning history
- **State**: Active job, form inputs, model list
- **API**: POST `/api/v1/training/start`, GET `/api/v1/models`

### epi/ — EPI Monitoring Module

#### EpiDashboard.tsx, EpiCameras.tsx, EpiAlerts.tsx — REMOVIDAS (2026-08-30)
Demolidas no lote 1 (PR-B); substitutas são `app/epi/Dashboard.tsx`,
`app/epi/Cameras.tsx` e `app/epi/Eventos.tsx` (rotas
`/novo/epi/{dashboard,cameras,eventos}`).
Recuperação: `git show archive/front-antigo-epi-lote1-2026-08-30:apps/frontend/src/pages/epi/<arquivo>.tsx`.

### fueling/ — Fueling Bay Monitoring Module

#### FuelingPlaceholder.tsx
- **Status**: Placeholder for future fueling bay module
- **To be implemented**: Similar structure to EPI module but for fueling operations

## Page-Level Hooks

### Recommended Custom Hooks (from hooks/)
- `useAuth()` — Get/set token, login/logout
- `usePolling()` — Exponential backoff polling
- `useMonitoringSocket()` — WebSocket detections + alerts
- `useModules()` — Module configuration

## API Integration Pattern

```typescript
import { api } from '../services/api'

useEffect(() => {
  api.get<Camera[]>('/cameras')
    .then(res => setCameras(res.data || res))
    .catch(err => toast.error(err.message))
    .finally(() => setLoading(false))
}, [])
```

**Service centralization**: Never use fetch/axios directly. Always import from `services/api.ts`.

## Styling Convention

Pages use **inline styles** (matching component pattern):
- `padding: 24` or `32` for main page margins
- Responsive grid: `gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))'`
- Flex layouts for header/sidebar arrangements
- Color palette: See `components/AGENTS.md`

## Error Handling Pattern

```typescript
// ✅ CORRECT — user-friendly fallback
const [data, setData] = useState<DataType | null>(null)

useEffect(() => {
  api.get<DataType>('/endpoint')
    .then(res => setData(res.data))
    .catch(() => setData(null))  // Silent, show empty state
    .finally(() => setLoading(false))
}, [])

// Or with explicit error message:
.catch(err => {
  const msg = err instanceof Error ? err.message : 'Erro ao carregar'
  toast.error(msg)
})
```

## Loading States

Every page should handle:
1. **Initial load** — show LoadingSpinner
2. **Empty state** — show descriptive message + CTA button
3. **Error state** — show error message + retry button (if applicable)
4. **Loaded state** — show content

Example:
```typescript
if (loading) return <LoadingSpinner />

if (data.length === 0) {
  return (
    <div style={{ textAlign: 'center', padding: 40 }}>
      <h3>Nenhum item</h3>
      <p>Comece adicionando um novo item</p>
      <button onClick={handleCreate}>+ Adicionar</button>
    </div>
  )
}

return <div>...</div>  // Actual content
```

## TypeScript Strict Mode

All pages must:
- Declare all state types explicitly: `useState<Type>(initialValue)`
- Type all function parameters
- No `any` types
- Handle union types explicitly (`| null`, `| undefined`)

Example:
```typescript
// ✅ CORRECT
const [items, setItems] = useState<Item[]>([])
const [error, setError] = useState<string | null>(null)

async function loadData(): Promise<void> {
  try {
    const data = await api.get<Item[]>('/items')
    setItems(data)
  } catch (err: unknown) {
    // ...
  }
}

// ❌ WRONG
const [items, setItems] = useState([])  // Type: any[]
const loadData = async () => { ... }     // Return type: Promise<any>
```

## Testing Convention

Each page directory should have `__tests__/PageName.test.tsx`:
```typescript
import { render, screen } from '@testing-library/react'
import { CamerasPage } from '../CamerasPage'

describe('CamerasPage', () => {
  it('renders page title', () => {
    render(<CamerasPage />)
    expect(screen.getByText('Câmeras')).toBeInTheDocument()
  })
})
```

## Deep Linking

Pages supporting URL parameters:
- **AlertsHistoryPage**: `?page=1&camera={id}&from={date}`
- **Others**: As needed

Use `useSearchParams()` from react-router-dom.

## Future Modules (Reserved)

- `fueling/` — Will follow same structure as EPI module
- `rules/` — Rules engine for detections
- `training/` — Advanced model training UI
- `reports/` — PDF/Excel report generation
