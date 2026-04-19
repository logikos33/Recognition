"""
Módulo de Qualidade — Task de inferência contínua YOLO.

Fila: quality_inference
Responsabilidade: loop de detecção YOLO26m para câmeras com active_module='quality'.
Publica resultados no Redis para o Andon e para o frontend via WebSocket.

REGRAS CRÍTICAS:
- Verificar active_module == 'quality' ANTES de qualquer inferência
- É setup_mode → suprimir inspeções (gravar contagens mas não salvar como NOK)
- CEP: calcular rolling_nok_rate e disparar alerta se processo fora de controle
- Primeiro OK de lote → disparar capture_reference_snapshot
"""
import json
import logging
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

# FPS alvo para inferência de qualidade
INFERENCE_FPS = int(os.environ.get("QUALITY_INFERENCE_FPS", "5"))

# Confiança mínima para registrar inspeção
MIN_CONFIDENCE = float(os.environ.get("QUALITY_MIN_CONFIDENCE", "0.60"))

# Chave Redis que sinaliza se o loop deve continuar
def _active_key(camera_id: str) -> str:
    return f"quality:inference:{camera_id}:active"

# Chave Redis para último production_order visto (detecção de troca de lote)
def _order_key(camera_id: str) -> str:
    return f"quality:inference:{camera_id}:production_order"


def _get_pool():
    from app.infrastructure.database.connection import DatabasePool
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("DatabasePool não inicializado")
    return pool


def _get_redis():
    import redis as _redis
    return _redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
        socket_timeout=5,
    )


