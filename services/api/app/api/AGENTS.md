# backend/app/api/AGENTS.md

<!-- Parent: ../AGENTS.md -->

## Overview

The `api/` directory contains Flask blueprints organized by domain. All routes define API endpoints with URL prefix `/api/v1/{domain}`.

**Key Architectural Principle**: Routes are thin delegators. All business logic lives in `domain/services/`. All database access lives in `infrastructure/database/repositories/`.

---

## Directory Structure

```
api/
└── v1/                    # API v1 endpoints
    ├── auth/              # register, login, me
    ├── cameras/           # CRUD, stream control, RTSP testing
    ├── datasets/          # dataset operations
    ├── frames/            # frame operations, quality scoring
    ├── annotations/       # frame annotations, labels
    ├── videos/            # upload, transcoding
    ├── training/          # training jobs, model management
    ├── modules/           # YOLO module info, deployment
    ├── reports/           # reporting, Excel export
    ├── rules/             # rules engine
    ├── storage/           # presigned URLs
    ├── streams/           # HLS streams (public, no JWT)
    ├── alerts/            # alert configuration
    ├── dashboard/         # KPIs, analytics
    └── health/            # /api/health (public, no JWT)
```

---

## Route Organization Pattern

Each domain blueprint (`auth/`, `cameras/`, etc.) follows this structure:

```python
# {domain}/routes.py

from flask import Blueprint

{domain}_bp = Blueprint("{domain}", __name__, url_prefix="/api/{domain}")

def _{domain}_service() -> {DomainService}:
    """Factory: injects dependencies."""
    pool = DatabasePool.get_instance()
    return {DomainService}(
        {repo_name}(pool),
        storage_strategy,  # if needed
        celery=celery,     # if needed
    )

@{domain}_bp.route("/...", methods=["POST"])
@jwt_required  # unless public endpoint
def create_resource():
    """Docstring with Swagger YAML (flasgger auto-parses)."""
    try:
        service = _{domain}_service()
        result = service.create(...)
        return success(result, status=201)
    except EpiMonitorError as exc:
        return error(exc.message, status=exc.status_code)
```

---

## Core Patterns

### 1. No Business Logic in Routes

```python
# WRONG — logic in route
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if User.exists(data["email"]):
        raise ConflictError(...)
    return success(...)

# RIGHT — route delegates to service
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    service = _get_auth_service()
    user = service.register(data["email"], data["password"], data["name"])
    return success(user, status=201)
```

### 2. All Errors are EpiMonitorError

```python
# Every route wraps responses in try/except
@bp.route("/resource/<id>")
def get_resource(id):
    try:
        service = _get_service()
        resource = service.get_by_id(id)
        return success(resource)
    except EpiMonitorError as exc:
        return error(exc.message, status=exc.status_code)
    except Exception as exc:
        logger.error("unexpected_error", error=str(exc), exc_info=True)
        return error("Erro interno", status=500)
```

### 3. JWT Security (Except Public Endpoints)

```python
from flask_jwt_extended import jwt_required
from app.core.auth import get_current_user_id

# Protected route — requires valid JWT
@bp.route("/my-resources")
@jwt_required
def list_my_resources():
    user_id = get_current_user_id()
    service = _get_service()
    resources = service.list_by_user(user_id)
    return success(resources)

# Public route — streams and health only
@bp.route("/streams/<camera_id>/<filename>")
def get_hls_file(camera_id, filename):
    """No JWT required for HLS streaming."""
    data = get_hls_file(camera_id, filename)
    return send_file(data, mimetype="application/x-mpegURL")
```

### 4. Swagger Documentation via Docstring YAML

All routes have Swagger YAML in docstrings. Flasgger auto-parses:

```python
@bp.route("/videos", methods=["POST"])
@jwt_required
def upload_video():
    """
    ---
    tags:
      - videos
    summary: Upload a new video
    parameters:
      - in: formData
        name: file
        type: file
        required: true
        description: Video file (mp4, avi, mov)
      - in: formData
        name: dataset_id
        type: string
        required: true
        description: Target dataset UUID
    responses:
      201:
        description: Video uploaded successfully
        schema:
          properties:
            success: {type: boolean}
            data:
              properties:
                id: {type: string}
                presigned_url: {type: string}
      400:
        description: Invalid input (unsupported format, filename too long)
      401:
        description: Missing or invalid JWT
      403:
        description: User not authorized for this dataset
      502:
        description: Storage error (R2 unreachable)
    """
    try:
        # implementation
    except EpiMonitorError as exc:
        return error(exc.message, status=exc.status_code)
```

