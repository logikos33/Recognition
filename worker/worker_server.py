#!/usr/bin/env python3
"""
EPI Monitor V2 — Worker Service.
FFmpeg + YOLO + streams. Comunica APENAS via Redis.
Escala: 1 instancia Railway por 3-4 cameras (~1.5 GB RAM).
"""
import json
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [WORKER:%(process)d] %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

_db = os.environ.get('DATABASE_URL', '')
if _db.startswith('postgres://'):
    os.environ['DATABASE_URL'] = _db.replace('postgres://', 'postgresql://', 1)

WORKER_ID = os.environ.get('WORKER_ID', 'worker-1')
YOLO_MODEL = os.environ.get('YOLO_MODEL_PATH', 'storage/models/active/model.pt')


class WorkerManager:
    def __init__(self):
        from services.shared.events import EventPublisher, get_redis_client
        self.pub = EventPublisher()
        self.redis = get_redis_client()
        self.active: dict = {}
        self.running = True
        self._load_processors()
        logger.info(f"✅ Worker {WORKER_ID} pronto")

    def _load_processors(self):
        try:
            from api.utils.stream_manager import StreamManager
            self.stream_mgr = StreamManager()
            logger.info("✅ StreamManager carregado")
        except ImportError as e:
            logger.warning(f"StreamManager indisponível: {e}")
            self.stream_mgr = None

        try:
            from api.utils.yolo_processor import YOLOProcessor
            self.yolo = YOLOProcessor(model_path=YOLO_MODEL)
            self.yolo.on_detection = self._on_detection
            logger.info("✅ YOLOProcessor carregado")
        except ImportError as e:
            logger.warning(f"YOLOProcessor indisponível: {e} — modo simulado")
            self.yolo = None

    def _on_detection(self, camera_id, detections, timestamp=None):
        self.pub.publish_detection(camera_id, detections, timestamp or time.time())

    def start_stream(self, camera_id: str, rtsp_url: str, config: dict = None):
        if camera_id in self.active:
            return
        logger.info(f"Iniciando stream: {camera_id}")
        self.pub.set_stream_status(camera_id, 'starting')
        try:
            if self.stream_mgr:
                self.stream_mgr.start_stream(camera_id, rtsp_url)
            if self.yolo:
                self.yolo.start_processing(camera_id, rtsp_url, fps=5)
            else:
                threading.Thread(
                    target=self._simulate,
                    args=(camera_id,), daemon=True
                ).start()
            self.active[camera_id] = {'rtsp_url': rtsp_url, 'started': time.time()}
            self.pub.set_stream_status(camera_id, 'active')
            logger.info(f"✅ Stream {camera_id} ativo")
        except Exception as e:
            logger.error(f"❌ Stream {camera_id}: {e}")
            self.pub.set_stream_status(camera_id, 'error', str(e))

    def stop_stream(self, camera_id: str):
        if camera_id not in self.active:
            return
        try:
            if self.stream_mgr:
                self.stream_mgr.stop_stream(camera_id)
            if self.yolo:
                self.yolo.stop_processing(camera_id)
            del self.active[camera_id]
            self.pub.set_stream_status(camera_id, 'stopped')
            logger.info(f"✅ Stream {camera_id} parado")
        except Exception as e:
            logger.error(f"Stop {camera_id}: {e}")

    def _simulate(self, camera_id: str):
        import random
        while camera_id in self.active and self.running:
            if random.random() > 0.6:
                self._on_detection(camera_id, [{
                    'class_name': random.choice(['produto', 'caminhao', 'placa']),
                    'confidence': round(random.uniform(0.7, 0.99), 2),
                    'bbox': [100, 100, 300, 300]
                }])
            time.sleep(3)

    def handle_command(self, cmd: dict):
        action = cmd.get('action')
        cam = cmd.get('camera_id')
        if action == 'start_stream':
            self.start_stream(cam, cmd.get('rtsp_url', ''), cmd.get('config'))
        elif action == 'stop_stream':
            self.stop_stream(cam)
        elif action == 'ping':
            self._health()
        else:
            logger.warning(f"Comando desconhecido: {action}")

    def _health(self):
        self.pub.update_health(WORKER_ID, len(self.active), list(self.active.keys()))

    def _health_loop(self):
        while self.running:
            self._health()
            time.sleep(20)

    def _make_pubsub(self):
        """Dedicated pubsub connection with no socket_timeout (blocks on listen)."""
        import redis as redis_lib
        url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
        r = redis_lib.from_url(
            url,
            decode_responses=True,
            socket_timeout=None,
            socket_keepalive=True,
            health_check_interval=25,
        )
        ps = r.pubsub()
        ps.subscribe(f'epi:commands:{WORKER_ID}')
        return ps

    def run(self):
        self.redis.sadd('epi:workers', WORKER_ID)
        logger.info(f"✅ Escutando: epi:commands:{WORKER_ID}")

        threading.Thread(target=self._health_loop, daemon=True).start()

        backoff = 2
        while self.running:
            pubsub = None
            try:
                pubsub = self._make_pubsub()
                logger.info("pubsub connected")
                backoff = 2

                for msg in pubsub.listen():
                    if not self.running:
                        return
                    if msg['type'] == 'message':
                        try:
                            self.handle_command(json.loads(msg['data']))
                        except Exception as e:
                            logger.error(f"Comando: {e}")

            except Exception as exc:
                if not self.running:
                    return
                logger.warning(f"pubsub lost: {exc} -- reconnecting in {backoff}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
            finally:
                if pubsub is not None:
                    try:
                        pubsub.close()
                    except Exception:
                        pass

    def shutdown(self):
        self.running = False
        for cam in list(self.active.keys()):
            self.stop_stream(cam)
        self.redis.srem('epi:workers', WORKER_ID)


def main():
    logger.info(f"EPI Monitor V2 Worker -- {WORKER_ID}")

    from services.shared.events import get_redis_client
    try:
        get_redis_client().ping()
        logger.info("Redis OK")
    except Exception as e:
        logger.error(f"Redis unreachable: {e}")
        sys.exit(1)

    mgr = WorkerManager()

    signal.signal(signal.SIGTERM, lambda s, f: (mgr.shutdown(), sys.exit(0)))
    signal.signal(signal.SIGINT,  lambda s, f: (mgr.shutdown(), sys.exit(0)))

    mgr.run()


if __name__ == '__main__':
    main()
