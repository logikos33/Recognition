from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .enums import DeploymentMode, SiteStatus


class EdgeSiteCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str | None = None
    location: str | None = None
    deployment_mode: DeploymentMode
    status: SiteStatus = SiteStatus.provisioning


class EdgeSite(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    location: str | None
    deployment_mode: DeploymentMode
    status: SiteStatus
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
