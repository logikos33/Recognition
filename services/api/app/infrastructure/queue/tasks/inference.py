"""
Recognition — Celery Tasks: Inferência ONNX + HLS Streaming.

Tasks:
  - inference_loop: Loop contínuo de inferência por câmera.
  - start_hls_stream: FFmpeg RTSP→HLS transcoding.

Detector backend selecionável via env:
  DETECTOR_BACKEND = yolox_onnx | rfdetr_onnx | ultralytics  (padrão: yolox_onnx)
  DETECTOR_MODEL_PATH = /path/to/model.onnx  (padrão: models/yolox_s.onnx)
  VIOLATION_CLASSES = no_helmet,no_vest,no_gloves  (classes que geram alerta)
  DETECTION_CONFIDENCE_THRESHOLD = 0.5
  MODEL_CACHE_DIR = /tmp/models  (cache local dos ONNX baixados do R2 — WS-A6)

Resolução de modelo efetivo por câmera (WS-A6):
  1. model_deployments ativo da câmera+módulo (registry-level)
  2. cameras.model_{module}_id (override direto na câmera)
  3. trained_models.r2_onnx_key → download p/ MODEL_CACHE_DIR (skip se existe)
  Sem deployment/modelo → fallback env acima (comportamento atual intacto).
  Invalidação de cache via canal Redis camera:model_change:{camera_id}.

Task-055a: caminho de inferência servido NÃO usa ultralytics (AGPL-3.0).
"""
import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from uuid import UUID

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

# ── Configuração do detector ──────────────────────────────────────────────────

_DETECTOR_BACKEND: str = os.environ.get("DETECTOR_BACKEND", "yolox_onnx")
_DETECTOR_MODEL_PATH: str = os.environ.get(
    "DETECTOR_MODEL_PATH",
    os.environ.get("YOLO_MODEL_PATH", "models/yolox_s.onnx"),
)
_DETECTION_CONFIDENCE: float = float(
    os.environ.get("DETECTION_CONFIDENCE_THRESHOLD", "0.5")
)
# Classes que geram alerta de violação.
# Para modelos EPI: "no_helmet,no_vest,no_gloves".
# Para teste com COCO pré-treinado: setar VIOLATION_CLASSES=person.
_VIOLATION_CLASSES: set[str] = {
    c.strip()
    for c in os.environ.get("VIOLATION_CLASSES", "no_helmet,no_vest,no_gloves").split(",")
    if c.strip()
}
_INFERENCE_EVERY_N: int = int(os.environ.get("YOLO_INFERENCE_EVERY_N_FRAMES", "5"))

