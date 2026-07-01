from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .enums import DeviceTokenScope


class EnrollmentRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enrollment_token: str
    device_id: str
    device_name: str | None = None
    public_key_pem: str


class EnrollmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_token: str
    expires_at: datetime


class DeviceClaims(BaseModel):
    """Claims dentro do JWT RS256 emitido para dispositivos edge."""
    model_config = ConfigDict(from_attributes=True)

    tenant_id: UUID
    site_id: UUID
    device_id: str
    scopes: list[DeviceTokenScope]
    iat: int
    exp: int


class DeviceToken(BaseModel):
    """Registro persistido em public.device_tokens após enrollment."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    site_id: UUID
    device_id: str
    device_name: str | None
    fingerprint: str
    revoked: bool
    revoked_at: datetime | None
    revoked_by: UUID | None
    revocation_reason: str | None
    last_seen_at: datetime | None
    enrolled_at: datetime
