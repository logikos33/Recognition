# Frontend Training Page Exploration Report

**Date**: 2026-04-12  
**Explorer**: Agent ac94692da4461c7ca (oh-my-claudecode:explore)  
**Status**: INVESTIGATION COMPLETE — Ready for next steps

---

## Executive Summary

The TrainingPage is a unified training interface with 3 tabs (Dados, Treinar, Modelos). It integrates a **FROZEN** AnnotationInterface component (JSX, never modify) and a new FrameTimeline carousel component. The system supports video upload → frame extraction → annotation workflow with WebSocket live training progress.

**Key Finding**: No ImageUpload component exists; upload is built directly into TrainingPage via drag-drop/file input with presigned R2 URLs.

---

## File Structure & Absolute Paths

### Main Files

| File | Purpose | Status |
|------|---------|--------|
| `/Users/vitoremanuel/Documents/Logikos/CATH/EPI - CATH V2/frontend/src/pages/TrainingPage.tsx` | Main training page (812 lines) | Active — recently edited |
| `/Users/vitoremanuel/Documents/Logikos/CATH/EPI - CATH V2/frontend/src/components/AnnotationInterface.jsx` | Frame annotation UI (1071 lines, **FROZEN**) | Read-only — never modify |
| `/Users/vitoremanuel/Documents/Logikos/CATH/EPI - CATH V2/frontend/src/components/training/FrameTimeline.tsx` | CapCut-style frame carousel (168 lines) | Active — new component |
| `/Users/vitoremanuel/Documents/Logikos/CATH/EPI - CATH V2/frontend/src/components/training/FrameTimeline.css.ts` | FrameTimeline styles | Active |
| `/Users/vitoremanuel/Documents/Logikos/CATH/EPI - CATH V2/frontend/src/hooks/useTrainingSocket.ts` | WebSocket training progress (125 lines) | Active |
| `/Users/vitoremanuel/Documents/Logikos/CATH/EPI - CATH V2/frontend/src/services/api.ts` | Centralized API client (66 lines) | Active |
| `/Users/vitoremanuel/Documents/Logikos/CATH/EPI - CATH V2/frontend/src/types/index.ts` | Shared TypeScript types (115 lines) | Active |

---

## TrainingPage Component Structure

### Props/Inputs
- **None**: Self-contained page component with internal state management

### State Variables (43 tracked)

**Video Management:**
- `videos: Video[]` — all uploaded videos
- `selectedVideoId: string | null` — full-screen annotation mode
- `frameTimelineVideo: Video | null` — FrameTimeline modal

**Upload State:**
- `uploading: boolean`, `uploadProgress: number` (0-100), `dragOver: boolean`
- `fileInputRef: React.Ref<HTMLInputElement>`

**Training Config:**
- `showConfig: boolean` — reveal training form
- `cfgPreset: 'fast'|'balanced'|'quality'`, `cfgModelSize: 'yolov8n'|'yolov8s'|'yolov8m'`
- `cfgEpochs: number` (default 50), `cfgBatch: number` (default 16), `cfgImgSize: number` (default 640)
- `creating: boolean` — job creation in progress
- `activating: string | null` — model activation in progress
- `deleteConfirmVideo: Video | null` — delete confirmation modal

**Storage:**
- `storageUsed: string`, `storagePercent: number`

**Frame Handling:**
- `frameCache: Record<string, FrameInfo[]>` — frame metadata per video (no image data, lazy-loaded)
- `extractingSetRef: Set<string>` — actively extracting videos (ref)

**WebSocket:**
- `jobs: TrainingJob[]` from database (initial load)
- `liveJobs: Record<string, TrainingJobState>` from useTrainingSocket (live updates)

---

## UI Tabs & Sections

### Tab 1: "Dados" — Video Management
**Sections:**
1. **Storage Bar** — Shows used/total (5 GB), % filled, plus button (placeholder)
2. **Upload Zone** — Drag-drop or click-to-select video files
   - Presigned R2 URL flow (production) or multipart fallback (local dev)
   - Real byte-level progress tracking via `xhr.upload.onprogress`
