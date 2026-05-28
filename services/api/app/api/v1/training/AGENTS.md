<!-- Parent: ../AGENTS.md -->

# training — Video Training Pipeline

Video upload, frame extraction, annotation, YOLO classes, and training jobs.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/training/videos` | GET | List user's training videos |
| `/api/training/videos` | POST | Register video file upload |
| `/api/training/videos/<id>/frames` | GET | List approved frames for annotation (AnnotationInterface.jsx) |
| `/api/training/frames/<id>/image` | GET | Serve frame image (redirects to R2 presigned URL or local file) |
| `/api/training/frames/<id>/annotations` | GET/POST | Get/save frame annotations (YOLO normalized format) |
| `/api/classes` | GET/POST | List/create YOLO classes for user |
| `/api/training/jobs` | GET/POST | List/create training jobs (preset, model_size, epochs) |
| `/api/training/jobs/<id>/status` | GET | Get job status |
| `/api/training/models` | GET | List trained models |
| `/api/training/models/<id>/activate` | POST | Activate model for inference |
| `/api/cameras/<id>/alerts` | GET | List alerts for camera (limit, offset) |
| `/api/alerts/<id>/acknowledge` | POST | Acknowledge alert |

**Key Notes:**
- AnnotationInterface.jsx requires frame list + image URLs + annotation format
- Annotations format: `{class_id, x_center, y_center, width, height}` (normalized 0-1)
- Frame image: auto-redirects to R2 presigned URL if available (fallback: local storage)
- Path traversal guard on frame file serving
- Classes linked to user, annotations linked to frames
