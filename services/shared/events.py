"""
Event bus Redis: Worker → API (detecções) | API → Worker (comandos).

Design:
  Worker detecta produto → publica em epi:detections
  API consome → aplica Rules Engine → cria session_event
  API quer parar stream → publica em epi:commands:{worker_id}
  Worker consome → para FFmpeg e YOLO
"""
import os
import json
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


def get_redis_client():
    import redis
    url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    return redis.from_url(url, decode_responses=True, socket_timeout=5)


def is_redis_available() -> bool:
    try:
        get_redis_client().ping()
        return True
    except Exception:
        return False


class EventPublisher:
    """Worker usa para publicar para a API."""

    def __init__(self):
        self._r = None

    @property
    def r(self):
        if self._r is None:
            self._r = get_redis_client()
        return self._r

    def publish_detection(self, camera_id: str, detections: List[Dict], timestamp: float):
        try:
            self.r.publish('epi:detections', json.dumps({
                'type': 'detection',
                'camera_id': str(camera_id),
                'detections': detections,
                'timestamp': timestamp
            }))
        except Exception as e:
            logger.error(f"Publish detection: {e}")

    def set_stream_status(self, camera_id: str, status: str, error: Optional[str] = None):
        try:
            data = {'status': status, 'camera_id': str(camera_id)}
            if error:
                data['error'] = error
            self.r.setex(f'epi:stream:{camera_id}', 120, json.dumps(data))
            self.r.publish('epi:stream_status', json.dumps({'type': 'stream_status', **data}))
        except Exception as e:
            logger.error(f"Set stream status: {e}")

    def update_health(self, worker_id: str, active_streams: int, stream_ids: List[str]):
        try:
            self.r.sadd('epi:workers', worker_id)
            self.r.setex(f'epi:worker:{worker_id}:alive', 60, '1')
            self.r.setex(f'epi:worker:{worker_id}:health', 90, json.dumps({
                'worker_id': worker_id,
                'active_streams': active_streams,
                'stream_ids': stream_ids
            }))
        except Exception as e:
            logger.error(f"Update health: {e}")


class EventConsumer:
    """API usa para consumir eventos e enviar comandos."""

    def __init__(self):
        self._r = None

    @property
    def r(self):
        if self._r is None:
            self._r = get_redis_client()
        return self._r

    def send_command(self, worker_id: str, command: Dict):
        self.r.publish(f'epi:commands:{worker_id}', json.dumps(command))

    def get_best_worker(self) -> Optional[str]:
        workers = self.r.smembers('epi:workers')
        best, min_streams = None, float('inf')
        for wid in workers:
            if not self.r.get(f'epi:worker:{wid}:alive'):
                continue
            h = self.r.get(f'epi:worker:{wid}:health')
            if h:
                n = json.loads(h).get('active_streams', 0)
                if n < 4 and n < min_streams:
                    min_streams, best = n, wid
        return best or (list(workers)[0] if workers else None)

    def get_stream_status(self, camera_id: str) -> Dict:
        data = self.r.get(f'epi:stream:{camera_id}')
        return json.loads(data) if data else {'status': 'stopped'}

    def get_all_workers_health(self) -> List[Dict]:
        workers = self.r.smembers('epi:workers')
        result = []
        for wid in workers:
            h = self.r.get(f'epi:worker:{wid}:health')
            alive = bool(self.r.get(f'epi:worker:{wid}:alive'))
            if h:
                data = json.loads(h)
                data['is_alive'] = alive
                result.append(data)
        return result

    def subscribe_all(self):
        pubsub = self.r.pubsub()
        pubsub.subscribe('epi:detections', 'epi:stream_status')
        return pubsub

    def set_camera_worker(self, camera_id: str, worker_id: str):
        self.r.setex(f'epi:camera:{camera_id}:worker', 3600, worker_id)

    def get_camera_worker(self, camera_id: str) -> Optional[str]:
        return self.r.get(f'epi:camera:{camera_id}:worker')
