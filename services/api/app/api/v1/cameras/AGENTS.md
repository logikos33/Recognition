<!-- Parent: ../AGENTS.md -->

# cameras — IP Camera Management

CRUD for IP cameras + stream control + YOLO model assignment.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cameras` | GET | List user's cameras (with gateway/inference status) |
| `/api/cameras` | POST | Create camera (auto-encrypts password with Fernet) |
| `/api/cameras/<id>` | GET/PUT/DELETE | Read, update, delete camera |
| `/api/cameras/<id>/stream/start` | POST | Start HLS + YOLO (gateway dispatch or Celery fallback) |
| `/api/cameras/<id>/stream/stop` | POST | Stop stream, delete Redis active key |
| `/api/cameras/<id>/stream/status` | GET | Check if streaming (TTL, gateway online) |
| `/api/cameras/<id>/test` | POST | 5-check diagnostics (URL, DNS, TCP, RTSP, ffprobe) |
| `/api/cameras/<id>/model` | GET/PUT | Get/set active YOLO model per camera |
| `/api/cameras/<id>/stream/<filename>` | GET | Serve HLS segments (no JWT — browsers can't send auth headers) |

**Key Notes:**
- Passwords NEVER returned in API (Fernet encryption)
- Operator sees only own cameras; admin sees all
- Gateway dispatch checks `service:gateway:health` Redis key
- Test endpoint returns structured 5-check result with suggestions
- HLS path validation: regex `^[a-zA-Z0-9_.-]+$` prevents path traversal