def _get_camera_config(camera_id: str, tenant_schema: str) -> dict | None:
    """Busca configuração de câmera de qualidade.

    Retorna: rtsp_url, modelo, is_setup_mode, production_order.
    """
    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute("""
                SELECT c.rtsp_url, c.model_quality_id, c.active_module,
                       qcc.is_setup_mode, qcc.production_order, qcc.product_type
                FROM cameras c
                LEFT JOIN quality_camera_config qcc ON qcc.camera_id = c.id
                WHERE c.id = %s
            """, (camera_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as exc:
        logger.error("quality_inference_get_config_error: camera=%s err=%s", camera_id, exc)
        return None


def _get_model_path(model_id: str, tenant_schema: str) -> str | None:
    """Resolve path do modelo YOLO a partir do model_id."""
    if not model_id:
        return None
    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute("SELECT r2_key FROM training_models WHERE id = %s", (model_id,))
            row = cur.fetchone()
            if row is None:
                return None
            # Download do modelo se necessário
            from app.infrastructure.storage.r2_storage import R2Storage
            storage = R2Storage.get_instance()
            model_dir = Path(f"/tmp/quality_models/{tenant_schema}")
            model_dir.mkdir(parents=True, exist_ok=True)
            model_path = model_dir / f"{model_id}.pt"
            if not model_path.exists():
                data = storage.download_bytes(row["r2_key"])
                model_path.write_bytes(data)
            return str(model_path)
    except Exception as exc:
        logger.error("quality_inference_model_path_error: model=%s err=%s", model_id, exc)
        return None


def _current_shift() -> str:
    """Turno atual: morning/afternoon/night."""
    hour = datetime.now(UTC).hour
    if 6 <= hour < 14:
        return "morning"
    if 14 <= hour < 22:
        return "afternoon"
    return "night"


def _get_rolling_nok_rate(camera_id: str, tenant_schema: str, hours: int = 1) -> float:
    """Calcula taxa de NOK nas últimas N horas."""
    try:
        pool = _get_pool()
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE result = 'nok') AS nok_count,
                    COUNT(*) AS total
                FROM quality_inspections
                WHERE camera_id = %s AND created_at >= %s
            """, (camera_id, cutoff))
            row = cur.fetchone()
            if row and row["total"] > 0:
                return round(row["nok_count"] / row["total"], 4)
            return 0.0
    except Exception as exc:
        logger.error("quality_inference_nok_rate_error: camera=%s err=%s", camera_id, exc)
        return 0.0


def _check_cep_alert(camera_id: str, tenant_schema: str, nok_rate_1h: float, r) -> None:
    """
    Verifica se processo está fora de controle (CEP).
    Publica alerta no Redis se necessário.
    """
    try:
        pool = _get_pool()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute(
                "SELECT control_limit_upper FROM quality_cep_baseline WHERE camera_id = %s",
                (camera_id,)
            )
            row = cur.fetchone()
            if row and nok_rate_1h > row["control_limit_upper"]:
                r.publish(f"quality:cep_alert:{tenant_schema}:{camera_id}", json.dumps({
                    "camera_id": camera_id,
                    "nok_rate_1h": nok_rate_1h,
                    "limit": row["control_limit_upper"],
                }))
                logger.warning("quality_cep_alert: camera=%s rate=%.2f limit=%.2f",
                               camera_id, nok_rate_1h, row["control_limit_upper"])
    except Exception as exc:
        logger.warning("quality_cep_check_error: camera=%s err=%s", camera_id, exc)


def _save_inspection(
    camera_id: str,
    tenant_schema: str,
    result: str,
    defect_class: int,
    confidence: float,
    evidence_r2_key: str | None,
    production_order: str | None,
    product_type: str | None,
    is_first_ok: bool,
    nok_rate_1h: float,
    nok_rate_8h: float,
) -> str | None:
    """INSERT na tabela quality_inspections. Retorna o UUID gerado."""
    try:
        import uuid
        pool = _get_pool()
        inspection_id = str(uuid.uuid4())
        shift = _current_shift()
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute("""
                INSERT INTO quality_inspections (
                    id, camera_id, result, defect_class, confidence,
                    evidence_r2_key, production_order, product_type, shift,
                    is_first_ok_of_order, rolling_nok_rate_1h, rolling_nok_rate_8h,
                    clip_status, feedback_status
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    'pending', 'pending'
                )
            """, (
                inspection_id, camera_id, result, defect_class, confidence,
                evidence_r2_key, production_order, product_type, shift,
                is_first_ok, nok_rate_1h, nok_rate_8h,
            ))
        return inspection_id
    except Exception as exc:
        logger.error("quality_inference_save_inspection_error: camera=%s err=%s", camera_id, exc)
        return None


@celery.task(
    bind=True,
    queue="quality_inference",
    max_retries=10,
    name="app.infrastructure.queue.tasks.quality_inference.quality_inference_loop",
    default_retry_delay=30,
)
def quality_inference_loop(self, camera_id: str, tenant_schema: str):
    """
    Loop de inferência YOLO para câmera de qualidade industrial.

    Fila: quality_inference
    Máx retries: 10 (backoff exponencial)

    Fluxo:
    1. Verificar active_module == 'quality' — parar se não
    2. Carregar modelo YOLO (model_quality_id)
    3. Abrir RTSP stream com OpenCV
    4. Loop: capturar frame → YOLO predict → analisar resultado
       a. Se is_setup_mode → suprimir inspeção (apenas log)
       b. Se NOK → INSERT inspection + dispara generate_quality_clip
       c. Se OK → INSERT inspection; se primeiro OK do lote → dispara capture_reference_snapshot
       d. Publicar Redis quality:inspection:{tenant}:{camera_id} para WebSocket
       e. Publicar Redis quality:andon_live:{camera_id} a cada 5 frames
    5. Monitorar Redis quality:inference:{camera_id}:active — parar se ausente
    6. Verificar CEP a cada 60s
    """
    logger.info("quality_inference_loop_start: camera=%s tenant=%s", camera_id, tenant_schema)

    # 1. Verificar módulo
    cfg = _get_camera_config(camera_id, tenant_schema)
    if cfg is None or cfg.get("active_module") != "quality":
        logger.info("quality_inference_skip: camera=%s not quality module", camera_id)
        return {"status": "skipped", "reason": "not_quality_module"}

    # 2. Carregar modelo
    model_id = cfg.get("model_quality_id")
    model_path = _get_model_path(model_id, tenant_schema) if model_id else None

    rtsp_url = cfg.get("rtsp_url")
    if not rtsp_url:
        logger.error("quality_inference_no_rtsp: camera=%s", camera_id)
        raise self.retry(countdown=60, exc=RuntimeError("RTSP URL ausente"))

    try:
        from app.core.validators import RTSPUrlValidator
        RTSPUrlValidator.validate(rtsp_url)
    except Exception as exc:
        logger.error("quality_inference_invalid_rtsp: camera=%s err=%s", camera_id, exc)
        return {"status": "error", "reason": "invalid_rtsp"}

    r = _get_redis()
    # Registrar atividade
    r.setex(_active_key(camera_id), 120, "1")

    try:
        import cv2
        from ultralytics import YOLO

        model = YOLO(model_path) if model_path else YOLO("yolov8n.pt")

        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            raise RuntimeError(f"Não foi possível abrir RTSP: {rtsp_url[:40]}")

        frame_count = 0
        last_cep_check = time.time()
        frame_interval = 1.0 / INFERENCE_FPS

        last_order = r.get(_order_key(camera_id))
        andon_buffer = []

        while True:
            # Verificar sinal de parada Redis
            if not r.exists(_active_key(camera_id)):
                logger.info("quality_inference_stop: camera=%s", camera_id)
                break

            # Renovar heartbeat
            r.setex(_active_key(camera_id), 120, "1")

            # Re-verificar configuração periodicamente (detecta mudanças de módulo)
            if frame_count % 300 == 0 and frame_count > 0:
                cfg = _get_camera_config(camera_id, tenant_schema)
                if cfg is None or cfg.get("active_module") != "quality":
                    logger.info("quality_inference_module_changed: camera=%s", camera_id)
                    break

            t_start = time.time()

            ret, frame = cap.read()
            if not ret:
                logger.warning("quality_inference_frame_error: camera=%s", camera_id)
                time.sleep(1.0)
                # Tentar reabrir
                cap.release()
                cap = cv2.VideoCapture(rtsp_url)
                continue

            frame_count += 1

            # Inferência YOLO
            results = model.predict(frame, conf=MIN_CONFIDENCE, verbose=False)
            detections = results[0].boxes if results else None

            best_conf = 0.0
            best_class = -1
            if detections is not None and len(detections) > 0:
                for box in detections:
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    if conf > best_conf:
                        best_conf = conf
                        best_class = cls

            if best_class < 0:
                # Nada detectado neste frame
                elapsed = time.time() - t_start
                sleep_time = max(0, frame_interval - elapsed)
                time.sleep(sleep_time)
                continue

            is_nok = best_class != 0  # classe 0 = produto_ok
            result_str = "nok" if is_nok else "ok"

            # Recarregar config para is_setup_mode e production_order atuais
            cfg = _get_camera_config(camera_id, tenant_schema)
            is_setup = cfg.get("is_setup_mode", False) if cfg else False
            production_order = cfg.get("production_order") if cfg else None
            product_type = cfg.get("product_type") if cfg else None

            if is_setup:
                # Modo configuração: suprimir inspeções reais
                logger.debug("quality_inference_setup_mode_suppress: camera=%s", camera_id)
                elapsed = time.time() - t_start
                time.sleep(max(0, frame_interval - elapsed))
                continue

            # Detectar troca de lote (primeiro OK de novo production_order)
            is_first_ok = False
            if result_str == "ok" and production_order and production_order != last_order:
                is_first_ok = True
                last_order = production_order
                r.set(_order_key(camera_id), production_order or "")

            # Calcular rolling NOK rates
            nok_rate_1h = _get_rolling_nok_rate(camera_id, tenant_schema, hours=1)
            nok_rate_8h = _get_rolling_nok_rate(camera_id, tenant_schema, hours=8)

            # Salvar frame de evidência (apenas para NOK)
            evidence_r2_key = None
            if is_nok:
                try:
                    import uuid

                    import cv2 as cv_local
                    ev_id = str(uuid.uuid4())
                    ev_key = f"quality-frames/{tenant_schema}/{camera_id}/evidence/{ev_id}.jpg"
                    _, jpg_buf = cv_local.imencode(
                        ".jpg", frame, [cv_local.IMWRITE_JPEG_QUALITY, 85]
                    )
                    from app.infrastructure.storage.r2_storage import R2Storage
                    R2Storage.get_instance().upload_bytes(
                        ev_key, jpg_buf.tobytes(), content_type="image/jpeg"
                    )
                    evidence_r2_key = ev_key
                except Exception as exc:
                    logger.warning(
                        "quality_inference_evidence_upload_error: camera=%s err=%s",
                        camera_id, exc
                    )

            # Salvar inspeção no banco
            inspection_id = _save_inspection(
                camera_id=camera_id,
                tenant_schema=tenant_schema,
                result=result_str,
                defect_class=best_class,
                confidence=best_conf,
                evidence_r2_key=evidence_r2_key,
                production_order=production_order,
                product_type=product_type,
                is_first_ok=is_first_ok,
                nok_rate_1h=nok_rate_1h,
                nok_rate_8h=nok_rate_8h,
            )

            if inspection_id:
                # Publicar evento para WebSocket
                payload = {
                    "inspection_id": inspection_id,
                    "camera_id": camera_id,
                    "result": result_str,
                    "defect_class": best_class,
                    "confidence": round(best_conf, 3),
                    "nok_rate_1h": nok_rate_1h,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                try:
                    channel = f"quality:inspection:{tenant_schema}:{camera_id}"
                    r.publish(channel, json.dumps(payload))
                except Exception as exc:
                    logger.warning(
                        "quality_inference_publish_error: camera=%s err=%s",
                        camera_id, exc
                    )

                # Disparar geração de clip para NOK
                if is_nok:
                    from app.infrastructure.queue.tasks.quality_clips import generate_quality_clip
                    generate_quality_clip.delay(
                        inspection_id,
                        camera_id,
                        datetime.now(UTC).isoformat(),
                        tenant_schema,
                    )

                # Dispara snapshot de referência no primeiro OK de novo lote
                if is_first_ok and production_order:
                    from app.infrastructure.queue.tasks.quality_clips import (
                        capture_reference_snapshot,
                    )
                    capture_reference_snapshot.delay(camera_id, tenant_schema, production_order)

                # Buffer para Andon (últimos 5 eventos)
                andon_buffer.append(payload)
                if len(andon_buffer) > 5:
                    andon_buffer.pop(0)

                if frame_count % 5 == 0:
                    try:
                        r.publish(f"quality:andon_live:{camera_id}", json.dumps({
                            "camera_id": camera_id,
                            "recent_inspections": andon_buffer,
                            "nok_rate_1h": nok_rate_1h,
                        }))
                    except Exception:
                        pass

            # Verificar CEP a cada 60s
            if time.time() - last_cep_check >= 60:
                _check_cep_alert(camera_id, tenant_schema, nok_rate_1h, r)
                last_cep_check = time.time()

            elapsed = time.time() - t_start
            time.sleep(max(0, frame_interval - elapsed))

        cap.release()

    except ImportError as exc:
        logger.error("quality_inference_import_error: camera=%s err=%s", camera_id, exc)
        raise self.retry(countdown=60, exc=exc) from exc
    except Exception as exc:
        logger.error("quality_inference_error: camera=%s err=%s", camera_id, exc)
        raise self.retry(
            countdown=min(30 * (2 ** self.request.retries), 300),
            exc=exc,
        ) from exc

    logger.info("quality_inference_loop_ended: camera=%s", camera_id)


# === QUALITY GATE — Inspeção sob demanda por peça ===

@celery.task(
    bind=True,
    queue="quality_inference",
    max_retries=3,
    name="app.infrastructure.queue.tasks.quality_inference.run_quality_gate_inspection",
    default_retry_delay=5,
)
def run_quality_gate_inspection(
    self,
    piece_id: str,
    validation_type: str,
    camera_id: str,
    tenant_schema: str,
):
    """Task de inspeção do quality gate — roda sob demanda quando operador dispara.

    Diferente do quality_inference_loop (contínuo), esta task:
    1. Captura múltiplos frames (QUALITY_CAPTURE_FRAMES, default 5)
    2. Executa YOLO em cada frame
    3. Aplica voting: >= QUALITY_VOTING_THRESHOLD frames OK → resultado OK
    4. Publica resultado no Redis → socket_bridge → tablet

    Args:
        piece_id: UUID da peça sendo inspecionada.
        validation_type: "v1", "v2" ou "v3".
        camera_id: UUID da câmera de inspeção.
        tenant_schema: Schema do tenant para isolamento.
    """
    logger.info(
        "gate_inspection_start: piece=%s validation=%s camera=%s",
        piece_id,
        validation_type,
        camera_id,
    )

    capture_frames = int(os.environ.get("QUALITY_CAPTURE_FRAMES", "5"))
    voting_threshold = float(os.environ.get("QUALITY_VOTING_THRESHOLD", "0.6"))

    try:
        # 1. Carrega configuração da câmera e modelo
        config = _get_camera_config(camera_id, tenant_schema)
        if not config:
            logger.error("gate_inspection_camera_not_found: camera=%s", camera_id)
            return {"status": "error", "reason": "camera_not_found"}

        rtsp_url = config.get("rtsp_url")
        if not rtsp_url:
            return {"status": "error", "reason": "no_rtsp_url"}

        # 2. Abre stream RTSP
        import cv2
        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            logger.error("gate_inspection_stream_error: camera=%s", camera_id)
            return {"status": "error", "reason": "stream_unavailable"}

        # 3. Captura N frames — tenta 3x mais para descartar frames ruins
        frames = []
        for _ in range(capture_frames * 3):
            ret, frame = cap.read()
            if ret and frame is not None:
                frames.append(frame)
            if len(frames) >= capture_frames:
                break
        cap.release()

        if not frames:
            return {"status": "error", "reason": "no_frames_captured"}

        # 4. Carrega modelo YOLO
        model_id = str(config.get("model_quality_id") or "")
        model_path = _get_model_path(model_id, tenant_schema) if model_id else None
        try:
            from ultralytics import YOLO
            model = YOLO(model_path or "yolov8n.pt")
        except Exception as exc:
            logger.error("gate_inspection_model_load_error: %s", exc)
            return {"status": "error", "reason": "model_load_failed"}

        # 5. Executa inferência em cada frame
        ok_count = 0
        best_nok_frame = None
        best_nok_confidence = 0.0
        best_nok_detections: list = []

        for frame in frames:
            results = model.predict(frame, conf=MIN_CONFIDENCE, verbose=False)
            is_ok = True
            frame_detections: list = []

            for r in results:
                for box in r.boxes:
                    cls_idx = int(box.cls[0])
                    conf = float(box.conf[0])
                    if cls_idx > 0:  # classe 0 = ok, 1+ = defeito
                        is_ok = False
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        frame_detections.append({
                            "class": r.names[cls_idx],
                            "class_id": cls_idx,
                            "confidence": conf,
                            "bbox": [x1, y1, x2, y2],
                            "is_defect": True,
                        })
                        if conf > best_nok_confidence:
                            best_nok_confidence = conf
                            best_nok_frame = frame
                            best_nok_detections = frame_detections

            if is_ok:
                ok_count += 1

        # 6. Aplica voting: ok_ratio >= threshold → aprovado
        ok_ratio = ok_count / len(frames)
        final_result = "ok" if ok_ratio >= voting_threshold else "nok"

        logger.info(
            "gate_inspection_result: piece=%s validation=%s result=%s ok_ratio=%.2f",
            piece_id,
            validation_type,
            final_result,
            ok_ratio,
        )

        # 7. Salva foto se NOK (frame com maior confiança de defeito)
        nok_photo_path = ""
        nok_photo_r2 = ""
        if final_result == "nok" and best_nok_frame is not None:
            import cv2 as _cv2
            _, frame_bytes_enc = _cv2.imencode(
                ".jpg", best_nok_frame, [_cv2.IMWRITE_JPEG_QUALITY, 85]
            )
            from app.api.v1.quality.photo_service import get_photo_service
            photo_svc = get_photo_service()
            nok_photo_path, nok_photo_r2 = photo_svc.save_analysis_photo(
                frame_bytes_enc.tobytes(), best_nok_detections, camera_id
            )

        # 8. Publica resultado no Redis → WebSocket → tablet
        redis = _get_redis()
        result_data = {
            "piece_id": piece_id,
            "validation_type": validation_type,
            "camera_id": camera_id,
            "result": final_result,
            "confidence": ok_ratio,
            "ok_ratio": ok_ratio,
            "ok_count": ok_count,
            "total_frames": len(frames),
            "detections": best_nok_detections,
            "photo_path": nok_photo_path,
            "photo_r2_key": nok_photo_r2,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        import json as _json
        # Canal específico da peça (tablet ouve este canal)
        redis.publish(
            f"quality:gate_result:{tenant_schema}:{piece_id}",
            _json.dumps(result_data),
        )
        # Canal geral do schema (gate_service ouve para avançar a state machine)
        redis.publish(
            f"quality:inspection_result:{tenant_schema}",
            _json.dumps(result_data),
        )

        return {"status": "completed", "result": final_result, "ok_ratio": ok_ratio}

    except Exception as exc:
        logger.error("gate_inspection_error: piece=%s err=%s", piece_id, exc)
        try:
            self.retry(countdown=5)
        except Exception:
            return {"status": "error", "reason": str(exc)}


@celery.task(
    queue="quality_inference",
    name="app.infrastructure.queue.tasks.quality_inference.retry_failed_wiser_exports",
)
def retry_failed_wiser_exports():
    """Task periódica (Celery Beat): re-tenta exportações Wiser com falha.

    Roda a cada 5 minutos via beat schedule. Busca peças aprovadas com
    wiser_exported=false em todos os schemas de tenant e re-exporta.
    """
    logger.info("wiser_retry_start")
    try:
        pool = _get_pool()
        # Busca todos os schemas de tenant ativos
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT schema_name FROM public.tenants "
                "WHERE schema_name IS NOT NULL AND schema_name != ''"
            )
            schemas = [row["schema_name"] for row in cur.fetchall()]

        for schema in schemas:
            try:
                _retry_wiser_for_schema(schema)
            except Exception as exc:
                logger.warning("wiser_retry_schema_error: schema=%s err=%s", schema, exc)

        logger.info("wiser_retry_done: schemas=%d", len(schemas))
    except Exception as exc:
        logger.error("wiser_retry_error: %s", exc)


def _retry_wiser_for_schema(schema: str) -> None:
    """Re-tenta exportações Wiser pendentes para um schema específico.

    Busca até 20 peças aprovadas com wiser_exported=false e tenta
    exportar cada uma. Atualiza o flag após sucesso.

    Args:
        schema: Schema do tenant a processar.
    """
    pool = _get_pool()
    with pool.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SET search_path TO %s, public", (schema,))
        cur.execute(
            """
            SELECT id, piece_number, work_order, product_type, status,
                   photo_quality_path, total_rework_count, total_rework_time_seconds
            FROM quality_pieces
            WHERE status = 'approved' AND wiser_exported = false
            LIMIT 20
            """
        )
        pieces = [dict(r) for r in cur.fetchall()]

    if not pieces:
        return

    from app.api.v1.quality.wiser_integration import get_wiser_integration
    wiser = get_wiser_integration()

    for piece in pieces:
        result = wiser.export_piece(piece, piece.get("photo_quality_path") or "")
        if result["success"]:
            with pool.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SET search_path TO %s, public", (schema,))
                cur.execute(
                    "UPDATE quality_pieces "
                    "SET wiser_exported=true, wiser_exported_at=NOW(), updated_at=NOW() "
                    "WHERE id=%s",
                    (piece["id"],),
                )
            logger.info(
                "wiser_retry_success: schema=%s piece=%s method=%s",
                schema,
                piece["id"],
                result.get("method"),
            )
