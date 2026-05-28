# backend/app/domain/AGENTS.md

<!-- Parent: ../AGENTS.md -->

## Overview

The `domain/` directory contains pure business logic: models (dataclasses) and services (use cases). This layer knows **nothing** about Flask, Celery, PostgreSQL, or R2.

**Key Principle**: Domain is the most reusable, testable layer. All dependencies are injected, no global state.

---

## Directory Structure

```
domain/
├── models/              # Dataclasses per entity
│   ├── user.py
│   ├── camera.py
│   ├── video.py
│   ├── frame.py
│   ├── annotation.py
│   ├── dataset.py
│   ├── training_job.py
│   └── alert.py
└── services/            # Use cases per domain
    ├── auth_service.py
    ├── camera_service.py
    ├── video_service.py
    ├── frame_service.py
    ├── annotation_service.py
    ├── dataset_service.py
    ├── training_service.py
    ├── inference_service.py
    ├── module_service.py
    ├── report_service.py
    └── alert_service.py
```

---

## Models (Dataclasses)

Models are **immutable dataclasses** representing domain entities. No methods, no logic.

### Example: User Model

```python
# domain/models/user.py
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.constants import UserRole

@dataclass(frozen=True)
class User:
    """Usuário do sistema."""
    
    id: UUID
    email: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    password_hash: str = ""  # Never sent to client
```

### Example: Camera Model

```python
@dataclass(frozen=True)
class Camera:
    """Câmera IP para streaming HLS."""
    
    id: UUID
    user_id: UUID
    name: str
    manufacturer: str  # "intelbras", "hikvision", "generic"
    ip: str
    port: int
    channel: int | None
    username: str
    password_encrypted: str  # Fernet-encrypted, never sent to client
    rtsp_url: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
```

### Rules for Models

1. **Frozen dataclasses** — `@dataclass(frozen=True)` to enforce immutability
2. **No methods** — Only `__init__`, `__eq__`, `__repr__` (auto)
3. **All fields explicit** — No hidden properties
4. **Sensible types** — UUID for IDs, datetime for timestamps, enums for status
5. **Never expose secrets** — Password fields excluded from responses
6. **Match database columns** — Field names match PostgreSQL column names

---

## Services (Use Cases)

Services contain business logic. Each service receives repositories and collaborators via **dependency injection**.

### Example: AuthService

```python
# domain/services/auth_service.py
import logging
from uuid import UUID

from app.core.auth import check_password, hash_password
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.infrastructure.database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

class AuthService:
    """Use cases de autenticação."""

    def __init__(self, user_repo: UserRepository) -> None:
        """DI: repository injected."""
        self._user_repo = user_repo

    def register(
        self, email: str, password: str, name: str
    ) -> dict:
        """Registra novo usuário. Retorna dict (sem hash)."""
        # Validation
        email = email.strip().lower()
        name = name.strip()
        if not all([email, password, name]):
            raise ValidationError("email, password e name são obrigatórios")
        if len(password) < 6:
            raise ValidationError("Senha: mínimo 6 caracteres")

        # Check conflict
        if self._user_repo.exists_by_email(email):
            raise ConflictError("Email já cadastrado")

        # Hash and persist
        hashed = hash_password(password)
        user = self._user_repo.create(email, hashed, name)
        
        # Return without password
        user["id"] = str(user["id"])
        return user

    def login(self, email: str, password: str) -> dict:
        """Autentica usuário. Retorna dict (sem hash)."""
        email = email.strip().lower()
        
        # Get user
        user = self._user_repo.get_by_email(email)
        if not user:
            raise AuthenticationError("Email ou senha inválidos")

        # Check password
        if not check_password(password, user.get("password_hash", "")):
            raise AuthenticationError("Email ou senha inválidos")

        if not user.get("is_active"):
            raise AuthenticationError("Usuário inativo")

        # Return without password
        user_copy = dict(user)
        user_copy.pop("password_hash", None)
        user_copy["id"] = str(user_copy["id"])
        return user_copy
```

### Service Patterns

#### Pattern 1: CRUD Operations

