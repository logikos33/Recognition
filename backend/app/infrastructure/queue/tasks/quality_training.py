"""
Módulo de Qualidade — Task de treinamento YOLO.

Fila: quality_training
Responsabilidade: pipeline completo de treinamento a partir de frames anotados.

Etapas:
1. Coletar frames anotados (quality_annotation_frames com status='annotated')
2. Montar dataset YOLO (images/ + labels/)
3. Upload para Ultralytics Hub (ou treinar localmente com fallback)
4. Registrar job e modelo treinado
5. Publicar progresso via Redis quality:training_progress:{job_id}
"""
import json
import logging
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)


def _get_pool():
    from app.infrastructure.database.connection import DatabasePool
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("DatabasePool não inicializado")
    return pool


def _get_storage():
    from app.infrastructure.storage.r2_storage import R2Storage
    return R2Storage.get_instance()


def _get_redis():
    import redis as _redis
    return _redis.from_url(
        os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
        socket_timeout=5,
    )


def _publish_progress(job_id: str, step: str, progress: int, message: str, r) -> None:
    """Publica progresso do job de treinamento no Redis. Best-effort."""
    try:
        r.publish(f"quality:training_progress:{job_id}", json.dumps({
            "job_id": job_id,
            "step": step,
            "progress": progress,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),
        }))
    except Exception as exc:
        logger.warning("quality_training_publish_error: job=%s err=%s", job_id, exc)


def _update_job_status(job_id: str, tenant_schema: str, status: str, **kwargs) -> None:
    """Atualiza status do job na tabela quality_training_jobs."""
    try:
        pool = _get_pool()
        set_clauses = ["status = %s"]
        values = [status]
        for key, val in kwargs.items():
            set_clauses.append(f"{key} = %s")
            values.append(val)
        values.append(job_id)
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute(
                f"UPDATE quality_training_jobs SET {', '.join(set_clauses)} WHERE id = %s",
                values,
            )
    except Exception as exc:
        logger.error("quality_training_update_job_error: job=%s err=%s", job_id, exc)