# ── Auto-captura de frames de treino (WS-B3) ──────────────────────────────────
# Feature flags por tenant (tenants.feature_flags JSONB, mesmo padrão do
# módulo fueling — ver FUELING_MOCK_FLAG em api/v1/fueling/routes.py), com
# fallback env global.
_AUTO_CAPTURE_ENABLED_FLAG = "auto_capture_enabled"
_AUTO_CAPTURE_DAILY_CAP_FLAG = "auto_capture_daily_cap"
_AUTO_CAPTURE_RATE_LIMIT_TTL = 86400  # 24h — janela do teto diário
_AUTO_CAPTURE_DEDUP_TTL_SECONDS = int(os.environ.get("AUTO_CAPTURE_DEDUP_TTL_SECONDS", "30"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_redis_client():
    import redis  # noqa: PLC0415
    return redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379"),
        decode_responses=True,
    )


def _is_stream_active(camera_id: str, r) -> bool:
    return bool(r.exists(f"epi:stream:{camera_id}:active"))


def _has_violation(detections: list[dict]) -> bool:
    """True se qualquer detecção é de uma classe que gera alerta."""
    return any(d["class"] in _VIOLATION_CLASSES for d in detections)


def _camera_tenant_module(pool, camera_id: str) -> tuple[str | None, str | None]:
    """Resolve (tenant_id, module_code) da câmera para alertas tenant-scoped.

    Best-effort: câmera não encontrada ou erro de lookup → (None, None)
    (AlertRepository.create usa defaults do schema — ajuste #8).
    """
    try:
        from app.infrastructure.database.repositories.camera_repository import (  # noqa: PLC0415
            CameraRepository,
        )

        camera = CameraRepository(pool).get_by_id(UUID(camera_id))
        if not camera:
            return None, None
        tenant_id = str(camera["tenant_id"]) if camera.get("tenant_id") else None
        module_code = camera.get("module_code") or "epi"
        return tenant_id, module_code
    except Exception as exc:
        logger.warning("camera_tenant_lookup_failed: camera=%s error=%s", camera_id, exc)
        return None, None


def _auto_capture_daily_cap(pool, tenant_id: str | None) -> int:
    """Teto diário de auto-captura por câmera (feature_flags > env, default 20)."""
    if tenant_id:
        try:
            from app.infrastructure.database.repositories.tenant_settings_repository import (  # noqa: PLC0415,E501
                TenantSettingsRepository,
            )
            flags = TenantSettingsRepository(pool).get_feature_flags(UUID(str(tenant_id)))
            if _AUTO_CAPTURE_DAILY_CAP_FLAG in flags:
                return max(0, int(flags[_AUTO_CAPTURE_DAILY_CAP_FLAG]))
        except Exception as exc:
            logger.warning("auto_capture_cap_read_failed: tenant=%s err=%s", tenant_id, exc)
    return max(0, int(os.environ.get("AUTO_CAPTURE_DAILY_CAP", "20")))


def _auto_capture_enabled(pool, tenant_id: str | None) -> bool:
    """Auto-captura ligada por padrão (custo marginal — reusa frame já
    decodificado pro alerta); feature_flags permite desligar por tenant."""
    if tenant_id:
        try:
            from app.infrastructure.database.repositories.tenant_settings_repository import (  # noqa: PLC0415,E501
                TenantSettingsRepository,
            )
            flags = TenantSettingsRepository(pool).get_feature_flags(UUID(str(tenant_id)))
            if _AUTO_CAPTURE_ENABLED_FLAG in flags:
                return bool(flags[_AUTO_CAPTURE_ENABLED_FLAG])
        except Exception as exc:
            logger.warning("auto_capture_flag_read_failed: tenant=%s err=%s", tenant_id, exc)
    return os.environ.get("AUTO_CAPTURE_ENABLED", "true").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _try_reserve_auto_capture_slot(camera_id: str, cap: int) -> bool:
    """Reserva atômica de 1 slot do teto diário (INCR+EXPIRE — sem race de
    check-then-act, mesmo padrão de core/quality_video_security.py).

    cap<=0 desliga a auto-captura sem tocar Redis.
    """
    if cap <= 0:
        return False
    try:
        r = _get_redis_client()
        key = f"epi:autocapture:{camera_id}:{datetime.utcnow().strftime('%Y%m%d')}"
        count = r.incr(key)
        if count == 1:
            r.expire(key, _AUTO_CAPTURE_RATE_LIMIT_TTL)
        return count <= cap
    except Exception as exc:
        logger.warning("auto_capture_rate_limit_failed: camera=%s err=%s", camera_id, exc)
        return False


def _try_acquire_auto_capture_dedup_lock(camera_id: str) -> bool:
    """Debounce (SET NX EX) por câmera — colapsa N chamadas consecutivas da
    MESMA violação em andamento (amostrada em frames consecutivos pelo
    inference_loop) em no máximo 1 captura por janela de
    _AUTO_CAPTURE_DEDUP_TTL_SECONDS. Roda ANTES do teto diário
    (_try_reserve_auto_capture_slot) pra recapturas do mesmo evento não
    consumirem reserva do teto.

    Fail-closed (mesma convenção de _try_reserve_auto_capture_slot): erro de
    Redis nega a captura — o risco aqui é custo/storage, não disponibilidade
    do stream, então negar é mais seguro que capturar sem coordenação.
    """
    try:
        r = _get_redis_client()
        key = f"epi:autocapture:dedup:{camera_id}"
        return bool(r.set(key, "1", nx=True, ex=_AUTO_CAPTURE_DEDUP_TTL_SECONDS))
    except Exception as exc:
        logger.warning("auto_capture_dedup_lock_failed: camera=%s err=%s", camera_id, exc)
        return False


def _auto_capture_frame(
    camera_id: str,
    tenant_id: str | None,
    module_code: str | None,
    frame_bytes: bytes,
    frame,
    avg_confidence: float,
    pool,
) -> None:
    """Grava o frame de violação como amostra de treino (source=auto, WS-B3).

    Best-effort: qualquer falha aqui NUNCA deve derrubar o salvamento do
    alerta (chamado depois dele, nunca antes) nem propagar exceção.
    """
    from app.constants import FrameSource, R2Prefix  # noqa: PLC0415
    from app.infrastructure.database.repositories.frame_repository import (  # noqa: PLC0415
        FrameRepository,
    )
    from app.infrastructure.storage.local_storage import get_storage  # noqa: PLC0415

    try:
        if not _auto_capture_enabled(pool, tenant_id):
            return
        if not _try_acquire_auto_capture_dedup_lock(camera_id):
            logger.debug("auto_capture_dedup_skip: camera=%s", camera_id)
            return
        cap = _auto_capture_daily_cap(pool, tenant_id)
        if not _try_reserve_auto_capture_slot(camera_id, cap):
            return

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
        r2_key = f"{R2Prefix.TRAINING_IMAGES}/{tenant_id or 'unknown'}/auto/{timestamp}.jpg"
        get_storage(tenant_id).upload_bytes(r2_key, frame_bytes, "image/jpeg")

        height, width = frame.shape[0], frame.shape[1]
        FrameRepository(pool).create(
            video_id=None,
            frame_number=0,
            filename=r2_key,
            source=FrameSource.AUTO,
            r2_key=r2_key,
            camera_id=UUID(camera_id),
            width=width,
            height=height,
            model_confidence=round(avg_confidence, 3),
            captured_at=datetime.utcnow(),
            tenant_id=tenant_id,
            module_code=module_code,
        )
        logger.info("auto_capture_saved: camera=%s r2_key=%s", camera_id, r2_key)
    except Exception as exc:
        logger.error("auto_capture_failed: camera=%s err=%s", camera_id, exc, exc_info=True)


def _save_alert(camera_id: str, detections: list[dict], frame) -> None:
    """Salva alerta: frame no storage + registro no banco (tenant-scoped).

    Único ponto do sistema que grava alerta a partir de uma detecção ao vivo
    e, por isso, único lugar correto pro hook de auto-captura de frame de
    treino (WS-B3) — NUNCA duplicar esse hook em socket_bridge.py::
    _create_alert_and_verify (caminho concorrente que já insere em `alerts`
    direto por SQL cru; duplicar o hook lá duplicaria o frame de treino e a
    reserva do teto diário, já que os dois processos — worker e API — não
    coordenam entre si).
    """
    try:
        import cv2  # noqa: PLC0415

        from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
        from app.infrastructure.database.repositories.alert_repository import (  # noqa: PLC0415
            AlertRepository,
        )
        from app.infrastructure.storage.local_storage import get_storage  # noqa: PLC0415

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
        evidence_key = f"evidence/{camera_id}/{timestamp}.jpg"

        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            logger.error("alert_frame_encode_failed: camera=%s", camera_id)
            return
        frame_bytes = buf.tobytes()

        storage = get_storage()
        storage.upload_bytes(evidence_key, frame_bytes, "image/jpeg")

        avg_confidence = (
            sum(d["confidence"] for d in detections) / len(detections)
            if detections else 0.0
        )

        pool = DatabasePool.get_instance()
        if pool is None:
            logger.warning("alert_db_skip: DatabasePool not initialized")
            return

        tenant_id, module_code = _camera_tenant_module(pool, camera_id)

        AlertRepository(pool).create(
            camera_id=UUID(camera_id),
            violations=detections,
            confidence=round(avg_confidence, 3),
            evidence_key=evidence_key,
            tenant_id=tenant_id,
            module_code=module_code,
        )
        logger.info(
            "alert_saved: camera=%s evidence=%s violations=%d",
            camera_id, evidence_key, len(detections),
        )

        _auto_capture_frame(
            camera_id, tenant_id, module_code, frame_bytes, frame, avg_confidence, pool,
        )
    except Exception as exc:
        logger.error("alert_save_failed: camera=%s error=%s", camera_id, exc, exc_info=True)


# ── Cache do detector (singleton por processo) ────────────────────────────────

_detector_instance = None
_detector_lock = None


def _get_detector():
    """Retorna o detector singleton para este processo (lazy init, thread-safe)."""
    global _detector_instance, _detector_lock  # noqa: PLW0603
    import threading  # noqa: PLC0415

    if _detector_lock is None:
        _detector_lock = threading.Lock()

    with _detector_lock:
        if _detector_instance is None:
            from app.domain.detectors.factory import get_detector  # noqa: PLC0415
            _detector_instance = get_detector(
                backend=_DETECTOR_BACKEND,
                model_path=_DETECTOR_MODEL_PATH,
                confidence=_DETECTION_CONFIDENCE,
            )
            logger.info(
                "detector_initialized: backend=%s model=%s ready=%s",
                _DETECTOR_BACKEND, _DETECTOR_MODEL_PATH,
                _detector_instance.is_ready,
            )
    return _detector_instance


# ── Modelo efetivo por câmera (WS-A6) ─────────────────────────────────────────

_MODEL_CACHE_DIR: str = os.environ.get("MODEL_CACHE_DIR", "/tmp/models")

# Cache por processo: camera_id → {"model_id": str, "detector": Detector}.
# Invalidado via canal Redis camera:model_change:{camera_id} (publicado por
# cameras/model_handlers._notify_model_assignment e pelo model-config WS-C2).
_camera_detector_lock = threading.Lock()
_camera_detectors: dict[str, dict] = {}


def _fetch_trained_model(pool, model_id: str, tenant_id: str) -> dict | None:
    """Busca campos do registry (framework, r2_onnx_key) validando o tenant.

    Posse validada via JOIN com users — cobre linhas legadas com tenant_id
    NULL (mesmo padrão de TrainingRepository.get_model_for_tenant).

    NOTA: query local temporária — mover para TrainingRepository quando o
    cluster WS-A5 consolidar o acesso ao registry (pendência registrada).
    """
    from app.infrastructure.database.repositories.training_repository import (  # noqa: PLC0415
        TrainingRepository,
    )

    return TrainingRepository(pool)._execute_one(  # noqa: SLF001
        """
        SELECT tm.id, tm.framework, tm.r2_onnx_key, tm.model_path
        FROM trained_models tm
        JOIN users u ON u.id = tm.user_id
        WHERE tm.id = %s AND u.tenant_id = %s
        """,
        (str(model_id), str(tenant_id)),
    )


def _resolve_camera_model(camera_id: str) -> dict | None:
    """Resolve o modelo efetivo da câmera (cascata WS-A6).

    1. model_deployments ativo da câmera+módulo (registry-level)
    2. cameras.model_{module}_id (override direto na câmera)
    → trained_models (framework + r2_onnx_key)

    Retorna {"model_id", "framework", "r2_onnx_key"} ou None — None faz o
    caller usar o fallback env (DETECTOR_BACKEND/DETECTOR_MODEL_PATH),
    preservando o comportamento atual quando não há deployment.
    """
    from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
    from app.infrastructure.database.repositories.camera_repository import (  # noqa: PLC0415
        CameraRepository,
    )
    from app.infrastructure.database.repositories.model_deployment_repository import (  # noqa: PLC0415
        ModelDeploymentRepository,
    )

    pool = DatabasePool.get_instance()
    if pool is None:
        return None

    camera = CameraRepository(pool).get_by_id(UUID(camera_id))
    if not camera or not camera.get("tenant_id"):
        return None

    tenant_id = str(camera["tenant_id"])
    module_code = str(
        camera.get("active_module") or camera.get("module_code") or "epi"
    ).strip()

    model_id: str | None = None
    deployment = ModelDeploymentRepository(pool).get_active_for_camera(
        tenant_id, UUID(camera_id), module_code
    )
    if deployment and deployment.get("model_id"):
        model_id = str(deployment["model_id"])
    else:
        column = CameraRepository.MODEL_COLUMNS.get(module_code)
        if column and camera.get(column):
            model_id = str(camera[column])

    if model_id is None:
        return None

    model = _fetch_trained_model(pool, model_id, tenant_id)
    if not model:
        logger.warning(
            "camera_model_not_found: camera=%s model=%s tenant=%s — fallback env",
            camera_id, model_id, tenant_id,
        )
        return None
    if not model.get("r2_onnx_key"):
        logger.warning(
            "camera_model_no_onnx: camera=%s model=%s — fallback env",
            camera_id, model_id,
        )
        return None

    return {
        "model_id": model_id,
        "framework": model.get("framework"),
        "r2_onnx_key": model["r2_onnx_key"],
    }


def _ensure_local_model(model_id: str, r2_key: str) -> str:
    """Garante cópia local do ONNX em {MODEL_CACHE_DIR}/{model_id}.onnx.

    Skip se já existe (cache warm entre tasks do mesmo worker). Escrita
    atômica (tmp + os.replace) — evita leitura de download parcial por
    processos concorrentes do worker.
    """
    local_path = os.path.join(_MODEL_CACHE_DIR, f"{model_id}.onnx")
    if os.path.exists(local_path):
        return local_path

    from app.infrastructure.storage.local_storage import get_storage  # noqa: PLC0415

    os.makedirs(_MODEL_CACHE_DIR, exist_ok=True)
    data = get_storage().download_bytes(r2_key)
    tmp_path = f"{local_path}.{os.getpid()}.tmp"
    with open(tmp_path, "wb") as fh:
        fh.write(data)
    os.replace(tmp_path, local_path)
    logger.info(
        "model_downloaded: model=%s key=%s bytes=%d", model_id, r2_key, len(data)
    )
    return local_path


def _invalidate_camera_detector(camera_id: str) -> None:
    """Remove o detector cacheado da câmera (evento camera:model_change)."""
    with _camera_detector_lock:
        removed = _camera_detectors.pop(camera_id, None)
    if removed is not None:
        logger.info(
            "camera_detector_invalidated: camera=%s model=%s",
            camera_id, removed.get("model_id"),
        )


def _get_detector_for_camera(camera_id: str):
    """Detector efetivo da câmera (WS-A6), com cache keyed por model_id.

    Qualquer falha na cascata (sem pool, sem modelo, R2 indisponível, init
    do backend) → fallback ao singleton env (_get_detector) — zero regressão
    sobre o comportamento atual quando não há deployment.
    """
    try:
        resolved = _resolve_camera_model(camera_id)
    except Exception as exc:
        logger.warning(
            "camera_model_resolution_failed: camera=%s error=%s — fallback env",
            camera_id, exc,
        )
        resolved = None

    if resolved is None:
        return _get_detector()

    model_id = resolved["model_id"]
    with _camera_detector_lock:
        cached = _camera_detectors.get(camera_id)
        if cached is not None and cached["model_id"] == model_id:
            return cached["detector"]

        try:
            local_path = _ensure_local_model(model_id, resolved["r2_onnx_key"])
            from app.domain.detectors.factory import get_detector  # noqa: PLC0415

            detector = get_detector(
                backend=resolved.get("framework") or _DETECTOR_BACKEND,
                model_path=local_path,
                confidence=_DETECTION_CONFIDENCE,
            )
        except Exception as exc:
            logger.error(
                "camera_detector_init_failed: camera=%s model=%s error=%s — "
                "fallback env",
                camera_id, model_id, exc, exc_info=True,
            )
            return _get_detector()

        _camera_detectors[camera_id] = {"model_id": model_id, "detector": detector}
        logger.info(
            "camera_detector_ready: camera=%s model=%s backend=%s ready=%s",
            camera_id, model_id,
            resolved.get("framework") or _DETECTOR_BACKEND, detector.is_ready,
        )
        return detector


def _subscribe_model_change(redis_client, camera_id: str):
    """Assina camera:model_change:{camera_id}. Best-effort — None se falhar."""
    try:
        pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(f"camera:model_change:{camera_id}")
        return pubsub
    except Exception as exc:
        logger.warning(
            "model_change_subscribe_failed: camera=%s error=%s", camera_id, exc
        )
        return None


def _drain_model_change(pubsub) -> bool:
    """Drena mensagens pendentes do canal camera:model_change (non-blocking).

    Retorna True se houve pelo menos uma mudança de modelo publicada.
    """
    if pubsub is None:
        return False
    changed = False
    try:
        while True:
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0)
            if message is None:
                break
            if message.get("type") == "message":
                changed = True
    except Exception as exc:
        logger.warning("model_change_poll_failed: error=%s", exc)
    return changed


