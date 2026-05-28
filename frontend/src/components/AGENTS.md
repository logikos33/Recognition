# frontend/src/components — Component Specialist

<!-- Parent: ../AGENTS.md -->

This directory contains reusable React/TypeScript components organized by domain.

## Directory Structure

```
components/
├── annotation/
│   └── PreAnnotationControls.tsx    # Controls (hidden in frozen state)
├── AnnotationInterface.jsx          # ⛔ FROZEN — never touch
├── CameraPlayer.jsx                 # Legacy player (deprecated)
├── cameras/
│   ├── CameraCard.tsx               # Camera grid card with actions
│   └── CameraWizard.tsx             # 4-step camera setup wizard
├── monitoring/
│   ├── CameraPlayer.tsx             # HLS player with hls.js + error handling
│   ├── DetectionOverlay.tsx         # Canvas overlay for bounding boxes
│   ├── AlertsPanel.tsx              # Real-time alerts display
│   └── index.ts                     # Exports
├── shared/
│   ├── LoadingSpinner.tsx           # Reusable loading indicator
│   ├── StatusBadge.tsx              # Status color+label badge
│   └── ErrorBoundary.tsx            # React error boundary
├── training/                        # (empty, reserved for future use)
└── VideoTimelineSelector.jsx        # Legacy (deprecated)
```

## Frozen Component — ABSOLUTE Rule

### AnnotationInterface.jsx

**Status**: FROZEN — zero modifications permitted.

```
Do NOT:
  - Modify any line
  - Add/remove imports
  - Change props signature
  - Refactor logic
  - Move to different location
  - Rename file

Why: Contract between legacy Fase 1 and Fase 2 systems. Any change breaks
canvas overlay, keyboard shortcuts, and frame navigation.

Action: If you need to integrate with this component, ADAPT your code
to match its existing interface, not the reverse.
```

## Component Guidelines

### Size Limits
- **Max 200 lines per file** (excluding imports + types)
- If exceeding: split into smaller components

### Props Definition Pattern
```typescript
// ✅ CORRECT — interfaces above component
interface MyComponentProps {
  title: string
  onClose: () => void
  items?: Item[]
}

export function MyComponent({ title, onClose, items = [] }: MyComponentProps) {
  // ... implementation
}

// ❌ WRONG — inline props (hard to document)
export function MyComponent(props: { title: string; onClose: () => void }) {}
```

### forwardRef Pattern (for DOM-exposing components)
```typescript
export const MyInput = forwardRef<HTMLInputElement, MyInputProps>(
  ({ placeholder, ...props }, ref) => (
    <input ref={ref} placeholder={placeholder} {...props} />
  )
)
MyInput.displayName = 'MyInput'
```

## Domain Breakdown

### annotation/ — AnnotationInterface Helpers
- **PreAnnotationControls.tsx** — Toolbar, class selector, undo/redo
  - Used by AnnotationInterface (frozen parent)
  - Keep max 100 lines
  - Props: `classes`, `activeClass`, `onClassChange`, `onUndo`, `onRedo`

### cameras/ — Camera Management

#### CameraCard.tsx
- **Purpose**: Display single camera with inline actions
- **State**: `testState`, `testMsg`, `streaming`, `confirmDelete`
- **Actions**:
  - Test connectivity (API: `cameraService.test()`)
  - Start stream (API: `cameraService.start()`)
  - Stop stream (API: `cameraService.stop()`)
  - Edit (opens CameraWizard)
  - Delete (inline confirmation)
- **Styling**: Dark theme, colored status badges
- **Props**: `Camera`, `onEdit`, `onDelete`, `onRefresh`

#### CameraWizard.tsx
- **Purpose**: 4-step wizard for create/edit cameras
- **Steps**:
  1. Manufacturer selection (Hikvision, Dahua, Intelbras, Axis, Samsung, Generic)
  2. Connection details (IP, port, username, password, path)
  3. Identification (name, location, RTSP preview)
  4. Connectivity test with diagnostic checklist
- **Modes**:
  - **Create**: form data → POST `/api/cameras` → test
  - **Edit**: form data → PUT `/api/cameras/{id}` → test
- **Validation**: RTSPUrlValidator, IP format, port range
- **Props**: `isOpen`, `onClose`, `onSuccess`, `camera?`

### monitoring/ — Real-Time Monitoring

#### CameraPlayer.tsx
- **Purpose**: HLS video player using hls.js
- **Features**:
  - Low latency mode (`lowLatencyMode: true`)
  - Graceful Safari fallback (native HLS)
  - Auto-play on manifest parsed
  - Error handling with user-friendly messages
