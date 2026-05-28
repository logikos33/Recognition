"""EPI Monitor Edge Agent — Main Entry Point."""
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [EDGE:%(process)d] %(levelname)s %(message)s',
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import AgentConfig
from src.cloud_connector import CloudConnector
from src.camera_manager import CameraManager
from src.inference_engine import InferenceEngine


async def main() -> None:
    config = AgentConfig.from_env_and_yaml()

    if not config.api_url or not config.api_key:
        logger.error("API_URL and API_KEY are required")
        sys.exit(1)

    engine = InferenceEngine(config.yolo_model, config.detection_confidence)
    cam_mgr = CameraManager()
    connector = CloudConnector(
        api_url=config.api_url,
        api_key=config.api_key,
        agent_id=config.agent_id,
    )

    loop = asyncio.get_event_loop()

    def on_frame(camera_id: str, frame) -> None:
        detections = engine.infer(frame) if config.inference_mode != "relay" else []
        has_violation = any(d["class"].startswith("no_") for d in detections)
        asyncio.run_coroutine_threadsafe(
            connector.send({
                "type": "detection",
                "camera_id": camera_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "detections": detections,
                "has_violation": has_violation,
            }),
            loop,
        )

    for cam in config.cameras:
        cam_mgr.add_camera(cam.id, cam.get_rtsp_url(), on_frame)

    def shutdown(*_):
        logger.info("Shutting down...")
        cam_mgr.stop_all()
        loop.stop()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    logger.info(
        "Edge Agent %s starting — mode: %s", config.agent_id, config.inference_mode
    )
    await connector.run()


if __name__ == "__main__":
    asyncio.run(main())
