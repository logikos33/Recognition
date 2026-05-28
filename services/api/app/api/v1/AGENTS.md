# backend/app/api/v1 — REST API Blueprints

<!-- Parent: ../AGENTS.md -->

## Overview

The `api/v1/` directory contains **13 Flask blueprints** that define all REST endpoints. Each blueprint is a separate domain: auth, cameras, streams, videos, training, etc.

**Key Principle**: Routes delegate to service layer. Never do business logic in routes.

---

## Directory Structure

```
api/v1/
├── auth/                  # Authentication (register, login, me)
│   ├── __init__.py
│   └── routes.py
├── cameras/               # Camera CRUD + stream control
│   ├── __init__.py
│   └── routes.py
├── streams/               # HLS status, health, public HLS files
│   ├── __init__.py
│   └── routes.py
├── videos/                # Video upload, list, metadata
│   ├── __init__.py
│   └── routes.py
├── frames/                # Frame list, metadata, labeling
│   ├── __init__.py
│   └── routes.py
├── training/              # Training job submission, status
│   ├── __init__.py
│   └── routes.py
├── datasets/              # Dataset CRUD, versions
│   ├── __init__.py
│   └── routes.py
├── dashboard/             # KPIs, Excel export
│   ├── __init__.py
│   └── routes.py
├── alerts/                # Alert list, filter, export, acknowledge
│   ├── __init__.py
│   └── routes.py
├── rules/                 # Detection rules
│   ├── __init__.py
│   └── routes.py
├── modules/               # Module enable/disable
│   ├── __init__.py
│   └── routes.py
├── reports/               # Report generation
│   ├── __init__.py
│   └── routes.py
├── storage/               # R2 health check
│   ├── __init__.py
│   └── routes.py
├── health/                # System health (no auth required)
│   ├── __init__.py
│   └── routes.py
└── annotations/           # Annotation CRUD (legacy)
    ├── __init__.py
    └── routes.py
```

---

## Blueprint Pattern

Every blueprint follows the same pattern:

### 1. `__init__.py` (empty)

```python
# Usually empty, or re-exports Blueprint
```

### 2. `routes.py` (all endpoints)

```python
"""
Module docstring explaining the domain.
"""
import logging

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error
from app.domain.services.my_service import MyService
from app.infrastructure.database.connection import DatabasePool

logger = logging.getLogger(__name__)

my_bp = Blueprint("my_domain", __name__, url_prefix="/api/v1/my_domain")


def _get_service() -> MyService:
    """Factory: creates service with dependencies."""
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return MyService(MyRepository(pool))


@my_bp.route("", methods=["GET"])
@jwt_required()
def list_items():
    """
    ---
    tags:
      - my_domain
    summary: List all items
    security:
      - Bearer: []
    responses:
      200:
        description: List of items
    """
    try:
        user_id = get_current_user_id()
        service = _get_service()
        items = service.list_items(user_id)
        return success(items)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_items_error: %s", exc, exc_info=True)
        return error("Internal error", 500)
```

### 3. Registration in `app/__init__.py`

```python
def _register_blueprints(app: Flask) -> None:
    """Register all API blueprints."""
    from app.api.v1.auth import routes as auth
    from app.api.v1.cameras import routes as cameras
    # ... more blueprints ...
    
    app.register_blueprint(auth.auth_bp)
    app.register_blueprint(cameras.cameras_bp)
    # ... more registrations ...
```

---

## Endpoint Categories

### Category 1: Public Endpoints (No JWT)

```python
# health/routes.py
@health_bp.route("", methods=["GET"])
def health_check():  # No @jwt_required()
    """System health check."""
    # ...
```

**Examples**:
- `GET /api/v1/health` — system health
- `GET /api/v1/streams/{id}/stream.m3u8` — HLS file (no auth headers in browser)

### Category 2: Authenticated Endpoints (JWT Required)

```python
# cameras/routes.py
@cameras_bp.route("", methods=["GET"])
@jwt_required()
def list_cameras():
    """List user's cameras."""
    user_id = get_current_user_id()
    # ...
```

**All other endpoints require `@jwt_required()`**.

### Category 3: Admin-Only Endpoints

```python
# modules/routes.py
@modules_bp.route("", methods=["GET"])
@jwt_required()
def list_modules():
    """Admin only: list modules."""
    user_id = get_current_user_id()
    # Check if admin
    repo = UserRepository(pool)
    user = repo.get_by_id(user_id)
    if user.get("role") != "admin":
        return error("Permission denied", 403)
    # ...
```