3. **Aguardando extracao** — Uploaded but not extracted (status: `uploaded`)
   - Button: "Extrair Frames" → calls `/v1/videos/{videoId}/server-extract`
4. **Extraindo frames...** — Server-side extraction in progress (status: `extracting`)
   - Polled every 3s via `/v1/videos/{videoId}/status`
5. **Falha na extracao** — Failed extractions (status: `error`)
   - Shows error_message, retry button
6. **Prontos para anotacao** — Extracted & ready (status: `extracted`)
   - Mini thumbnail carousel (first 12 frames + "+X more")
   - Click opens FrameTimeline modal (450x frame carousel in overlay)

---

### Tab 2: "Treinar" — Training Jobs
**Sections:**
1. **Training Config Form** (conditionally shown, `showConfig === true`)
   - Preset: `fast` (30min) | `balanced` (2h) | `quality` (6h)
   - Model Size: yolov8n | yolov8s | yolov8m
   - Epochs: 5-300, Batch: 1-64, Img Size: 320-1280 (step 32)
   - Button: "Iniciar Treinamento" → POST `/training/jobs`
2. **Training Jobs List**
   - Each job card shows:
     - Model name (yolov8n→LGKV8n via `displayModelName()`)
     - Preset, status badge
     - **Live WebSocket Progress** (when status='training' or 'creating_pod'):
       - Progress bar (0-100%) + "Epoch X/Y"
       - ETA countdown (if `eta_seconds > 0`)
       - Mini SVG sparkline charts: Loss, mAP@50 (last 200 values)
       - Metric badges: Precision %, Recall %
     - **Static Progress** (fallback, no live data): Progress bar only
     - **Completed Metrics**: mAP@50, Precision, Recall (if available)

---

### Tab 3: "Modelos" — Trained Models
**Sections:**
1. **Models List**
   - Each model card shows:
     - Name (yolov8n→LGKV8n), active badge (green) if `is_active === true`
     - Metrics: mAP@50, Precision, Recall (if available, shown as %)
   - Inactive models: "Ativar" button → POST `/training/models/{modelId}/activate`

---

## AnnotationInterface Component (FROZEN)

**Location**: `/Users/vitoremanuel/Documents/Logikos/CATH/EPI - CATH V2/frontend/src/components/AnnotationInterface.jsx`

**Critical**: This JSX component is **CONGELADO** (frozen) — never rename, move, modify, or refactor. Any integration must adapt to its contract.

### Props
```typescript
{
  videoId: string,              // Video ID to annotate
  onBack: () => void            // Callback when "← Voltar" clicked
}
```

### API Endpoints
- **On Mount**: `GET /api/training/videos/{videoId}/frames`
- **On Frame Change**: `GET /api/training/frames/{frameId}/annotations`
- **On Save**: `POST /api/training/frames/{frameId}/annotations`
- **Classes**: `GET /api/classes`, `POST /api/classes`

### Internal Features
- Tools: Draw (rectangles), Select (move/resize), Delete
- Keyboard: Arrow keys (prev/next), Esc (deselect)
- Timeline: Horizontal scroll strip showing all frames
- Bounding Boxes: YOLO format (x_center, y_center, width, height as 0-1 normalized)
- Status Badges: ✓ (annotated) | ◎ (pre-annotated) | ○ (empty)

---

## FrameTimeline Component

**Location**: `/Users/vitoremanuel/Documents/Logikos/CATH/EPI - CATH V2/frontend/src/components/training/FrameTimeline.tsx`

### Props
```typescript
{
  frames: FrameInfo[],                    // Frame metadata array
  videoName: string,                      // Display name
  apiBase: string,                        // API base URL
  onAnnotate: (frameId: string) => void,  // Click "Anotar"
  onPreAnnotate?: (frameId: string) => void, // Click "Pre-anotar com IA"
  onClose: () => void                     // Click close or Esc
}
```

