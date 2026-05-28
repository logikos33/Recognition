# backend/app/core/AGENTS.md

<!-- Parent: ../AGENTS.md -->

## Overview

The `core/` directory contains cross-cutting concerns used throughout the application: authentication, exception hierarchy, request/response standardization, validation, middleware, and WebSocket bridging.

**Key Principle**: No business logic here. Only framework utilities and security infrastructure.

---

## Module Breakdown

### auth.py — JWT and Password Utilities

**Purpose**: Password hashing with bcrypt, JWT token extraction, authentication decorators.

**Key Functions**:

| Function | Purpose | Returns |
|---|---|---|
| `hash_password(password: str)` | Hash password with bcrypt | hashed string (ready for DB) |
| `check_password(password: str, hash: str)` | Verify password against hash | bool |
| `get_current_user_id()` | Extract user_id from JWT token | UUID |
| `get_tenant_id()` | Extract tenant_id from JWT claims | str |
| `@jwt_required_custom` | Decorator: verify JWT + inject user_id | decorator |
| `@admin_required` | Decorator: verify JWT + inject user_id + admin flag | decorator |

**Usage**:

```python
from app.core.auth import hash_password, check_password, get_current_user_id

# Register
password_hash = hash_password("user_password")
db.users.insert(email="user@example.com", password_hash=password_hash)

# Login
user = db.users.find_by_email("user@example.com")
if check_password("user_password", user.password_hash):
    # Create JWT token in route
    token = create_access_token(identity=str(user.id))

# In protected route
@bp.route("/me")
@jwt_required  # Flask-JWT-Extended
def get_current_user():
    user_id = get_current_user_id()  # Raises AuthenticationError if invalid
    return success({"user_id": str(user_id)})
```

---

### exceptions.py — Exception Hierarchy

**Purpose**: Standardized exceptions with built-in HTTP status codes. Never expose stack traces to clients.

**Exception Tree**:

```
EpiMonitorError (base, status=500)
├── ValidationError (status=400)          — Invalid input
├── AuthenticationError (status=401)      — Invalid JWT or credentials
├── AuthorizationError (status=403)       — Valid JWT, no permission
├── NotFoundError (status=404)            — Resource doesn't exist
├── ConflictError (status=409)            — Resource already exists
├── StorageError (status=502)             — R2/S3 issues
├── DatabaseError (status=503)            — PostgreSQL issues
├── TrainingError (status=500)            — Vast.ai/YOLOv8 issues
├── InferenceError (status=500)           — YOLO runtime errors
└── StreamError (status=500)              — FFmpeg/HLS errors
```

**Usage**:

```python
from app.core.exceptions import (
    EpiMonitorError,
    ValidationError,
    NotFoundError,
    StorageError,
    AuthorizationError,
)

# In service
def get_user_by_id(user_id: UUID) -> User:
    user = self._user_repo.get_by_id(user_id)
    if not user:
        raise NotFoundError("User", str(user_id))  # 404
    return user

# In route
try:
    user = service.get_user_by_id(user_id)
    return success(user)
except EpiMonitorError as exc:
    return error(exc.message, status=exc.status_code)
```

**Rule**: Never catch and re-raise same exception. Transform at layer boundaries:

```python
# WRONG
except DatabaseError:
    raise DatabaseError("...")  # Same layer

# RIGHT — transform to domain exception
except psycopg2.Error as exc:
    raise DatabaseError(f"DB error: {str(exc)}")
```

---

### responses.py — Standardized JSON Responses

**Purpose**: Consistent response format for all API endpoints.

**Functions**:

| Function | Purpose | Returns |
|---|---|---|
| `success(data=None, message="OK", status=200)` | Success response | (json_body, status_code) |
| `error(message="...", status=400, error_code=None)` | Error response | (json_body, status_code) |

**Response Format**:

```python
# Success
{
  "success": true,
  "message": "OK",
  "data": {...}
}

# Error
{
  "success": false,
  "error": "Mensagem de erro legível",
  "error_code": "OPTIONAL_ERROR_CODE"  # only if provided
}
```

**Usage**:

```python
from app.core.responses import success, error

@bp.route("/resource", methods=["POST"])
def create_resource():
    try:
        service = _get_service()
        resource = service.create(...)
        return success(resource, status=201)  # (json, 201)
    except ValidationError as exc:
        return error(exc.message, status=400)  # (json, 400)
```

**Rule**: Never use `jsonify()` directly in routes. Always use `success()` or `error()`.

---

### validators.py — Input Validation

**Purpose**: Multi-layer validation of untrusted user input before processing.

**Classes**:

#### RTSPUrlValidator (Security: SEC-002)

Validates RTSP URLs to prevent command injection attacks on FFmpeg.

```python
from app.core.validators import RTSPUrlValidator
from app.core.exceptions import ValidationError

# Multi-layer validation
try:
    validated_url = RTSPUrlValidator.validate("rtsp://user:pass@192.168.1.100:554/...")
except ValidationError as exc:
    return error(exc.message, status=400)
```

**Validation Layers**:

1. **URL Length** — Max 2048 characters
2. **Dangerous Characters** — Blocks: `;|$\`\n\r`
3. **URL Format** — Must be valid URL (scheme, host, port)
4. **IP Validation** — Rejects loopback (127.x.x.x), multicast, reserved, 0.0.0.0
5. **Port Range** — 1-65535 only

**Important Note**: Credentials with special characters must be URL-encoded **before** reaching validator:

