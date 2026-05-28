<!-- Parent: ../AGENTS.md -->

# videos — Training Video Upload & Extraction

Direct upload, presigned URLs, and frame extraction trigger.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/videos/upload` | POST | Direct file upload (multipart/form-data, max 2GB) |
| `/api/v1/videos/upload-url` | POST | Get presigned upload URL for R2 direct upload |
| `/api/v1/videos/<id>/extract` | POST | Trigger Celery frame extraction task |
| `/api/v1/videos/<id>/status` | GET | Get video status + frame counts |

**Key Notes:**
- Allowed extensions: `.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`
- Upload creates record with status `pending` → `extracting` → `extracted`
- Direct upload: file stored as `raw-videos/{user_id}/{video_id}/{filename}`
- Presigned URL: auto-generates video record before upload completes
- Frame extraction: dispatches to Celery, returns 202 with status `extracting`