---

## Response Pattern (Mandatory)

All endpoints return standardized JSON:

### Success Response

```python
return success(data, status=200)
```

Returns:
```json
{
  "status": "success",
  "data": {...}
}
```

### Error Response

```python
return error("User not found", 404)
```

Returns:
```json
{
  "status": "error",
  "message": "User not found",
  "code": 404
}
```

**Rules**:
- Never expose stack traces
- Never expose SQL errors
- Never expose internal paths
- Never expose credentials

---

## Error Handling Pattern

Every endpoint must have try/except:

```python
@my_bp.route("/<id>", methods=["GET"])
@jwt_required()
def get_item(id: str):
    """Get item by ID."""
    try:
        user_id = get_current_user_id()
        service = _get_service()
        item = service.get_by_id(UUID(id), user_id)
        return success(item)
    except EpiMonitorError:  # Catch domain exceptions first
        raise  # Re-raise to error handler
    except Exception as exc:  # Generic fallback
        logger.error("get_item_error: %s", exc, exc_info=True)
        return error("Internal error", 500)
```

**Flow**:
1. Domain layer raises `EpiMonitorError` (or subclass)
2. Route re-raises it
3. Global error handler in `app/__init__.py` catches it
4. Returns formatted error response

**Exception Hierarchy**:
```python
EpiMonitorError (base)
├── ValidationError (400)
├── AuthenticationError (401)
├── AuthorizationError (403)
├── NotFoundError (404)
├── ConflictError (409)
├── DatabaseError (500)
├── StorageError (500)
└── InferenceError (500)
```

---

## Authorization Pattern

### Pattern 1: Operator sees only their resources

```python
@cameras_bp.route("/<camera_id>", methods=["GET"])
@jwt_required()
def get_camera(camera_id: str):
    """Get camera by ID."""
    try:
        user_id = get_current_user_id()
        service = _get_camera_service()
        camera = service.get_camera(UUID(camera_id))
        
        # Ownership check: operator vê só suas câmeras
        if str(camera["user_id"]) != str(user_id) and not _is_admin(user_id):
            return error("Permission denied", 403)
        
        return success(camera)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_camera_error: %s", exc, exc_info=True)
        return error("Internal error", 500)
```

### Pattern 2: Service-layer authorization (preferred)

Services handle authorization checks:

```python
# cameras/routes.py
@cameras_bp.route("/<camera_id>", methods=["GET"])
@jwt_required()
def get_camera(camera_id: str):
    """Get camera by ID."""
    try:
        user_id = get_current_user_id()
        service = _get_camera_service()
        # Service raises AuthorizationError if not owner
        camera = service.get_camera(UUID(camera_id), user_id)
        return success(camera)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_camera_error: %s", exc, exc_info=True)
        return error("Internal error", 500)
```

---

## Request/Response Serialization

### Input Validation

```python
@my_bp.route("", methods=["POST"])
@jwt_required()
def create_item():
    """Create item."""
    try:
        data = request.get_json() or {}
        # Extract and validate
        name = data.get("name", "").strip()
        if not name:
            return error("name is required", 400)
        
        service = _get_service()
        item = service.create(name)
        return success(item, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("create_item_error: %s", exc, exc_info=True)
        return error("Internal error", 500)
```

### UUID Handling

```python
# When receiving UUID from path
from uuid import UUID

@my_bp.route("/<item_id>", methods=["GET"])
@jwt_required()
def get_item(item_id: str):
    """Get item by ID."""
    try:
        item_uuid = UUID(item_id)  # Raises ValueError if invalid
        service = _get_service()
        item = service.get_by_id(item_uuid)
        return success(item)
    except ValueError:
        return error("Invalid ID format", 400)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_item_error: %s", exc, exc_info=True)
        return error("Internal error", 500)
```

### Dict/List Response

```python
# Return dicts, not objects
item = service.get_item()  # service returns dict
return success(item)  # JSON serializes dict

# List with pagination
items = service.list_items(limit=20, offset=0)
return success({
    "items": items,
    "count": len(items),
    "total": 100,
    "page": 1,
})
```

---

## Related Documentation

- **Services**: `../domain/services/` — business logic called by routes
- **Exceptions**: `../core/exceptions.py` — error handling
- **Responses**: `../core/responses.py` — response formatting
- **Auth**: `../core/auth.py` — JWT token handling