```python
# CORRECT — password URL-encoded
password_encoded = urllib.parse.quote("p@ss&word", safe="")
url = f"rtsp://admin:{password_encoded}@192.168.1.100:554/stream"
RTSPUrlValidator.validate(url)  # ✅ OK

# WRONG — password has '&' as literal
url = f"rtsp://admin:p@ss&word@192.168.1.100:554/stream"
RTSPUrlValidator.validate(url)  # ❌ ValidationError
```

#### VideoUploadValidator

Validates video filenames before presigned URL generation.

```python
from app.core.validators import VideoUploadValidator

# Validate extension
try:
    ext = VideoUploadValidator.validate_extension("video.mp4")  # ✅ OK
except ValidationError:
    # Invalid extension

# Sanitize filename
try:
    safe_name = VideoUploadValidator.sanitize_filename("my video (1).mp4")
    # Returns: "my_video_1.mp4"
except ValidationError:
    # Empty or invalid filename
```

**Rules**:
- Allowed extensions: `mp4`, `avi`, `mov`
- Max filename: 255 chars
- Removes: `<>:"/\|?*` and control chars
- Max size: 2GB

#### HLSFilenameValidator

Validates HLS playlist filenames to prevent path traversal.

```python
from app.core.validators import HLSFilenameValidator

# Validate HLS filename
try:
    filename = HLSFilenameValidator.validate("stream.m3u8")  # ✅ OK
except ValidationError:
    # Invalid HLS filename
```

**Rules**:
- Pattern: `[a-zA-Z0-9_-]+.(m3u8|ts)`
- Rejects: `..`, `/`, `\`

---

### middleware.py — Request Logging and Error Handling

**Purpose**: Global request/response logging and exception handling.

**Functionality**:

- **Request Logging**: Log all HTTP requests with method, path, IP
- **Response Logging**: Log response status and latency
- **Exception Handlers**: Catch unhandled exceptions and return standardized error responses
- **Security Headers**: Add `X-Content-Type-Options`, `X-Frame-Options`, etc.

**Registered in `app/__init__.py`**:

```python
from app.core.middleware import register_middleware

app = create_app()
register_middleware(app)
```

**Error Handler Pattern**:

```python
@app.errorhandler(404)
def handle_not_found(error):
    return error("Recurso não encontrado", status=404)

@app.errorhandler(500)
def handle_internal_error(error):
    logger.error("internal_error", exc_info=True)
    return error("Erro interno", status=500)
```

---

### socket_bridge.py — Redis → SocketIO Bridge

**Purpose**: Real-time event broadcasting. Worker publishes detections to Redis, Socket Bridge consumes and emits to browser via WebSocket.

**Architecture**:

```
Worker (Celery)
    ↓ redis.publish("det:camera-123", json)
Redis (pub/sub)
    ↓
Socket Bridge (Redis subscriber)
    ↓ socketio.emit(f"det_camera_123", data)
Browser (socket.io-client)
```

**Key Classes**:

| Class | Purpose |
|---|---|
| `SocketBridge` | Subscribes to Redis channels, emits to SocketIO |
| `start_redis_listeners(app, socketio)` | Initialize bridge on app startup |

**Usage**:

```python
# In worker (app/infrastructure/queue/tasks/inference.py)
from redis import Redis

redis = Redis.from_url(os.environ.get("REDIS_URL"))
detections = {...}
redis.publish(f"det:{camera_id}", json.dumps(detections))

# In SocketBridge
# Automatically subscribes to det:* channels
# Emits: socketio.emit(f"det_{camera_id}", detections)

# In frontend
socket.on("det_camera_123", (data) => {
    // Draw bounding boxes
})
```

**Channels Monitored**:

| Channel | Purpose |
|---|---|
| `det:*` | Detection broadcasts from inference tasks |
| `training:*` | Training job status updates |

---

## Integration Pattern

Here's how core modules work together in a typical flow:

```python
# 1. ROUTE (api/v1/cameras/routes.py)
@bp.route("/cameras", methods=["POST"])
@jwt_required
def create_camera():
    try:
        # 2. Extract auth
        user_id = get_current_user_id()  # from core.auth
        
        # 3. Validate input
        data = request.get_json()
        RTSPUrlValidator.validate(data.get("rtsp_url"))  # from core.validators
        
        # 4. Call service
        service = _get_camera_service()
        camera = service.create(user_id, data)
        
        # 5. Return response
        return success(camera, status=201)  # from core.responses
        
    except ValidationError as exc:
        return error(exc.message, status=400)  # from core.exceptions + responses
    except EpiMonitorError as exc:
        return error(exc.message, status=exc.status_code)
    except Exception as exc:
        logger.error("unexpected_error", exc_info=True)
        return error("Erro interno", status=500)
```

---

## Testing Core Modules

```bash
# Test password hashing
python -c "
from app.core.auth import hash_password, check_password
hash = hash_password('secret123')
assert check_password('secret123', hash)
assert not check_password('wrong', hash)
print('✅ Password hashing works')
"

# Test validators
python -c "
from app.core.validators import RTSPUrlValidator, VideoUploadValidator
RTSPUrlValidator.validate('rtsp://192.168.1.100:554/stream')
VideoUploadValidator.validate_extension('video.mp4')
print('✅ Validators work')
"

# Test exception handling
python -c "
from app.core.exceptions import NotFoundError
exc = NotFoundError('Camera', '123-abc')
assert exc.status_code == 404
assert 'não encontrado' in exc.message
print('✅ Exceptions work')
"
```

---

## Related Documentation

- **API Layer**: `../api/` — routes that use these utilities
- **Domain Layer**: `../domain/` — services that raise these exceptions
- **Infrastructure**: `../infrastructure/` — storage and database that raise exceptions
