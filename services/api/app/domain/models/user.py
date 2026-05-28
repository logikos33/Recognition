"""Domain model: User."""
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
    password_hash: str = ""
