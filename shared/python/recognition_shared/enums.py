from enum import Enum


class DeploymentMode(str, Enum):
    cloud = "cloud"
    edge = "edge"
    hybrid = "hybrid"


class SiteStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    maintenance = "maintenance"
    provisioning = "provisioning"


class HeartbeatStatus(str, Enum):
    healthy = "healthy"
    degraded = "degraded"
    critical = "critical"
    offline = "offline"


class DeviceTokenScope(str, Enum):
    events_write = "events:write"
    config_read = "config:read"
    models_download = "models:download"
    heartbeat_write = "heartbeat:write"
    streams_report = "streams:report"