```python
class CameraService:
    """Use cases para gerenciamento de câmeras."""

    def __init__(
        self,
        camera_repo: CameraRepository,
        rtsp_builder: RTSPBuilder,
        storage: StorageStrategy,
    ) -> None:
        self._camera_repo = camera_repo
        self._rtsp_builder = rtsp_builder
        self._storage = storage

    def create(
        self,
        user_id: UUID,
        name: str,
        manufacturer: str,
        ip: str,
        port: int,
        username: str,
        password: str,
        channel: int | None = None,
    ) -> dict:
        """Cria câmera e gera RTSP URL."""
        # Validate
        if not all([name, manufacturer, ip, port, username]):
            raise ValidationError("Campos obrigatórios faltando")

        # Generate RTSP URL
        rtsp_url = self._rtsp_builder.build(
            manufacturer=manufacturer,
            ip=ip,
            port=port,
            username=username,
            password=password,
            channel=channel,
        )

        # Persist
        camera = self._camera_repo.create(
            user_id=user_id,
            name=name,
            manufacturer=manufacturer,
            ip=ip,
            port=port,
            username=username,
            password=password,  # Encrypted by repository
            rtsp_url=rtsp_url,
            channel=channel,
        )
        return dict(camera)

    def get_by_id(self, user_id: UUID, camera_id: UUID) -> dict:
        """Get camera, check ownership."""
        camera = self._camera_repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundError("Camera", str(camera_id))
        if camera["user_id"] != user_id:
            raise AuthorizationError("Sem acesso a esta câmera")
        return dict(camera)

    def delete(self, user_id: UUID, camera_id: UUID) -> None:
        """Delete camera, check ownership."""
        camera = self.get_by_id(user_id, camera_id)
        # Stop running stream if any
        self._camera_repo.delete(camera_id)
```

#### Pattern 2: Async Task Dispatch

```python
class VideoService:
    """Use cases de vídeo e frames."""

    def __init__(
        self,
        video_repo: VideoRepository,
        storage: StorageStrategy,
        celery_app: Celery,
    ) -> None:
        self._video_repo = video_repo
        self._storage = storage
        self._celery = celery_app

    def upload_video(
        self,
        user_id: UUID,
        dataset_id: UUID,
        filename: str,
    ) -> tuple[str, UUID]:
        """Valida e gera presigned URL. Celery fará extraction depois."""
        # Create video record
        video_id = self._video_repo.create(
            user_id=user_id,
            dataset_id=dataset_id,
            filename=filename,
            status="pending",
        )

        # Generate presigned upload URL
        key = f"raw-videos/{dataset_id}/{video_id}.mp4"
        presigned_url = self._storage.generate_presigned_upload_url(
            key, content_type="video/mp4", ttl=3600
        )

        # Dispatch async extraction task
        # (This will be triggered by webhook after client uploads to R2)
        self._celery.send_task(
            "app.infrastructure.queue.tasks.extraction.extract_frames",
            args=[str(key), str(video_id), str(dataset_id)],
            queue="extraction",
        )

        return presigned_url, video_id
```

#### Pattern 3: Query with Authorization

```python
class DatasetService:
    """Use cases de datasets."""

    def __init__(self, dataset_repo: DatasetRepository) -> None:
        self._dataset_repo = dataset_repo

    def list_by_user(self, user_id: UUID) -> list[dict]:
        """List all datasets owned by user."""
        rows = self._dataset_repo.list_by_user(user_id)
        return [dict(row) for row in rows]

    def get_by_id(self, user_id: UUID, dataset_id: UUID) -> dict:
        """Get dataset, verify ownership."""
        dataset = self._dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise NotFoundError("Dataset", str(dataset_id))
        if dataset["user_id"] != user_id:
            raise AuthorizationError("Sem acesso a este dataset")
        return dict(dataset)
```

---

## Service Design Rules

### Rule 1: Every Method Raises Explicit Exceptions

Never return None or error codes. Raise exceptions:

```python
# WRONG
def get_user(user_id: UUID) -> dict | None:
    user = repo.get(user_id)
    return user  # Could be None

# RIGHT
def get_user(self, user_id: UUID) -> dict:
    user = self._repo.get(user_id)
    if not user:
        raise NotFoundError("User", str(user_id))
    return dict(user)
```

### Rule 2: No Flask/Celery/DB Imports

Domain services are pure Python. They don't know about infrastructure:

```python
# WRONG — imports from Flask/Celery
from flask import request, current_app
from celery import Celery

class VideoService:
    def upload(self):
        file = request.files["file"]  # No!

# RIGHT — receives dependencies as parameters
class VideoService:
    def __init__(self, storage: StorageStrategy, celery_app: Celery):
        self._storage = storage  # DI
        self._celery = celery_app

    def upload(self, file_bytes: bytes, filename: str):
        # Use injected dependencies
        self._storage.upload_bytes(...)
        self._celery.send_task(...)
```

### Rule 3: Validate Inputs Early

