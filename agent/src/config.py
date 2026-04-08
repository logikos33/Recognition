"""Edge Agent Configuration."""
import os
from dataclasses import dataclass, field
from typing import List, Optional

import yaml


@dataclass
class CameraConfig:
    id: str
    name: str
    rtsp_url: Optional[str] = None
    manufacturer: str = "generic"
    host: Optional[str] = None
    port: int = 554
    username: str = "admin"
    password: str = ""

    def get_rtsp_url(self) -> str:
        if self.rtsp_url:
            return self.rtsp_url
        return f"rtsp://{self.username}:{self.password}@{self.host}:{self.port}/stream1"


@dataclass
class AgentConfig:
    api_url: str = ""
    api_key: str = ""
    agent_id: str = "edge-1"
    inference_mode: str = "edge"
    cameras: List[CameraConfig] = field(default_factory=list)
    yolo_model: str = "yolov8n.pt"
    detection_confidence: float = 0.5
    inference_every_n: int = 5

    @classmethod
    def from_env_and_yaml(cls, config_path: str = "config.yaml") -> "AgentConfig":
        cfg = cls()
        cfg.api_url = os.environ.get("API_URL", "")
        cfg.api_key = os.environ.get("API_KEY", "")
        cfg.agent_id = os.environ.get("WORKER_ID", "edge-1")
        cfg.yolo_model = os.environ.get("YOLO_MODEL", "yolov8n.pt")
        cfg.inference_mode = os.environ.get("INFERENCE_MODE", "edge")

        if os.path.exists(config_path):
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
            api_cfg = data.get("api", {})
            cfg.api_url = cfg.api_url or api_cfg.get("url", "")
            cfg.api_key = cfg.api_key or api_cfg.get("key", "")
            agent_cfg = data.get("agent", {})
            cfg.agent_id = agent_cfg.get("id", cfg.agent_id)
            cfg.inference_mode = agent_cfg.get("inference_mode", cfg.inference_mode)
            cfg.cameras = [
                CameraConfig(**{k: v for k, v in cam.items() if k in CameraConfig.__dataclass_fields__})
                for cam in data.get("cameras", [])
            ]

        return cfg