# ── Tasks ─────────────────────────────────────────────────────────────────────

@celery.task(
    bind=True,
    queue="inference",
    max_retries=5,
    name="tasks.inference.inference_loop",
)
def inference_loop(
    self,
    camera_id: str,
    rtsp_url: str,
    model_path: str | None = None,
) -> dict:
    """
    Loop de inferência ONNX por câmera.

    1. Resolve o detector efetivo da câmera (WS-A6: deployment ativo →
       cameras.model_{module}_id → ONNX do registry no R2), com fallback
       ao singleton env (DETECTOR_BACKEND/DETECTOR_MODEL_PATH).
    2. Conecta stream RTSP via OpenCV.
    3. A cada N frames: roda inferência (recarrega o detector se houver
       evento no canal Redis camera:model_change:{camera_id}).
    4. Publica detecções no Redis (canal det:{camera_id}).
    5. Salva alertas no banco + storage em caso de violação.
    6. Para quando a chave epi:stream:{camera_id}:active sumir do Redis.

    model_path (obsoleto): ignorado — use DETECTOR_MODEL_PATH env.
    """
    import cv2  # noqa: PLC0415
    from app.core.segments_redis import get_segments_redis  # noqa: PLC0415

    redis_client = _get_redis_client()
    # epi:stream:*:active é segmento — client dedicado (SEGMENTS_REDIS_URL
    # isola do Redis de segurança); redis_client segue para pubsub/publish
    # (camera:model_change:*, det:*), que não são chaves de segmento.
    segments_client = get_segments_redis()
    detector = _get_detector_for_camera(camera_id)
    model_change = _subscribe_model_change(redis_client, camera_id)

    logger.info(
        "inference_start: camera=%s backend=%s every_n=%d",
        camera_id, _DETECTOR_BACKEND, _INFERENCE_EVERY_N,
    )

    cap = cv2.VideoCapture(rtsp_url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    frame_count = 0
    frames_processed = 0

    try:
        while _is_stream_active(camera_id, segments_client):
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            frame_count += 1
            if frame_count % _INFERENCE_EVERY_N != 0:
                continue

            frames_processed += 1

            # Recarrega o detector se o modelo da câmera mudou (WS-A6).
            if _drain_model_change(model_change):
                _invalidate_camera_detector(camera_id)
                detector = _get_detector_for_camera(camera_id)

            detections: list[dict] = []
            has_violation = False

            if detector.is_ready:
                detections = detector.predict(frame)
                has_violation = _has_violation(detections)

            payload = {
                "camera_id": camera_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "detections": detections,
                "has_violation": has_violation,
            }
            redis_client.publish(f"det:{camera_id}", json.dumps(payload))

            if has_violation:
                _save_alert(camera_id, detections, frame)

        logger.info(
            "inference_stopped: camera=%s frames_processed=%d",
            camera_id, frames_processed,
        )
        return {
            "camera_id": camera_id,
            "frames_processed": frames_processed,
            "status": "completed",
        }

    except Exception as exc:
        logger.error("inference_failed: camera=%s error=%s", camera_id, exc, exc_info=True)
        raise self.retry(exc=exc, countdown=30)

    finally:
        cap.release()
        if model_change is not None:
            try:
                model_change.close()
            except Exception as exc:
                logger.warning(
                    "model_change_close_failed: camera=%s error=%s", camera_id, exc
                )


@celery.task(
    bind=True,
    queue="inference",
    name="tasks.inference.start_hls_stream",
)
def start_hls_stream(self, camera_id: str, rtsp_url: str) -> dict:
    """
    Inicia FFmpeg convertendo RTSP → HLS.
    Salva em /tmp/hls/{camera_id}/stream.m3u8
    """
    try:
        hls_dir = f"/tmp/hls/{camera_id}"
        os.makedirs(hls_dir, exist_ok=True)

        hls_segment_time = int(os.environ.get("HLS_SEGMENT_TIME", "2"))
        hls_list_size = int(os.environ.get("HLS_LIST_SIZE", "3"))

        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-f", "hls",
            "-hls_time", str(hls_segment_time),
            "-hls_list_size", str(hls_list_size),
            "-hls_flags", "delete_segments",
            f"{hls_dir}/stream.m3u8",
        ]

        logger.info("hls_stream_start: camera=%s", camera_id)
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        return {
            "camera_id": camera_id,
            "pid": process.pid,
            "hls_path": f"{hls_dir}/stream.m3u8",
            "status": "started",
        }

    except Exception as exc:
        logger.error("hls_stream_failed: camera=%s error=%s", camera_id, exc, exc_info=True)
        raise self.retry(exc=exc, countdown=15)