---

## Public vs Protected Endpoints

| Endpoint | JWT Required | Purpose |
|---|---|---|
| `POST /api/auth/register` | NO | Register new user |
| `POST /api/auth/login` | NO | Authenticate and get token |
| `GET /api/auth/me` | YES | Get current user info |
| `GET /api/health` | NO | Health check (database, storage) |
| `GET /streams/<camera_id>/<filename>` | NO | HLS stream files (m3u8, ts) |
| `GET /api/streams/status` | NO | Public stream status |
| All other routes | YES | Requires valid JWT in Authorization header |

---

## Dependency Injection Pattern

Each route group has a factory function that creates service instances:

```python
def _get_auth_service() -> AuthService:
    """Factory: creates AuthService with all dependencies injected."""
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return AuthService(UserRepository(pool))
```

This pattern:
- Makes testing easier (mock repositories)
- Avoids global state (no singletons except DatabasePool)
- Makes dependency graphs explicit
- Allows adding new dependencies without touching all routes

---

## Common Endpoints by Domain

### auth/
- `POST /api/auth/register` — Register new user
- `POST /api/auth/login` — Login, return JWT token
- `GET /api/auth/me` — Get current user profile

### cameras/
- `GET /api/cameras` — List user's cameras
- `POST /api/cameras` — Create new camera (auto-generates RTSP URL)
- `GET /api/cameras/{id}` — Get camera by ID
- `PUT /api/cameras/{id}` — Update camera
- `DELETE /api/cameras/{id}` — Delete camera
- `POST /api/cameras/{id}/stream/start` — Start HLS stream + YOLO
- `POST /api/cameras/{id}/stream/stop` — Stop stream
- `GET /api/cameras/{id}/stream/status` — Stream status
- `POST /api/cameras/test` — Test RTSP connectivity

### streams/
- `GET /streams/<camera_id>/<filename>` — Serve HLS files (m3u8, ts)
- `GET /api/streams/status` — Status of all streams (public)
- `GET /api/streams/health` — Health report (public)

### videos/
- `POST /api/videos` — Get presigned upload URL
- `GET /api/videos/{id}` — Get video metadata
- `DELETE /api/videos/{id}` — Delete video

### frames/
- `GET /api/frames/{id}` — Get frame with quality scores
- `POST /api/frames/{id}/download` — Get download URL

### annotations/
- `POST /api/annotations` — Create frame annotation
- `GET /api/annotations/{id}` — Get annotation
- `PUT /api/annotations/{id}` — Update annotation

### training/
- `POST /api/training/jobs` — Start training job on Vast.ai
- `GET /api/training/jobs/{id}` — Get job status
- `POST /api/training/jobs/{id}/cancel` — Cancel job

### reports/
- `POST /api/reports/export` — Export dataset as Excel

### health/
- `GET /api/health` — System health check

---

## Error Handling

All routes follow the same error handling pattern:

```python
@bp.route("/.../...")
def my_endpoint():
    try:
        service = _get_service()
        result = service.do_something()
        return success(result)
    except ValidationError as exc:
        return error(exc.message, status=400)  # 400
    except NotFoundError as exc:
        return error(exc.message, status=404)  # 404
    except AuthorizationError as exc:
        return error(exc.message, status=403)  # 403
    except StorageError as exc:
        return error(exc.message, status=502)  # 502
    except EpiMonitorError as exc:
        return error(exc.message, status=exc.status_code)
    except Exception as exc:
        logger.error("unexpected_error", exc_info=True)
        return error("Erro interno", status=500)  # 500
```

All exceptions inherit from `EpiMonitorError` with explicit `status_code`. Routes return appropriate HTTP codes.

---

## Testing Blueprint Routes

```bash
# Test register
curl -X POST http://localhost:5001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"pass123","name":"Test"}'

# Get token
TOKEN=$(curl -s -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"pass123"}' \
  | jq -r '.data.access_token')

# Use token
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:5001/api/auth/me
```

---

## Related Documentation

- **Swagger/API Docs**: Auto-generated at `/api/docs` (flasgger)
- **Core Layer**: `../core/` — auth, exceptions, responses, validators
- **Domain Services**: `../domain/services/` — business logic
- **Repositories**: `../infrastructure/database/repositories/` — database access