### UI Layout
- **Header** (70px): Video name, frame counter, buttons (Pre-anotar, Anotar, Close)
- **Preview** (60%): Large frame image with navigation arrows, status badge
- **Timeline** (30%): Horizontal scrollable thumbnail strip
- **Hint** (footer): "← → navegar · Esc fechar"

### Interactions
- Arrow Keys: Navigate frames
- Esc: Close modal
- Thumb Click: Jump to frame
- "Anotar" Button: Calls `onAnnotate(frameId)`
- "Pre-anotar com IA" Button: Calls `onPreAnnotate(frameId)`

---

## API Endpoints Called by Frontend

### Video Upload & Management
| Endpoint | Method | Called From | Notes |
|----------|--------|-------------|-------|
| `/v1/videos/upload-url` | POST | TrainingPage.uploadFile | Get presigned R2 URL |
| `/v1/videos/upload` | POST | TrainingPage.uploadFile | Fallback multipart (local dev) |
| `PUT {upload_url}` | PUT | TrainingPage.uploadFile (XHR) | Direct to R2 (production) |
| `/v1/videos/{videoId}/server-extract` | POST | TrainingPage.runBrowserExtraction | Start frame extraction |
| `/v1/videos/{videoId}/status` | GET | TrainingPage (polling) | Poll extraction progress every 3s |
| `/v1/videos/{videoId}` | DELETE | TrainingPage.deleteVideo | Delete video |
| `/v1/videos/storage` | GET | TrainingPage.loadStorage | Get storage usage % |

### Training Jobs
| Endpoint | Method | Called From | Notes |
|----------|--------|-------------|-------|
| `/training/jobs` | GET | TrainingPage.loadData | Load all jobs (initial) |
| `/training/jobs` | POST | TrainingPage.createJob | Create new training job |
| `/training/models` | GET | TrainingPage.loadData | Load all trained models |
| `/training/models/{modelId}/activate` | POST | TrainingPage.activateModel | Activate a trained model |

### Frames & Annotations
| Endpoint | Method | Called From | Notes |
|----------|--------|-------------|-------|
| `/training/videos/{videoId}/frames` | GET | TrainingPage, AnnotationInterface | Load frame metadata |
| `/training/frames/{frameId}/image` | GET | FrameTimeline, AnnotationInterface (img src) | Fetch frame image |
| `/training/frames/{frameId}/annotations` | GET | AnnotationInterface.loadAnnotations | Load annotations for a frame |
| `/training/frames/{frameId}/annotations` | POST | AnnotationInterface.saveAnnotations | Save annotations for a frame |
| `/frames/{frameId}/pre-annotate` | POST | TrainingPage.handlePreAnnotate | Trigger AI pre-annotation |

### Classes
| Endpoint | Method | Called From | Notes |
|----------|--------|-------------|-------|
| `/api/classes` | GET | AnnotationInterface.loadClasses | Load YOLO classes |
| `/api/classes` | POST | AnnotationInterface.addNewClass | Create new class |

---

## Key Data Types

