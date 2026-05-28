# backend/app/domain/models — Dataclass Models

<!-- Parent: ../AGENTS.md -->

## Overview

The `models/` directory contains **immutable dataclasses** representing domain entities. Models are pure data structures with no logic.

**Key Principle**: Models are frozen dataclasses. They represent database rows, not business logic.

---

## Directory Structure

```
domain/models/
├── __init__.py           # Empty or imports all models
├── user.py               # User entity
├── camera.py             # Camera IP entity
├── video.py              # Video metadata entity
├── frame.py              # Frame (extracted from video)
├── annotation.py         # Annotation (label on frame)
├── dataset.py            # Dataset (collection of frames)
├── training_job.py       # Training job metadata
└── alert.py              # Alert (EPI violation)
```

---

## Model Pattern

### Basic Structure

```python
"""Domain model: EntityName."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.constants import EntityStatus


@dataclass(frozen=True)
class EntityName:
    """Brief description of entity."""
    
    id: UUID
    user_id: UUID
    name: str
    status: EntityStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
```

### Rules

1. **Always frozen**: `@dataclass(frozen=True)` — immutable
2. **No methods**: Only auto-generated `__init__`, `__eq__`, `__repr__`
3. **All fields explicit**: No hidden properties
4. **UUIDs for IDs**: `id: UUID`, `user_id: UUID`
5. **datetime for timestamps**: `created_at: datetime`
6. **Enums for status**: `status: EntityStatus` (from `app.constants`)
7. **Optional for nullable**: `Optional[type]` for nullable columns
8. **Field order**: ID first, then user_id, then business fields, then timestamps

---

## Model Examples

### User Model

```python
# domain/models/user.py
"""Domain model: User."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.constants import UserRole


@dataclass(frozen=True)
class User:
    """Usuário do sistema EPI Monitor."""
    
    id: UUID
    email: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    password_hash: str = ""  # Never returned to client
```

**Field mapping** (database → model):
```sql
SELECT id, email, name, role, is_active, created_at, updated_at, password_hash
FROM users
```

### Camera Model

```python
# domain/models/camera.py
"""Domain model: Camera."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.constants import CameraStatus


@dataclass(frozen=True)
class Camera:
    """Câmera IP para monitoramento."""
    
    id: UUID
    user_id: UUID
    name: str
    location: Optional[str]
    description: Optional[str]
    manufacturer: str
    host: str
    port: int
    username: str
    channel: int
    subtype: int
    rtsp_url_override: Optional[str]
    is_active: bool
    last_seen: Optional[datetime]
    created_at: datetime
```

**Field meanings**:
- `manufacturer`: "intelbras", "hikvision", "generic"
- `host`: IP address (e.g., "192.168.1.100")
- `port`: RTSP port (default 554)
- `username`: RTSP username for authentication
- `channel`: For multi-channel devices (Hikvision: 1-4)
- `subtype`: Stream subtype (usually 0)
- `rtsp_url_override`: Custom RTSP URL if auto-generation fails

---

## Using Models

### In Repositories (Infrastructure)

Repositories convert database rows to models:

```python
# infrastructure/database/repositories/user_repository.py
from app.domain.models.user import User

class UserRepository:
    def get_by_id(self, user_id: UUID) -> User | None:
        """Get user by ID."""
        with self._db.get_connection() as conn:
            cur = conn.cursor(RealDictCursor)
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                return None
            return User(**row)  # Convert row to model
```

### In Services (Domain)

Services work with models or dicts:

```python
# domain/services/auth_service.py
class AuthService:
    def get_user(self, user_id: UUID) -> dict:
        """Get user."""
        user = self._user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("User", str(user_id))
        return dict(user)  # Convert model to dict for JSON
```

### In Routes (API)

Routes receive dicts from services, return JSON:

```python
# api/v1/auth/routes.py
@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """Get current user."""
    try:
        user_id = get_current_user_id()
        service = _get_auth_service()
        user = service.get_user(user_id)  # dict
        return success(user)  # JSON response
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("me_error: %s", exc, exc_info=True)
        return error("Internal error", 500)
```

---

## Model Conversion

### Row → Model → Dict → JSON

```python
# 1. Row from database
row = {"id": "...", "email": "test@example.com", ...}

# 2. Convert to model
user = User(**row)

# 3. Convert to dict
user_dict = dict(user)

# 4. JSON serialization (Flask does this)
response = success(user_dict)  # {"status": "success", "data": {...}}
```

---

## Common Patterns

### Pattern 1: Optional Fields

```python
@dataclass(frozen=True)
class Camera:
    id: UUID
    name: str
    location: Optional[str]  # Can be None
    description: Optional[str] = None  # Default None
```

### Pattern 2: Default Values

```python
@dataclass(frozen=True)
class Video:
    id: UUID
    filename: str
    duration_seconds: Optional[int] = None  # Default None
    frame_count: int = 0  # Default 0
```

### Pattern 3: Status Enum

```python
from app.constants import VideoStatus

@dataclass(frozen=True)
class Video:
    id: UUID
    status: VideoStatus  # Use enum, never string
```

### Pattern 4: Timestamp Handling

```python
@dataclass(frozen=True)
class Entity:
    id: UUID
    created_at: datetime  # Always timezone-aware
    updated_at: Optional[datetime] = None  # Can be None
```

---

## Testing Models

Models are simple dataclasses, minimal testing needed:

```python
# tests/unit/test_models.py
from app.domain.models.user import User
from app.constants import UserRole
from datetime import datetime
from uuid import UUID

def test_user_model():
    """Test User model creation."""
    user = User(
        id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        email="test@example.com",
        name="Test User",
        role=UserRole.OPERATOR,
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    assert user.email == "test@example.com"
    assert user.role == UserRole.OPERATOR

def test_user_model_immutable():
    """Test that User model is immutable."""
    user = User(...)
    with pytest.raises(AttributeError):
        user.email = "new@example.com"  # Raises because frozen=True
```

---

## Related Documentation

- **Services**: `../services/` — use these models
- **Constants**: `../../constants.py` — enums used in models
- **Repositories**: `../../infrastructure/database/repositories/` — convert rows to models