@celery.task(
    bind=True,
    queue="quality_training",
    max_retries=3,
    name="app.infrastructure.queue.tasks.quality_training.run_quality_training_pipeline",
    default_retry_delay=60,
)
def run_quality_training_pipeline(self, job_id: str, tenant_schema: str):
    """
    Pipeline de treinamento YOLO para qualidade industrial.

    Fila: quality_training
    Máx retries: 3

    Fluxo:
    1. Buscar job e seus inspection_ids fonte
    2. Coletar frames anotados (status='annotated') das inspeções
    3. Montar estrutura de dataset YOLO (images/ + labels/)
    4. Treinar localmente com Ultralytics YOLO
    5. Upload do modelo treinado para R2
    6. INSERT em training_models
    7. UPDATE quality_training_jobs: status='completed', model_id=...
    8. Publicar Redis: quality:training_progress:{job_id} (100%)
    """
    logger.info("quality_training_start: job=%s tenant=%s", job_id, tenant_schema)
    r = _get_redis()

    # 1. Buscar job
    pool = _get_pool()
    with pool.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SET search_path TO %s, public", (tenant_schema,))
        cur.execute("SELECT * FROM quality_training_jobs WHERE id = %s", (job_id,))
        job = cur.fetchone()

    if job is None:
        logger.error("quality_training_no_job: %s", job_id)
        return {"status": "error", "reason": "job_not_found"}

    _update_job_status(job_id, tenant_schema, "running", started_at=datetime.now(UTC))
    _publish_progress(job_id, "collect", 5, "Coletando frames anotados...", r)

    tmp_dir = Path(f"/tmp/quality_training/{job_id}")
    images_dir = tmp_dir / "dataset" / "images" / "train"
    labels_dir = tmp_dir / "dataset" / "labels" / "train"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    try:
        storage = _get_storage()

        # 2. Coletar frames anotados
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute("""
                SELECT qaf.id, qaf.r2_key, qaf.annotations, qaf.inspection_id
                FROM quality_annotation_frames qaf
                JOIN quality_inspections qi ON qi.id = qaf.inspection_id
                WHERE qaf.status = 'annotated'
                  AND qaf.annotations IS NOT NULL
                  AND json_array_length(qaf.annotations::json) > 0
                ORDER BY qaf.created_at DESC
                LIMIT 2000
            """)
            frames = cur.fetchall()

        if not frames:
            _update_job_status(
                job_id, tenant_schema, "failed",
                error_message="Nenhum frame anotado disponível"
            )
            return {"status": "error", "reason": "no_annotated_frames"}

        _publish_progress(job_id, "download", 10, f"Baixando {len(frames)} frames...", r)

        # 3. Montar dataset YOLO
        valid_count = 0
        for i, frame in enumerate(frames):
            try:
                img_data = storage.download_bytes(frame["r2_key"])
                img_path = images_dir / f"{i:06d}.jpg"
                img_path.write_bytes(img_data)

                # Converter anotações para formato YOLO (class cx cy w h)
                annotations = frame["annotations"]
                if isinstance(annotations, str):
                    annotations = json.loads(annotations)

                label_lines = []
                for ann in annotations:
                    cls = int(ann.get("class_id", 0))
                    cx = float(ann.get("cx", 0.5))
                    cy = float(ann.get("cy", 0.5))
                    w = float(ann.get("w", 0.1))
                    h = float(ann.get("h", 0.1))
                    label_lines.append(f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

                label_path = labels_dir / f"{i:06d}.txt"
                label_path.write_text("\n".join(label_lines))
                valid_count += 1

            except Exception as exc:
                logger.warning("quality_training_frame_error: frame=%s err=%s", frame["id"], exc)

            if i % 50 == 0:
                progress = 10 + int((i / len(frames)) * 30)
                _publish_progress(job_id, "download", progress, f"Frame {i}/{len(frames)}...", r)

        if valid_count < 10:
            _update_job_status(
                job_id, tenant_schema, "failed",
                error_message=f"Frames válidos insuficientes: {valid_count} (mínimo 10)"
            )
            return {"status": "error", "reason": "insufficient_frames"}

        # Criar data.yaml para YOLO
        from app.api.v1.quality.classes import QUALITY_CLASSES
        class_names = [c["name"] for c in QUALITY_CLASSES]
        data_yaml = tmp_dir / "dataset" / "data.yaml"
        data_yaml.write_text(
            f"path: {tmp_dir}/dataset\n"
            f"train: images/train\n"
            f"val: images/train\n"
            f"nc: {len(class_names)}\n"
            f"names: {class_names}\n"
        )

        _publish_progress(
            job_id, "train", 45, f"Iniciando treinamento ({valid_count} frames)...", r
        )

        # 4. Treinar com Ultralytics YOLO
        try:
            from ultralytics import YOLO
            model = YOLO("yolov8n.pt")
            epochs = int(os.environ.get("QUALITY_TRAIN_EPOCHS", "50"))
            model.train(
                data=str(data_yaml),
                epochs=epochs,
                imgsz=640,
                batch=16,
                project=str(tmp_dir / "runs"),
                name="quality_train",
                verbose=False,
            )
            best_model_path = Path(str(tmp_dir / "runs" / "quality_train" / "weights" / "best.pt"))
        except ImportError:
            logger.error("quality_training_ultralytics_missing: job=%s", job_id)
            _update_job_status(
                job_id, tenant_schema, "failed",
                error_message="ultralytics não instalado no worker"
            )
            return {"status": "error", "reason": "ultralytics_not_installed"}

        _publish_progress(job_id, "upload", 85, "Treinamento concluído. Enviando modelo...", r)

        # 5. Upload do modelo
        if not best_model_path.exists():
            _update_job_status(
                job_id, tenant_schema, "failed",
                error_message="Modelo não encontrado após treinamento"
            )
            return {"status": "error", "reason": "model_not_found"}

        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        model_r2_key = f"quality-models/{tenant_schema}/{job_id}/{ts}_best.pt"
        model_data = best_model_path.read_bytes()
        storage.upload_bytes(model_r2_key, model_data, content_type="application/octet-stream")

        # 6. INSERT em training_models (tabela geral do sistema)
        import uuid
        model_id = str(uuid.uuid4())
        with pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (tenant_schema,))
            cur.execute("""
                INSERT INTO training_models (id, name, r2_key, module_code, created_at)
                VALUES (%s, %s, %s, 'quality', NOW())
                ON CONFLICT DO NOTHING
            """, (model_id, f"Quality Model {ts}", model_r2_key))

        # 7. UPDATE job
        _update_job_status(
            job_id, tenant_schema, "completed",
            model_id=model_id,
            completed_at=datetime.now(UTC),
        )

        # 8. Progresso final
        _publish_progress(job_id, "completed", 100, "Modelo treinado e disponível!", r)

        logger.info("quality_training_done: job=%s model=%s", job_id, model_id)
        return {"status": "completed", "model_id": model_id, "r2_key": model_r2_key}

    except Exception as exc:
        logger.error("quality_training_error: job=%s err=%s", job_id, exc)
        _update_job_status(job_id, tenant_schema, "failed", error_message=str(exc)[:500])
        _publish_progress(job_id, "error", 0, f"Erro: {exc}", r)
        raise self.retry(countdown=60, exc=exc) from exc

    finally:
        try:
            shutil.rmtree(str(tmp_dir), ignore_errors=True)
        except Exception:
            pass
