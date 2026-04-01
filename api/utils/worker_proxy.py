"""
Proxy da API para o Worker via Redis.
A API NUNCA chama FFmpeg/YOLO diretamente.
"""
import logging
from typing import Optional, Dict, List
from services.shared.events import EventConsumer, is_redis_available

logger = logging.getLogger(__name__)
_consumer: Optional[EventConsumer] = None


def _c() -> Optional[EventConsumer]:
    global _consumer
    if not is_redis_available():
        return None
    if _consumer is None:
        _consumer = EventConsumer()
    return _consumer


def start_stream(camera_id: str, rtsp_url: str, config: Dict = None) -> Dict:
    c = _c()
    if not c:
        return {'success': False, 'error': 'Redis indisponível — sem Worker'}
    worker_id = c.get_best_worker()
    if not worker_id:
        return {'success': False, 'error': 'Nenhum Worker disponível'}
    c.set_camera_worker(str(camera_id), worker_id)
    c.send_command(worker_id, {
        'action': 'start_stream',
        'camera_id': str(camera_id),
        'rtsp_url': rtsp_url,
        'config': config or {}
    })
    return {'success': True, 'worker_id': worker_id}


def stop_stream(camera_id: str) -> Dict:
    c = _c()
    if not c:
        return {'success': False, 'error': 'Redis indisponível'}
    worker_id = c.get_camera_worker(str(camera_id)) or c.get_best_worker()
    if worker_id:
        c.send_command(worker_id, {'action': 'stop_stream', 'camera_id': str(camera_id)})
    return {'success': True}


def get_stream_status(camera_id: str) -> Dict:
    c = _c()
    return c.get_stream_status(str(camera_id)) if c else {'status': 'unknown'}


def get_workers_health() -> List[Dict]:
    c = _c()
    return c.get_all_workers_health() if c else []


def start_detection_listener(on_detection_cb):
    """Thread que escuta detecções e aciona Rules Engine."""
    import threading, json

    def _listen():
        from services.shared.events import EventConsumer
        consumer = EventConsumer()
        pubsub = consumer.subscribe_all()
        logger.info("✅ Escutando detecções do Worker")
        for msg in pubsub.listen():
            if msg['type'] == 'message':
                try:
                    event = json.loads(msg['data'])
                    if event['type'] == 'detection':
                        on_detection_cb(
                            event['camera_id'],
                            event['detections'],
                            event.get('timestamp')
                        )
                except Exception as e:
                    logger.error(f"Detection: {e}")

    threading.Thread(target=_listen, daemon=True, name="detection-listener").start()
    logger.info("✅ Detection listener iniciado")
