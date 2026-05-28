# Annotation Interface & Training Integration Analysis

**Date**: 2026-04-13  
**Status**: EXPLORATION COMPLETE — Ready for Implementation Planning  
**Scope**: Full codebase analysis of AnnotationInterface.jsx, TrainingPage.tsx, pre-annotation pipeline, and data format contracts

---

## Executive Summary

The AnnotationInterface component is **CONGELADO (frozen)** but fully featured with drag-resize-delete, class management, and persistent annotation storage. The training workflow polls video status and calls pre-annotation via proxy. **NO direct integration of pre_annotations into AnnotationInterface exists yet** — the component loads only user-created annotations.

**Key Finding**: US-021 fallback logic exists in backend (`annotation_service.py` lines 42-107) but frontend AnnotationInterface never receives pre_annotations because:
1. AnnotationInterface uses raw `fetch()` to `/api/training/frames/{id}/annotations` (line 131)
2. This endpoint returns saved annotations only — no pre_annotations fallback yet
3. FrameTimeline has UI button for "Pre-anotar com IA" but no visual feedback on success

---

## 1. AnnotationInterface.jsx Analysis

**File**: `/frontend/src/components/AnnotationInterface.jsx`  
**Status**: FROZEN — Never modify, rename, move, or refactor  
**Size**: ~1000 lines  

### 1.1 Props Accepted
```javascript
AnnotationInterface({ videoId, onBack })
```
- `videoId` (string): Required. Used to load frames from `/api/training/videos/{videoId}/frames`
- `onBack` (function): Callback to close component

**NO props for initialAnnotations, pre_annotations, or onSave** — component is self-contained.

### 1.2 Data Format for Annotations
Stored in state as `annotations: list[dict]` with structure:
```javascript
{
  id: string,                    // "annotation-{timestamp}" or "pre-{index}"
  class_id: number,              // Selected class ID
  class_name: string,            // Display name
  x_center: number,              // [0, 1] normalized
  y_center: number,              // [0, 1] normalized
  width: number,                 // [0, 1] normalized
  height: number,                // [0, 1] normalized
  [source?: string],             // "ai" for pre-annotations (US-021)
  [confidence?: number],         // Confidence score from pre-annotation
}
```

**Important**: Coordinates are **YOLO format** (x_center, y_center, width, height) normalized to [0, 1], NOT pixel coordinates.

### 1.3 Move/Resize Capabilities
**YES — fully supported** (lines 211-356):
- **Draw mode** (default): Click-drag to create boxes
- **Select mode**: Click box to select → 8 resize handles (nw, n, ne, e, se, s, sw, w) with `data-handle` attribute
- **Delete mode**: Click to remove
- Drag offset tracking (line 232): `dragOffset = { x, y }` for smooth move
- Resize handle updates position correctly accounting for center-based coordinates (lines 265-305)

**Edge cases handled**:
- Min box size: `0.02` normalized (line 315)
- Boundary clamping: ensures boxes stay within [0, 1] bounds (lines 307-310)

### 1.4 Loading/Saving Annotations
**Load** (lines 126-151):
```javascript
GET /api/training/frames/{frameId}/annotations → setAnnotations(result.annotations)
```

**Save** (lines 153-179):
```javascript
POST /api/training/frames/{frameId}/annotations 
Body: { annotations: [...] }
```
- Sets `hasUnsavedChanges = false` on success
- Auto-saves when switching frames (line 183)
- No pre_annotations loading logic

### 1.5 Classes Management
- Fetches from `/api/classes` on mount (line 165)
- Dropdown shows existing + option to create new
- New class POST to `/api/classes` (lines 382-393)
- Default fallback: 6 hardcoded EPI classes (lines 5-6)

### 1.6 Timeline at Bottom
- Loads frames from same video (line 90)
- Shows thumbnails with annotation status dot (line 497)
- Clicking thumbnail switches frame (auto-saves previous)
- No polling or status refresh — static load on mount

---

## 2. TrainingPage.tsx Analysis

**File**: `/frontend/src/pages/TrainingPage.tsx`  
**Size**: 1149 lines  

### 2.1 Video States and Polling

**Video Status Values**:
- `uploaded` — File in R2/storage, not extracted yet
- `extracting` — FFmpeg extracting frames (3s polling)
- `extracted` — Ready for annotation
- `error` — Extraction failed

**Polling Logic** (lines 189-209):
```javascript
setInterval(async () => {
  const res = await api.get(`/v1/videos/{v.id}/status`)
  if (video.status !== 'extracting') {
    loadData()
    loadStorage()
  }
}, 3000)  // every 3 seconds while extracting
```

