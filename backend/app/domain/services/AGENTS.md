# backend/app/domain/services — Business Logic Services

<!-- Parent: ../AGENTS.md -->

## Overview

The `services/` directory contains **use case classes** implementing business logic. Services are independent of Flask, databases, or external systems — all dependencies are injected.

**Key Principle**: Services are pure Python. They validate inputs, orchestrate logic, raise exceptions, and delegate to repositories or collaborators. They never know about HTTP requests or responses.

---

## Directory Structure

```
domain/services/
├── __init__.py                # Empty or imports all services
├── auth_service.py            # register, login, get_user
├── camera_service.py          # camera CRUD, RTSP URL building
├── video_service.py           # video metadata, upload handling
├── frame_service.py           # frame queries
├── annotation_service.py       # annotation CRUD
├── dataset_service.py         # dataset management
├── training_service.py        # training job submission
├── inference_service.py       # YOLOv8 inference pipeline
├── module_service.py          # module enable/disable
├── report_service.py          # report generation
├── alert_service.py           # alert rules, detection
└── rule_service.py            # detection rule management
```

---

## Service Pattern

### Basic Structure

```python
"""
EPI Monitor V2 — MyDomain Service.

Lógica de negócio para my_domain. NÃO conhece Flask.
"""
import logging
from uuid import UUID

from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    AuthorizationError,
    ConflictError,
)
from app.infrastructure.database.repositories.my_repository import MyRepository

logger = logging.getLogger(__name__)


class MyService:
    """Use cases de my_domain."""

    def __init__(self, my_repo: MyRepository) -> None:
        """Initialize with injected repository."""
        self._my_repo = my_repo

    def create(self, user_id: UUID, name: str) -> dict:
        """Create item. Returns dict (for JSON)."""
        # 1. Validate inputs
        if not name or not name.strip():
            raise ValidationError("name é obrigatório")

        # 2. Check conflicts
        if self._my_repo.exists_by_name(name):
            raise ConflictError("name já existe")

        # 3. Create and return
        item = self._my_repo.create(user_id=user_id, name=name)
        return dict(item)  # Convert model to dict

    def get_by_id(self, user_id: UUID, item_id: UUID) -> dict:
        """Get item, verify ownership."""
        item = self._my_repo.get_by_id(item_id)
        if not item:
            raise NotFoundError("Item", str(item_id))

        # Authorization check
        if str(item["user_id"]) != str(user_id):
            raise AuthorizationError("Sem acesso a este item")

        return dict(item)

    def delete(self, user_id: UUID, item_id: UUID) -> None:
        """Delete item, verify ownership."""
        item = self.get_by_id(user_id, item_id)  # Raises if not owner
        self._my_repo.delete(item_id)
```

### Rules

1. **No Flask imports** — never import `request`, `current_app`, etc.
2. **No Celery imports** — never import `@celery.task`, pass celery via DI
3. **No database imports** — never import `psycopg2`, use repositories
4. **Dependency injection** — receive all dependencies in `__init__`
5. **Raise exceptions** — never return None or error codes
6. **Validate early** — check inputs before any operation
7. **Return dicts** — convert models to dicts for JSON serialization
8. **One responsibility** — services focus on one domain

---

## Service Examples

### AuthService (from actual codebase)

```python
"""
EPI Monitor V2 — Auth Service.

Lógica de negócio de autenticação. NÃO conhece Flask.
"""
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
        self._user_repo = user_repo

    def register(
        self, email: str, password: str, name: str
    ) -> dict:
        """Registra novo usuário. Retorna dict (sem hash)."""
        # Normalize input
        email = email.strip().lower()
        name = name.strip()

        # Validate
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

        # Return without hash
        user["id"] = str(user["id"])
        return user

    def login(self, email: str, password: str) -> dict:
        """Autentica usuário. Retorna dict (sem hash)."""
        email = email.strip().lower()
        if not email or not password:
            raise ValidationError("email e password obrigatórios")

        user = self._user_repo.get_by_email(email)
        if not user or not user.get("is_active"):
            raise AuthenticationError("Credenciais inválidas")

        if not check_password(password, user["password_hash"]):
            raise AuthenticationError("Credenciais inválidas")

        # Return without hash
        result = {
            k: str(v) if k == "id" else v
            for k, v in user.items()
            if k != "password_hash"
        }
        return result

    def get_user(self, user_id: UUID) -> dict:
        """Busca usuário por ID."""
        user = self._user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("Usuário", str(user_id))
        user["id"] = str(user["id"])
        return user
```