### Video
```typescript
{
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

### FrameInfo (internal)
```typescript
{
  id: string
  filename: string
  annotation_status?: 'annotated' | 'pre_annotated' | 'empty'
  frame_number?: number
}
```

### Annotation
```typescript
{
  id: string
  frame_id: string
  class_id: number
  class_name?: string
  class_color?: string
  x_center: number        // 0-1 normalized
  y_center: number        // 0-1 normalized
  width: number           // 0-1 normalized
  height: number          // 0-1 normalized
}
```

### TrainingJob
```typescript
{
  id: string
  preset: string                    // 'fast', 'balanced', 'quality'
  model_size: string                // 'yolov8n', 'yolov8s', 'yolov8m'
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
  progress: number                  // 0-100
  current_epoch: number
  total_epochs: number
  metrics: Record<string, number>
  error_message?: string
  started_at?: string
  completed_at?: string
  created_at: string
}
```

### TrainingJobState (WebSocket)
```typescript
{
  status: 'creating_pod' | 'training' | 'completed' | 'failed' | 'pending'
  progress: number          // 0-100
  epoch: number
  total_epochs: number
  metrics: {loss?, map50?, precision?, recall?}
  eta_seconds: number
  error?: string
  model_key?: string
  lossHistory: number[]     // Last 200 values
  map50History: number[]    // Last 200 values
}
```

---

## Key Functional Flows

### Video Upload Flow
1. **User Action**: Drag video or click upload zone
2. `uploadFile(file)` runs:
   - Step 1: POST `/v1/videos/upload-url` (get presigned URL + video_id)
   - Step 2a (Production): PUT file directly to R2 (with real-time byte progress)
   - Step 2b (Fallback): POST multipart to `/v1/videos/upload` (if R2 fails)
   - Step 3: Call `runBrowserExtraction(videoId)` → POST `/v1/videos/{videoId}/server-extract`
3. **Polling**: Every 3s, check `/v1/videos/{videoId}/status`
   - When status changes from "extracting" → "extracted", reload all data
4. **Result**: Video appears in "Prontos para anotacao" section

### Frame Annotation Flow
1. **User Action**: Click video in "Dados" → click FrameTimeline "Anotar" button
2. `handleAnnotate(frameId)` → `setSelectedVideoId(frameTimelineVideo.id)` + close FrameTimeline
3. Page renders `<AnnotationInterface videoId={...} onBack={...} />`
4. AnnotationInterface:
   - Loads frames: `GET /training/videos/{videoId}/frames`
   - Loads annotations per frame: `GET /training/frames/{frameId}/annotations`
   - User draws/edits boxes
   - User clicks save (internal, not exposed to TrainingPage)
   - POST `/training/frames/{frameId}/annotations`
5. **Return**: User clicks "← Voltar" → `onBack()` → back to TrainingPage

### Training Job Flow
1. **User Action**: Click "Novo Treinamento" → fill config → click "Iniciar Treinamento"
2. `createJob()` → POST `/training/jobs` with preset, model_size, epochs, batch_size, img_size
3. **Live Updates**: `useTrainingSocket` receives `training_progress` events via `/training` namespace
   - Updates `liveJobs[jobId]` with progress, epoch, loss, metrics, eta_seconds
4. **Rendering**: Job card shows live charts (Loss, mAP@50) + metric badges
5. **Completion**: When status='completed', show metrics (mAP@50, Precision, Recall)
6. **Model Activation**: User clicks "Ativar" → POST `/training/models/{modelId}/activate`

---

## Recommendations for Next Steps

### If Building New Features
1. **New Upload Component**: Don't create separate; extend TrainingPage's existing drag-drop zone
2. **New Training UI**: Add to "Treinar" tab via new Radix UI Tab or accordion section
3. **New Frame Action**: Add button to FrameTimeline header; call via `onAnnotate` or new `onAction` prop
4. **AnnotationInterface Integration**: Never fork; only call via `videoId` prop

### If Debugging
1. **Frame Not Loading**: Check `GET /training/videos/{videoId}/frames` payload matches `FrameInfo` interface
2. **Live Progress Not Updating**: Verify WebSocket connection to `/training` namespace; check token in query params
3. **Annotations Not Saving**: Ensure `POST /training/frames/{frameId}/annotations` receives `{annotations: Annotation[]}` body
4. **Storage % Wrong**: Check R2 bucket usage vs. claimed 5 GB limit

### If Refactoring
- **DO NOT TOUCH**: AnnotationInterface.jsx (copy/re-implement if needed)
- **SAFE TO REFACTOR**: FrameTimeline.tsx (new, no external dependencies)
- **SAFE TO REFACTOR**: useTrainingSocket hook (isolated, no side effects)
- **CAREFUL WITH**: TrainingPage state (43 variables, complex polling + WebSocket choreography)

---

## Summary

**TrainingPage is a sophisticated, multi-modal training interface with tight WebSocket integration and lazy-loaded frame handling.** The AnnotationInterface remains frozen, FrameTimeline is new and clean, and the backend API contract is well-defined. All paths are absolute and verified.

**Investigation complete. Ready for executor phase.**