Polling stops once status changes from `extracting`.

### 2.2 Status Transitions Handled
1. Upload → set status=`uploaded` (line 302)
2. Upload complete → call `runBrowserExtraction()` (line 306)
3. Extraction started → set status=`extracting` (line 361)
4. Polling detects status change → call `loadData()` (line 201)
5. Frames become available → filtered by `status === 'extracted'` (line 213)

**NO explicit "Pré-anotando" or "23/60 38%" display** — that's backend work, not reflected in video status.

### 2.3 Upload Flow

**Step 1**: Request presigned URL (line 229)
```javascript
POST /v1/videos/upload-url
Body: { filename, content_type, file_size }
Response: { upload_url, video_id, storage_key }
```

**Step 2**: Upload file (line 260-281)
- Production: PUT directly to R2 (line 269)
- Fallback: POST multipart to Flask (line 285)
- Real byte-level progress via `xhr.upload.onprogress` (lines 241, 264, 287)

**Step 3**: Notify backend (line 281)
```javascript
POST /v1/videos/{video_id}/upload-complete
```

**Step 4**: Start server extraction (line 306)
```javascript
runBrowserExtraction → POST /v1/videos/{videoId}/server-extract
```

**No upload-complete confirmation in TrainingPage** — fires "best effort" (line 281 comment).

### 2.4 FrameTimeline Integration
**Opened via**: `openTimeline(video)` (line 402) → sets `frameTimelineVideo`

**Props passed**:
```jsx
<FrameTimeline
  frames={frameCache[frameTimelineVideo.id]}
  videoName={frameTimelineVideo.original_filename}
  apiBase={apiBase}
  onAnnotate={handleAnnotate}
  onPreAnnotate={handlePreAnnotate}  // ← Pre-annotation callback
  onClose={() => setFrameTimelineVideo(null)}
/>
```

**Frame loading** (lines 391-399):
```javascript
loadFramesRef.current = async (videoId: string) => {
  const res = await api.get(`/training/videos/{videoId}/frames`)
  const frames: FrameInfo[] = Array.isArray(data) ? data : (data?.frames || [])
  setFrameCache(prev => ({ ...prev, [videoId]: frames }))
}
```

### 2.5 Pre-Annotation Handler
**Function** (lines 416-423):
```javascript
const handlePreAnnotate = useCallback(async (frameId: string) => {
  try {
    await api.post(`/frames/{frameId}/pre-annotate`, {})
    toast.success('Pre-anotacao iniciada')
  } catch (err) {
    toast.error(err instanceof Error ? err.message : 'Erro ao pre-anotar')
  }
}, [])
```

**NO feedback on completion** — just a success toast. No cache refresh, no frame reload, no polling for pre-annotation status.

### 2.6 WebSocket for Training Progress
**Hook** (line 14): `useTrainingSocket`
**Purpose**: Live job status updates during training (not extraction)
**Data**: `liveJobs` array with training metrics
**NOT used for**: Pre-annotation, extraction, or frame status

### 2.7 Validation Stats Display
**Loaded** (lines 131-158):
```javascript
GET /api/training/videos/{v.id}/validation-stats → { annotated, validated, total }
```

**Displays** in AnnotationPage (lines 74-84 of AnnotationPage.tsx): 
- Total frames
- Annotated count (green)
- Validated count (blue)
- Warning if < 20 validated (amber)

---

## 3. AnnotationPage.tsx Analysis

**File**: `/frontend/src/pages/AnnotationPage.tsx`  
**Purpose**: Video selector + validation panel + AnnotationInterface wrapper  

### 3.1 Page Flow
1. **Video List** (lines 187-202): Grid of extracted videos
2. **Video Detail** (lines 100-168): Back button + "Anotar Frames" button + stats + validation queue
3. **Full-Screen Annotation** (lines 91-95): AnnotationInterface in full-screen mode

### 3.2 Raw fetch() Calls (NOT using api.ts wrapper)
**Lines 54-62**:
```javascript
const [framesRes, statsRes] = await Promise.all([
  fetch(`/api/training/videos/{videoId}/frames`, {
    headers: { Authorization: authHeader },
  }).then(r => r.json()),
  fetch(`/api/training/videos/{videoId}/validation-stats`, {
    headers: { Authorization: authHeader },
  }).then(r => r.json()),
])
```

**Issue** (noted in CLAUDE.md): Uses raw `fetch()` instead of `api.ts` wrapper — no retry, no error handling beyond console.error.

### 3.3 Frame Validation Handler
**Lines 71-87**:
```javascript
POST /api/training/frames/{frameId}/validate
// Response: { success: true, validated_at: timestamp }
// Updates stats in place
```