### CameraService (from actual codebase)

```python
"""
EPI Monitor V2 — Camera Service.

Lógica de negócio para câmeras IP. NÃO conhece Flask.
"""
import logging
from uuid import UUID

from cryptography.fernet import Fernet

from app.core.exceptions import (
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from app.core.validators import RTSPUrlValidator
from app.infrastructure.database.repositories.camera_repository import CameraRepository

logger = logging.getLogger(__name__)


class CameraService:
    """Use cases de câmeras IP."""

    def __init__(
        self,
        camera_repo: CameraRepository,
        fernet_key: str,
    ) -> None:
        self._camera_repo = camera_repo
        self._fernet = Fernet(fernet_key.encode()) if fernet_key else None

    def _encrypt_password(self, password: str) -> str:
        """Criptografa senha com Fernet."""
        if not self._fernet:
            raise ValidationError("CAMERA_SECRET_KEY não configurada")
        return self._fernet.encrypt(password.encode()).decode()

    def _decrypt_password(self, encrypted: str) -> str:
        """Descriptografa senha com Fernet."""
        if not self._fernet or not encrypted:
            return ""
        try:
            return self._fernet.decrypt(encrypted.encode()).decode()
        except Exception:
            return ""

    def create_camera(self, user_id: UUID, data: dict) -> dict:
        """Cria câmera IP. Criptografa senha antes de salvar."""
        if not data.get("name") or not data.get("host"):
            raise ValidationError("name e host são obrigatórios")

        camera_data = {
            "user_id": user_id,
            "name": data["name"],
            "location": data.get("location"),
            "description": data.get("description"),
            "manufacturer": data.get("manufacturer", "generic"),
            "host": data["host"],
            "port": data.get("port", 554),
            "username": data.get("username", "admin"),
            "channel": data.get("channel", 1),
            "subtype": data.get("subtype", 0),
        }

        if data.get("password"):
            camera_data["password_encrypted"] = self._encrypt_password(
                data["password"]
            )

        camera = self._camera_repo.create(camera_data)
        camera["id"] = str(camera["id"])
        return camera

    def list_cameras(self, user_id: UUID, is_admin: bool = False) -> list[dict]:
        """Lista câmeras. Admin vê todas, operator vê as suas."""
        if is_admin:
            cameras = self._camera_repo.get_all()
        else:
            cameras = self._camera_repo.get_by_user(user_id)

        for cam in cameras:
            cam["id"] = str(cam["id"])
        return cameras

    def get_camera(self, camera_id: UUID) -> dict:
        """Busca câmera por ID (sem senha)."""
        camera = self._camera_repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundError("Câmera", str(camera_id))
        camera["id"] = str(camera["id"])
        camera.pop("password_encrypted", None)
        return camera

    def build_rtsp_url(
        self, camera_id: UUID, user_id: UUID, is_admin: bool = False
    ) -> str:
        """Constrói URL RTSP da câmera. Valida permissão."""
        camera = self._camera_repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundError("Câmera", str(camera_id))

        if str(camera["user_id"]) != str(user_id) and not is_admin:
            raise AuthorizationError("Sem permissão para esta câmera")

        if camera.get("rtsp_url_override"):
            url = camera["rtsp_url_override"]
        else:
            from urllib.parse import quote as _quote
            password = self._decrypt_password(camera.get("password_encrypted", ""))
            # URL-encode credentials para evitar command injection
            safe_user = _quote(str(camera.get("username", "")), safe="")
            safe_pass = _quote(password, safe="")
            url = (
                f"rtsp://{safe_user}:{safe_pass}"
                f"@{camera['host']}:{camera['port']}"
                f"/cam/realmonitor?channel={camera['channel']}"
                f"&subtype={camera['subtype']}"
            )

        RTSPUrlValidator.validate(url)
        return url

    def update_camera(
        self, camera_id: UUID, user_id: UUID, data: dict, is_admin: bool = False
    ) -> dict:
        """Atualiza câmera. Valida permissão."""
        camera = self._camera_repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundError("Câmera", str(camera_id))

        if str(camera["user_id"]) != str(user_id) and not is_admin:
            raise AuthorizationError("Sem permissão para esta câmera")

        update_data: dict = {}
        for field in (
            "name", "location", "description", "manufacturer",
            "host", "port", "username", "channel", "subtype",
            "rtsp_url_override", "is_active",
        ):
            if field in data:
                update_data[field] = data[field]

        if data.get("password"):
            update_data["password_encrypted"] = self._encrypt_password(data["password"])

        if not update_data:
            raise ValidationError("Nenhum campo para atualizar")

        updated = self._camera_repo.update(camera_id, update_data)
        if updated:
            updated["id"] = str(updated["id"])
            updated.pop("password_encrypted", None)
        return updated  # type: ignore[return-value]

    def delete_camera(
        self, camera_id: UUID, user_id: UUID, is_admin: bool = False
    ) -> None:
        """Deleta câmera. Valida permissão."""
        camera = self._camera_repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundError("Câmera", str(camera_id))

        if str(camera["user_id"]) != str(user_id) and not is_admin:
            raise AuthorizationError("Sem permissão para esta câmera")

        self._camera_repo.delete(camera_id)
```