- **State**: `error`, `loading`
- **Props**: `cameraId`, `hlsUrl`, `width`, `height`
- **Cleanup**: Properly destroy hls.js instance on unmount

#### DetectionOverlay.tsx ⛔ RULES

**ABSOLUTE CONSTRAINTS** (inherited from Fase 1):
```typescript
// ✅ MUST: pointerEvents: 'none' on canvas
<canvas style={{ pointerEvents: 'none', ... }} />

// ❌ MUST NOT: onClick handlers on boxes
// ❌ MUST NOT: event listeners on canvas
// ❌ MUST NOT: interactive bounding boxes

// Why: Mouse events handled mathematically at parent level
// (see AnnotationInterface.jsx, handleMouseDown)
```

- **Purpose**: Render YOLO detections as colored bounding boxes
- **Rendering**: Canvas 2D (fast, no DOM nodes)
- **Data**: Detections array with `class`, `confidence`, `bbox [x,y,w,h]`
- **Scaling**: Auto-scale from video dimensions to display dimensions
- **Colors**: Defined in `CLASS_COLORS` object (EPI classes)
- **Label**: Class name + confidence % with semi-transparent background
- **Props**: `detections`, `videoWidth`, `videoHeight`, `displayWidth?`, `displayHeight?`

#### AlertsPanel.tsx
- **Purpose**: Real-time alerts from WebSocket
- **Display**: Latest 5 alerts, violation classes, timestamps
- **Style**: Red theme, collapsible sections
- **Refresh**: Auto-scroll to newest alerts

### shared/ — Reusable Utilities

#### LoadingSpinner.tsx
- **Purpose**: Spinning loading indicator
- **Customization**: `size` prop (default 32px)
- **Animation**: CSS keyframes (no external libs)
- **Usage**: Wrap page during API calls

#### StatusBadge.tsx
- **Purpose**: Colored status label
- **Input**: `status` string + optional `label` override
- **Colors**: status-specific (active→green, error→red, etc.)
- **Usage**: Camera status, stream status, job status

#### ErrorBoundary.tsx
- **Purpose**: React error boundary for graceful error UI
- **Features**: Fallback component, error logging, reset button
- **Usage**: Wrap at page level, not component level
- **Props**: `children`, `fallback?`

## Styling Convention

All components use **inline styles** (no CSS modules/files):

```typescript
const card: React.CSSProperties = {
  background: '#1e293b',
  borderRadius: 12,
  border: '1px solid #334155',
  overflow: 'hidden',
}

const btn = (bg: string, fg = '#fff'): React.CSSProperties => ({
  padding: '8px 16px',
  borderRadius: 6,
  border: 'none',
  background: bg,
  color: fg,
  cursor: 'pointer',
})
```

**Color palette** (Tailwind):
- Backgrounds: `#0d1117` (black), `#1e293b` (dark slate), `#334155` (slate)
- Text: `#e2e8f0` (light), `#94a3b8` (muted), `#64748b` (gray)
- Success: `#22c55e` (green)
- Error: `#ef4444` (red)
- Warning: `#f59e0b` (amber)
- Info: `#3b82f6` (blue)

## API Integration Pattern

```typescript
import { cameraService } from '../../services/cameraService'

// Inside component event handler:
try {
  await cameraService.test(cameraId)
  toast.success('✓ Teste OK')
} catch (err: unknown) {
  const msg = err instanceof Error ? err.message : 'Erro'
  toast.error(msg)
}
```

**Services used**: `cameraService`, `moduleService`

## State Management

Components use **React hooks only** (no Redux/Context):
- `useState()` for local state
- `useEffect()` with dependencies for side effects
- `useCallback()` to optimize event handlers
- `useRef()` for DOM access (canvas, video, input focus)

## Testing Convention

Each component directory should have `__tests__/ComponentName.test.tsx`:
```typescript
import { render, screen } from '@testing-library/react'
import { CameraCard } from '../CameraCard'

describe('CameraCard', () => {
  it('renders camera name and status', () => {
    const camera = { id: '1', name: 'Cam 1', stream_status: 'active', ... }
    render(<CameraCard camera={camera} onEdit={() => {}} onDelete={() => {}} onRefresh={() => {}} />)
    expect(screen.getByText('Cam 1')).toBeInTheDocument()
  })
})
```

## Migration Notes

- **CameraPlayer.jsx** (legacy): Deprecated, use `monitoring/CameraPlayer.tsx`
- **VideoTimelineSelector.jsx** (legacy): Deprecated, reserved for future cleanup
- **All new components**: TypeScript only (no .jsx files)