---

## 4. Backend Integration Points

### 4.1 Frame Routes (`/backend/app/api/v1/frames/routes.py`)

**Line 40-44**: Pre-annotation endpoint
```python
@frames_bp.route("/<frame_id>/pre-annotate", methods=["POST"])
@jwt_required()
def trigger_pre_annotate(frame_id: str):
    return _proxy_post(f"/api/v1/pre-annotate/{frame_id}", {})
```

**Proxies to**: `pre-annotation-service:8080` (line 19)  
**Timeout**: 300s (line 29)  
**Response**: Success/error envelope

### 4.2 Annotation Service (`/backend/app/domain/services/annotation_service.py`)

**Lines 42-107**: `get_frame_annotations()` with US-021 fallback
```python
def get_frame_annotations(self, frame_id: UUID, user_id: UUID | None = None) -> list[dict]:
    """If no human annotations, fallback to pre_annotations from DB."""
    annotations = self._annotation_repo.get_by_frame(frame_id)
    if annotations:
        return annotations  # human-annotated — use as-is
    
    # No human annotations — try pre_annotations JSONB column
    pre = self._frame_repo.get_pre_annotations(frame_id)
    if not pre:
        return []
    
    # Convert pre_annotations to annotation format
    result = []
    for i, p in enumerate(pre):
        bbox = p.get("bbox", [0.5, 0.5, 0.1, 0.1])
        label = (p.get("label") or "").lower().strip()
        class_id = class_map.get(label) or 1  # map label → class_id
        
        result.append({
            "id": f"pre-{i}",
            "class_id": class_id,
            "class_name": p.get("label") or "Desconhecido",
            "x_center": bbox[0],
            "y_center": bbox[1],
            "width": bbox[2],
            "height": bbox[3],
            "source": "ai",
            "confidence": p.get("confidence"),
        })
    
    return result
```

**CRITICAL**: This fallback logic **EXISTS but is NOT reached** because:
- Frontend AnnotationInterface calls `GET /api/training/frames/{id}/annotations` directly (raw fetch, line 131)
- This endpoint likely uses `annotation_repo.get_by_frame()` only, not the fallback
- Need to verify which endpoint AnnotationInterface actually calls

### 4.3 Frame Repository
**Line 108-116**: `get_pre_annotations()`
```python
def get_pre_annotations(self, frame_id: UUID) -> "list[dict] | None":
    row = self._execute_one(
        "SELECT pre_annotations FROM training_frames WHERE id = %s",
        (frame_id,)
    )
    return row.get("pre_annotations") if row else None
```

**Storage**: `pre_annotations` JSONB column in `training_frames` table

---

## 5. Data Format Contracts

### 5.1 Pre-Annotation Format (from DINO+SAM)
```json
{
  "bbox": [0.5, 0.5, 0.3, 0.4],  // [x_center, y_center, width, height]
  "label": "helmet",
  "confidence": 0.92
}
```

### 5.2 AnnotationInterface Annotation Format
```json
{
  "id": "annotation-1234567890",
  "class_id": 2,
  "class_name": "Capacete",
  "x_center": 0.5,
  "y_center": 0.5,
  "width": 0.3,
  "height": 0.4,
  "source": "ai",           // only if from pre-annotation
  "confidence": 0.92        // optional
}
```

### 5.3 Video Status Machine
```
uploaded → extracting → extracted
                     ↘ error
```

### 5.4 Frame Annotation Status (FrameTimeline)
```javascript
annotation_status?: 'annotated' | 'pre_annotated' | 'empty'
// Used for badge display:
// ✓ = annotated
// ◎ = pre_annotated
// ○ = empty
```

---

## 6. Current Gaps & Issues

### 6.1 Pre-Annotations Not Loaded in UI
**Issue**: AnnotationInterface never displays pre_annotations, even if available.

**Root Cause**: 
- `GET /api/training/frames/{id}/annotations` endpoint doesn't apply US-021 fallback
- OR the endpoint exists elsewhere and AnnotationInterface calls the wrong one
- **Action**: Verify which endpoint AnnotationInterface actually hits (search backend routes)

### 6.2 No Feedback on Pre-Annotation Completion
**Issue**: `handlePreAnnotate()` fires a success toast but doesn't:
- Wait for completion
- Reload frame annotations
- Update frame status to `pre_annotated`
- Poll for success

**Root Cause**: Async fire-and-forget architecture. Pre-annotation-service runs async.

### 6.3 FrameTimeline Status Not Refreshed
**Issue**: After clicking "Pre-anotar", FrameTimeline shows no change to frame badge.