---

## Exception Handling

### Raising Exceptions

Services raise domain exceptions, never return error codes:

```python
def get_camera(self, camera_id: UUID, user_id: UUID) -> dict:
    """Get camera or raise exception."""
    camera = self._camera_repo.get_by_id(camera_id)
    
    # WRONG: Return None
    if not camera:
        return None  # WRONG
    
    # RIGHT: Raise exception
    if not camera:
        raise NotFoundError("Câmera", str(camera_id))  # RIGHT
    
    # Check ownership
    if camera["user_id"] != user_id:
        raise AuthorizationError("Sem permissão")
    
    return dict(camera)
```

### Exception Hierarchy

```
EpiMonitorError (base)
├── ValidationError (400) — invalid input
├── AuthenticationError (401) — login failed
├── AuthorizationError (403) — permission denied
├── NotFoundError (404) — resource not found
├── ConflictError (409) — duplicate/conflict
├── DatabaseError (500) — database operation failed
├── StorageError (500) — R2 operation failed
└── InferenceError (500) — YOLO inference failed
```

**Usage**:
```python
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    AuthorizationError,
    ConflictError,
)

# In service methods
if not email:
    raise ValidationError("email obrigatório")
if not camera:
    raise NotFoundError("Câmera", str(camera_id))
if user_id != camera["user_id"]:
    raise AuthorizationError("Sem permissão")
if existing:
    raise ConflictError("Email já cadastrado")
```

---

## Dependency Injection

### Constructor Injection (Required)

```python
class MyService:
    def __init__(
        self,
        my_repo: MyRepository,
        another_service: AnotherService,
        storage: StorageStrategy,
        celery_app: Celery,
    ) -> None:
        """All dependencies injected in constructor."""
        self._my_repo = my_repo
        self._another_service = another_service
        self._storage = storage
        self._celery = celery_app
```

### Factory Pattern (in routes)

```python
# api/v1/my_domain/routes.py

def _get_service() -> MyService:
    """Factory: creates service with all dependencies."""
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    
    return MyService(
        my_repo=MyRepository(pool),
        another_service=AnotherService(...),
        storage=r2_storage,
        celery_app=celery_app,
    )

@my_bp.route("", methods=["GET"])
@jwt_required()
def list_items():
    """List items."""
    user_id = get_current_user_id()
    service = _get_service()
    items = service.list(user_id)
    return success(items)
```

---

## Validation Rules

Services validate all inputs early:

```python
def create_camera(self, user_id: UUID, data: dict) -> dict:
    """Create camera."""
    # Validate required fields
    if not data.get("name"):
        raise ValidationError("name é obrigatório")
    if not data.get("host"):
        raise ValidationError("host é obrigatório")
    
    name = data["name"].strip()
    if not (3 <= len(name) <= 100):
        raise ValidationError("name deve ter 3-100 caracteres")
    
    host = data["host"].strip()
    if not self._is_valid_ip(host):
        raise ValidationError(f"IP inválido: {host}")
    
    port = data.get("port", 554)
    if not (1 <= port <= 65535):
        raise ValidationError(f"Porta inválida: {port}")
    
    # Now proceed with creation
    camera = self._camera_repo.create(user_id, data)
    return dict(camera)
```

---

## Related Documentation

- **Models**: `../models/` — dataclasses returned as dicts
- **Repositories**: `../../infrastructure/database/repositories/` — injected into services
- **Exceptions**: `../../core/exceptions.py` — raised by services
- **API Routes**: `../../api/v1/` — call these services