```python
def create_camera(self, name: str, ip: str, port: int) -> dict:
    # Validate before any operation
    if not name or not name.strip():
        raise ValidationError("Nome da câmera é obrigatório")
    if not ip or not self._is_valid_ip(ip):
        raise ValidationError(f"IP inválido: {ip}")
    if not (1 <= port <= 65535):
        raise ValidationError(f"Porta inválida: {port}")
    
    # Only then do work
    camera = self._repo.create(name, ip, port)
    return dict(camera)
```

### Rule 4: Authorization at Service Layer

Check user ownership in service, not in route:

```python
# WRONG — auth in route
@bp.route("/cameras/<camera_id>")
@jwt_required
def get_camera(camera_id):
    user_id = get_current_user_id()
    if user_id != camera.user_id:  # WRONG
        raise AuthorizationError()
    return ...

# RIGHT — auth in service
@bp.route("/cameras/<camera_id>")
@jwt_required
def get_camera(camera_id):
    user_id = get_current_user_id()
    service = _get_service()
    camera = service.get_by_id(user_id, camera_id)  # Raises if not owner
    return success(camera)
```

### Rule 5: Return Dicts, Not Models

Convert dataclasses to dicts for JSON serialization:

```python
def get_user(self, user_id: UUID) -> dict:
    user = self._repo.get(user_id)
    if not user:
        raise NotFoundError("User")
    return dict(user)  # ← Convert to dict
```

---

## Common Service Patterns

### Pattern: Multi-step Workflow

```python
def build_dataset_version(
    self,
    user_id: UUID,
    dataset_id: UUID,
) -> dict:
    """
    Multi-step workflow:
    1. Validate dataset exists and user owns it
    2. Collect frames from all videos
    3. Create version record
    4. Dispatch versioning task
    """
    # Step 1: Validate
    dataset = self.get_by_id(user_id, dataset_id)
    if dataset["status"] != "ready":
        raise ValidationError("Dataset não está pronto")

    # Step 2: Collect
    frames = self._frame_repo.list_by_dataset(dataset_id)
    if not frames:
        raise ValidationError("Dataset sem frames")

    # Step 3: Create version
    version = self._version_repo.create(
        dataset_id=dataset_id,
        version="1.0.0",
        frame_count=len(frames),
        status="building",
    )

    # Step 4: Dispatch async task
    self._celery.send_task(
        "app.infrastructure.queue.tasks.versioning.build_version",
        args=[str(dataset_id), version["id"]],
        queue="versioning",
    )

    return dict(version)
```

### Pattern: Collaborating Services

```python
class InferenceService:
    """Detecção em tempo real. Colabora com CameraService e AlertService."""

    def __init__(
        self,
        camera_service: CameraService,
        alert_service: AlertService,
    ) -> None:
        self._camera_service = camera_service
        self._alert_service = alert_service

    def run_inference(self, user_id: UUID, camera_id: UUID) -> None:
        """Start inference loop."""
        # Get camera via collaborator
        camera = self._camera_service.get_by_id(user_id, camera_id)
        
        # Process detections
        for detection in self._detect_loop(camera):
            # Check alerts via collaborator
            alerts = self._alert_service.check_rules(user_id, detection)
            if alerts:
                self._alert_service.trigger(alerts)
```

---

## Testing Services

Services are highly testable because they depend on repositories, not Flask/DB directly:

```python
# conftest.py
import pytest
from unittest.mock import MagicMock
from app.domain.services.auth_service import AuthService

@pytest.fixture
def mock_user_repo():
    return MagicMock()

@pytest.fixture
def auth_service(mock_user_repo):
    return AuthService(mock_user_repo)

# test_auth_service.py
def test_register_success(auth_service, mock_user_repo):
    """Test successful registration."""
    mock_user_repo.exists_by_email.return_value = False
    mock_user_repo.create.return_value = {
        "id": UUID("123e4567-e89b-12d3-a456-426614174000"),
        "email": "test@example.com",
        "name": "Test",
    }

    result = auth_service.register("test@example.com", "password123", "Test")
    
    assert result["email"] == "test@example.com"
    mock_user_repo.create.assert_called_once()

def test_register_duplicate_email(auth_service, mock_user_repo):
    """Test registration with duplicate email."""
    mock_user_repo.exists_by_email.return_value = True

    with pytest.raises(ConflictError):
        auth_service.register("test@example.com", "password123", "Test")
```

---

## Related Documentation

- **Models**: Immutable dataclasses per entity
- **Services**: Use cases, dependency injection, validation
- **API Layer**: `../api/` — routes that call these services
- **Infrastructure**: `../infrastructure/` — repositories injected into services