**Root Cause**: Frame cache loaded once, never refreshed. No polling or WebSocket for pre-annotation events.

### 6.4 Raw fetch() in AnnotationPage
**Issue**: Uses raw `fetch()` instead of `api.ts` wrapper for validation calls.

**Root Cause**: Component predates `api.ts` migration.

### 6.5 Classes Data Format
**Issue**: AnnotationInterface expects classes with `id` and `color`, but unclear if backend returns this format.

**Root Cause**: `/api/classes` endpoint not verified.

---

## 7. Key Findings Summary

| Aspect | Status | Notes |
|--------|--------|-------|
| **AnnotationInterface frozen** | ✓ | Never modify. Self-contained. ~1000 lines. |
| **Move/Resize supported** | ✓ | 8 resize handles, drag offset tracking, boundary clamping. |
| **Props contract** | Simple | `videoId` (string), `onBack` (fn). No pre_annotations prop. |
| **Data format** | YOLO | x_center, y_center, width, height [0,1]. |
| **Load annotations** | `GET /api/training/frames/{id}/annotations` | Raw fetch, no error recovery. |
| **Save annotations** | `POST /api/training/frames/{id}/annotations` | Auto-save on frame switch. |
| **Pre-annotations available** | Partial | Backend has fallback (US-021) but frontend doesn't use it. |
| **Pre-annotation UI button** | Exists | FrameTimeline has "Pre-anotar com IA" button (line 82). |
| **Pre-annotation feedback** | None | Toast only, no status update or cache refresh. |
| **WebSocket** | Training only | `useTrainingSocket` for job progress, not extraction/pre-annotation. |
| **Video polling** | 3s interval | Stops when status != `extracting`. |
| **Upload flow** | Complete | Presigned URL → R2 PUT/multipart → upload-complete → extraction. |

---

## 8. Implementation Readiness

### What's READY to Use
- AnnotationInterface full feature set (draw, move, resize, delete, classes, save)
- TrainingPage video upload and status polling
- FrameTimeline with keyboard navigation and timeline scrubbing
- Backend annotation_service fallback logic (US-021)

### What NEEDS Work
- Frontend integration of pre_annotations into AnnotationInterface
- Pre-annotation completion feedback and cache refresh
- Frame status badge updates after pre-annotation
- Verification of `/api/training/frames/{id}/annotations` endpoint behavior
- Migration of AnnotationPage validation calls from raw fetch() to api.ts

---

## 9. Next Steps (For Implementation Phase)

1. **Verify Backend Endpoint**: Find which endpoint serves annotations to AnnotationInterface
   - Search for `GET /api/training/frames` handler
   - Confirm if it uses annotation_service.get_frame_annotations() with fallback

2. **Test US-021 Fallback**: 
   - Create frame with pre_annotations in DB
   - Call endpoint and verify pre_annotations returned in response

3. **Add Pre-Annotation Polling** (if needed):
   - Option A: Poll pre-annotation status after trigger
   - Option B: WebSocket event from pre-annotation-service
   - Option C: Manual refresh button

4. **Update FrameTimeline Frame Cache**:
   - Refresh after successful pre-annotation
   - Update annotation_status from response

5. **Migrate AnnotationPage to api.ts**:
   - Replace raw fetch() calls with api.get(), api.post()
   - Add proper error handling and retry

6. **Document Annotation Data Format**:
   - Add to CLAUDE.md with examples
   - Include mapping of label → class_id logic

---

## Appendix: File Locations

| Component | File | Lines | Key Functions |
|-----------|------|-------|----------------|
| AnnotationInterface | `/frontend/src/components/AnnotationInterface.jsx` | 1-1000 | loadFrames, loadAnnotations, saveAnnotations, handleMouseDown/Move/Up |
| TrainingPage | `/frontend/src/pages/TrainingPage.tsx` | 1-1149 | uploadFile, runBrowserExtraction, handlePreAnnotate, openTimeline |
| AnnotationPage | `/frontend/src/pages/AnnotationPage.tsx` | 1-200 | loadVideos, loadFramesAndStats, handleValidate |
| FrameTimeline | `/frontend/src/components/training/FrameTimeline.tsx` | 1-169 | goTo, goPrev, goNext, keyboard nav |
| Frames Routes | `/backend/app/api/v1/frames/routes.py` | 1-57 | trigger_pre_annotate, _proxy_post |
| Annotation Service | `/backend/app/domain/services/annotation_service.py` | 1-120+ | get_frame_annotations (US-021 fallback at line 42) |
| Frame Repository | `/backend/app/infrastructure/database/repositories/frame_repository.py` | 108-116 | get_pre_annotations |

