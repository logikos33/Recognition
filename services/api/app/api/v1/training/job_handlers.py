"""
Recognition — Training Job, Model, and Alert handlers.

Handles: create_job, list_jobs, get_job_status, list_models,
         activate_model, get_alerts, acknowledge_alert

Dispatch flow:
  create_job → inserts to training_jobs → fires _dispatch_to_training_service()
               (fire-and-forget thread, does not block response)
  activate_model → updates trained_models → publishes model:reload to Redis
                   (inference-service subscribes and hot-reloads)
"""
import hmac
import json
import logging
import os
import threading

import requests as http_requests
from flask import request

from app.core.auth import get_current_user_id, get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success

from .helpers import get_dataset_service, get_inference_service, get_training_service

logger = logging.getLogger(__name__)

_TRAINING_SERVICE_URL = os.environ.get(
    "TRAINING_SERVICE_INTERNAL_URL",
    "http://training-service.railway.internal:8080",
)
_REDIS_URL = os.environ.get("REDIS_URL", "")


def _build_dataset_url(user_id: str, job_id: str) -> str:
    """Constrói URL do dataset no R2 (convenção: exportado antes do treino)."""
    endpoint = os.environ.get("R2_ENDPOINT", "").rstrip("/")
    bucket = os.environ.get("R2_BUCKET", "epi-monitor")
    return f"{endpoint}/{bucket}/datasets/{user_id}/{job_id}/dataset.zip"


def _issue_callback_token(job_id: str) -> str | None:
    """Gera e persiste callback_token por-job (WS-A4) para o progress-callback.

    Token aleatório revogável (ajuste C-1) — nunca HMAC determinístico.
    Best-effort: falha de DB não bloqueia o dispatch (retorna None).
    """
    import secrets  # noqa: PLC0415

    token = secrets.token_urlsafe(48)
    try:
        _get_training_repo()._execute_mutation_no_return(
            "UPDATE training_jobs SET callback_token = %s WHERE id = %s",
            (token, job_id),
        )
        return token
    except Exception as exc:
        logger.warning("callback_token_issue_failed: job=%s err=%s", job_id, exc)
        return None


def _dispatch_to_training_service(
    job_id: str, user_id: str, dataset_version_id: str | None = None
) -> None:
    """Dispara job para training-service via HTTP. Roda em thread separada.

    AI_NOTE: US-029 — fallback para Celery quando HTTP falha, evitando
    que jobs fiquem presos em status 'pending'.

    dataset_version_id (task B2): repassado só para o fallback Celery — o
    dispatch HTTP usa dataset_url (convenção de export no R2), o Celery
    fallback chama dispatch_training.delay(job_id, dataset_version_id)
    diretamente e precisa do valor real (ver _dispatch_celery_fallback).
    """
    dataset_url = _build_dataset_url(user_id, job_id)
    callback_token = _issue_callback_token(job_id)
    payload: dict = {"job_id": job_id, "dataset_url": dataset_url}
    if callback_token:
        payload["callback_token"] = callback_token
    http_ok = False
    try:
        resp = http_requests.post(
            f"{_TRAINING_SERVICE_URL}/jobs",
            json=payload,
            timeout=5,
        )
        if resp.status_code not in (200, 201):
            logger.warning(
                "training_dispatch_non2xx: job=%s status=%d body=%s",
                job_id, resp.status_code, resp.text[:200],
            )
        else:
            logger.info("training_dispatch_ok: job=%s", job_id)
            http_ok = True
    except Exception as exc:
        logger.warning(
            "training_dispatch_http_failed: job=%s err=%s — tentando Celery fallback",
            job_id, exc,
        )

    if not http_ok:
        _dispatch_celery_fallback(job_id, dataset_version_id)


def _dispatch_celery_fallback(job_id: str, dataset_version_id: str | None = None) -> None:
    """Fallback: enfileira dispatch_training via Celery quando HTTP falhou.

    AI_NOTE: US-029 — garante que job sai de 'pending' mesmo quando
    training-service.railway.internal está indisponível.

    task B2: dataset_version_id vem do job realmente criado (training_jobs.
    dataset_version_id, resolvido em create_job_handler) — NUNCA mais
    job_id como placeholder. job_id e dataset_version_id são PKs de tabelas
    diferentes (training_jobs vs. dataset_versions); usar um no lugar do
    outro nunca correspondia a uma versão real. None (sem versão nenhuma
    ainda pro usuário) é repassado como está — honesto, sem inventar id
    (ADR-0017).
    """
    try:
        from app.infrastructure.queue.tasks.training import dispatch_training
        dispatch_training.delay(
            job_id=job_id,
            dataset_version_id=dataset_version_id,
        )
        logger.info("training_dispatch_celery_fallback: job=%s", job_id)
    except Exception as exc:
        logger.error(
            "training_dispatch_both_failed: job=%s err=%s — job permanece pending",
            job_id, exc,
        )


def _publish_model_reload(model_path: str, framework: str | None = None) -> None:
    """Publica model:reload no Redis para inference-service hot-reload.

    task-082: `framework` (trained_models.framework — "yolox"/"rfdetr")
    viaja junto do peso para o serviço de inferência selecionar o backend
    (RfDetrOnnxDetector vs YoloxOnnxDetector).
    """
    if not _REDIS_URL or not model_path:
        return
    try:
        import redis as _redis
        r = _redis.from_url(_REDIS_URL, socket_timeout=3)
        payload: dict = {"model_path": model_path}
        if framework:
            payload["framework"] = framework
        r.publish("model:reload", json.dumps(payload))
        logger.info(
            "model_reload_published: path=%s framework=%s", model_path, framework
        )
    except Exception as exc:
        logger.warning("model_reload_publish_failed: %s", exc)


def create_job_handler():
    """Cria job de treinamento.
    ---
    tags:
      - training
    summary: Criar job de treinamento YOLOv8
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        schema:
          properties:
            preset: {type: string, enum: [fast, balanced, quality], default: balanced}
            model_size: {type: string, example: yolo26n}
            total_epochs: {type: integer, example: 100}
            dataset_version_id: {type: string, format: uuid, description: 'Opcional — sem ele, usa a dataset_version mais recente do usuário'}
    responses:
      201:
        description: Job criado
    """
    try:
        user_id = get_current_user_id()
        data = request.get_json() or {}
        service = get_training_service()

        # task B2 — fiar dataset_version_id ponta a ponta: o formulário
        # "Novo Treino" do TrainingPage não manda dataset_version_id (só
        # preset/module/model_size/epochs/batch_size/learning_rate). Sem
        # isso o job nascia sem nenhuma linhagem de dataset. Se o caller não
        # informar um explícito, resolve para a versão mais recente do
        # usuário (mesmo padrão de tasks/auto_training.py, que busca a
        # dataset_version pronta mais recente do tenant antes de disparar
        # o treino automático). None (usuário sem nenhuma versão construída
        # ainda) é repassado como está — sem inventar id (ADR-0017).
        dataset_version_id = data.get("dataset_version_id")
        if not dataset_version_id:
            latest_version = get_dataset_service().get_latest(user_id)
            dataset_version_id = latest_version["id"] if latest_version else None

        # tenant do CONTEXTO da requisição (honra contexto assumido de
        # superadmin) — sem isso o job nascia com o tenant de casa e o modelo
        # resultante ficava 404 na registry sob contexto assumido. Resolvido
        # aqui (request context vivo), antes da thread de dispatch.
        job = service.create_job(
            user_id=user_id,
            preset=data.get("preset", "balanced"),
            model_size=data.get("model_size", "yolo26n"),
            total_epochs=data.get("total_epochs", 100),
            dataset_version_id=dataset_version_id,
            tenant_id=get_tenant_id(),
        )
        # Dispara training-service em background — não bloqueia resposta
        threading.Thread(
            target=_dispatch_to_training_service,
            args=(job["id"], str(user_id), job.get("dataset_version_id")),
            daemon=True,
            name=f"dispatch-{job['id'][:8]}",
        ).start()
        return success(job, status=201)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("create_job_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def list_jobs_handler():
    """Lista jobs de treinamento do usuário."""
    try:
        user_id = get_current_user_id()
        jobs = get_training_service().list_jobs(user_id)
        return success(jobs)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_jobs_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def get_job_status_handler(job_id: str):
    """Status de um job de treinamento."""
    try:
        from uuid import UUID

        job = get_training_service().get_job(UUID(job_id))
        return success(job)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_job_status_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def list_models_handler():
    """Lista modelos treinados do usuário."""
    try:
        user_id = get_current_user_id()
        models = get_training_service().list_models(user_id)
        return success(models)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_models_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def activate_model_handler(model_id: str):
    """Ativa modelo para inferência."""
    try:
        from uuid import UUID

        user_id = get_current_user_id()
        model = get_training_service().activate_model(UUID(model_id), user_id)
        # Notifica inference-service para hot-reload (framework do registry
        # viaja junto — task-082)
        _publish_model_reload(model.get("model_path", ""), model.get("framework"))
        return success(model)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("activate_model_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def get_current_job_status_handler():
    """Status do job mais recente em execução (ou último job) do usuário.

    Também informa se GPU cloud está configurada (gpu_enabled).
    Usado pelo polling de 3s na Tab 'Treino ao Vivo'.
    """
    try:
        import os
        from uuid import UUID

        user_id = get_current_user_id()
        job = get_training_service().get_current_running_job(UUID(str(user_id)))

        # VAST_API_KEY é a var usada pelo dispatch (tasks/training.py);
        # VAST_AI_API_KEY aceita por retrocompat (deploys antigos).
        gpu_enabled = bool(
            os.environ.get("ULTRALYTICS_HUB_API_KEY")
            or os.environ.get("VAST_API_KEY")
            or os.environ.get("VAST_AI_API_KEY")
        )

        # Progress from Redis if job is running
        progress_data: dict | None = None
        if job and job.get("status") in ("pending", "running"):
            try:
                import json as _json
                import redis as _redis

                r = _redis.from_url(
                    os.environ.get("REDIS_URL", "redis://localhost:6379"),
                    decode_responses=True,
                    socket_timeout=2,
                )
                raw = r.get(f"training_progress:{job['id']}")
                r.close()
                if raw:
                    progress_data = _json.loads(raw)
            except Exception:
                pass  # Redis indisponível — usa só o DB

        return success({"job": job, "gpu_enabled": gpu_enabled, "live": progress_data})
    except Exception as exc:
        logger.error("get_current_job_status_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def stop_job_handler(job_id: str):
    """Para job de treinamento (marca como stopped).

    WS-A4: além do status, revoga o callback_token (NULL — a GPU remota
    perde acesso ao progress-callback) e destrói a instância Vast.ai se o
    job tem gpu_instance_ref (best-effort, nunca falha o stop).
    """
    try:
        from uuid import UUID

        user_id = get_current_user_id()
        stopped = get_training_service().stop_job(UUID(job_id), UUID(str(user_id)))
        if not stopped:
            return error("Job não encontrado ou já finalizado", 404)
        _teardown_vast_job(stopped)
        # Nunca expor o token (mesmo revogado) na resposta
        stopped.pop("callback_token", None)
        return success(stopped)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("stop_job_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def _teardown_vast_job(job: dict) -> None:
    """Revoga callback_token e destrói instância GPU do job (best-effort)."""
    job_id = str(job.get("id", ""))
    try:
        _get_training_repo()._execute_mutation_no_return(
            "UPDATE training_jobs SET callback_token = NULL WHERE id = %s",
            (job_id,),
        )
        logger.info("callback_token_revoked: job=%s", job_id)
    except Exception as exc:
        logger.warning("callback_token_revoke_failed: job=%s err=%s", job_id, exc)

    instance_ref = job.get("gpu_instance_ref")
    if not instance_ref:
        return
    try:
        from app.infrastructure.gpu.vast_client import (  # noqa: PLC0415
            VastAIClient,
            resolve_vast_api_key,
        )

        api_key = resolve_vast_api_key(get_tenant_id())
        if not api_key:
            logger.warning(
                "vast_stop_sem_api_key: job=%s instance=%s — destrua "
                "manualmente no console Vast.ai", job_id, instance_ref,
            )
            return
        VastAIClient(api_key).destroy_instance(instance_ref)
    except Exception as exc:
        logger.error(
            "vast_destroy_on_stop_failed: job=%s instance=%s err=%s",
            job_id, instance_ref, exc,
        )


# --------------------------------------------------------------------------
# Progress callback (WS-A4) — chamado pela GPU remota (remote_train.py)
# --------------------------------------------------------------------------

_ALLOWED_CALLBACK_STATUS = frozenset({"running", "completed", "failed"})
_CALLBACK_ERROR_MAX_LEN = 500
_PROGRESS_TTL_SECONDS = 86400  # 24h — mesmo TTL do tasks/training.py


def _get_training_repo():
    """TrainingRepository ligado ao pool (padrão _get_repo das routes)."""
    from app.infrastructure.database.connection import DatabasePool  # noqa: PLC0415
    from app.infrastructure.database.repositories.training_repository import (  # noqa: E501,PLC0415
        TrainingRepository,
    )

    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return TrainingRepository(pool)


def _publish_training_progress(job_id: str, payload: dict) -> None:
    """SETEX (polling) + PUBLISH no canal EXISTENTE training_progress:{job_id}.

    Ajuste vinculante #2: NÃO usar training:{job_id} — o bridge registra
    modelo duplicado nesse canal (dual-write Celery × socket_bridge).
    """
    try:
        import redis as _redis  # noqa: PLC0415

        r = _redis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379"),
            decode_responses=True,
            socket_timeout=3,
        )
        serialized = json.dumps(payload)
        r.setex(f"training_progress:{job_id}", _PROGRESS_TTL_SECONDS, serialized)
        r.publish(f"training_progress:{job_id}", serialized)
        r.close()
    except Exception as exc:
        logger.debug("callback_publish_failed: job=%s err=%s", job_id, exc)


def _validate_callback_payload(data: dict) -> tuple[dict | None, str | None]:
    """Valida payload do progress-callback (ajuste #5 da crítica).

    Retorna (payload_normalizado, None) ou (None, mensagem_de_erro).
    """
    progress = data.get("progress")
    if progress is not None:
        if isinstance(progress, bool) or not isinstance(progress, (int, float)):
            return None, "progress deve ser numérico"
        if not 0 <= progress <= 100:
            return None, "progress deve estar entre 0 e 100"
        progress = int(progress)

    epoch = data.get("epoch")
    if epoch is not None and (
        isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0
    ):
        return None, "epoch deve ser inteiro >= 0"

    metrics = data.get("metrics")
    if metrics is not None and not isinstance(metrics, dict):
        return None, "metrics deve ser um objeto"

    error_message = data.get("error_message")
    if error_message is not None:
        if not isinstance(error_message, str):
            return None, "error_message deve ser string"
        if len(error_message) > _CALLBACK_ERROR_MAX_LEN:
            return None, (
                f"error_message excede {_CALLBACK_ERROR_MAX_LEN} caracteres"
            )

    status = data.get("status") or "running"
    if status not in _ALLOWED_CALLBACK_STATUS:
        return None, (
            f"status inválido: {status!r} "
            f"(permitidos: {sorted(_ALLOWED_CALLBACK_STATUS)})"
        )

    return {
        "status": status,
        "progress": progress,
        "epoch": epoch,
        "metrics": metrics,
        "error_message": error_message,
    }, None


def training_progress_callback_handler(job_id: str):
    """Progresso do treinamento remoto (Vast.ai) — SEM JWT.

    Auth: header X-Callback-Token comparado em tempo constante
    (hmac.compare_digest) com training_jobs.callback_token (token por-job,
    gerado no dispatch, revogado no stop/fim). Rate limit 60/min na rota.
    """
    try:
        from uuid import UUID

        token = request.headers.get("X-Callback-Token", "")
        if not token:
            return error("Token de callback ausente", 401)

        repo = _get_training_repo()
        job = repo.get_job_by_id(UUID(job_id))
        stored = str((job or {}).get("callback_token") or "")
        if not job or not stored or not hmac.compare_digest(stored, token):
            logger.warning("callback_token_invalido: job=%s", job_id)
            return error("Token de callback inválido", 403)

        data = request.get_json(silent=True) or {}
        payload, validation_error = _validate_callback_payload(data)
        if payload is None:
            return error(validation_error or "Payload inválido", 400)

        repo.update_job_status(
            UUID(job_id),
            payload["status"],
            progress=payload["progress"],
            current_epoch=payload["epoch"],
            metrics=payload["metrics"],
            error_message=payload["error_message"],
        )
        _publish_training_progress(job_id, {
            "job_id": job_id,
            "stage": payload["status"],
            "progress": payload["progress"],
            "epoch": payload["epoch"],
            "metrics": payload["metrics"] or {},
            "error": payload["error_message"],
        })
        return success({"job_id": job_id, "status": payload["status"]})
    except ValueError:
        return error("job_id inválido", 400)
    except Exception as exc:
        logger.error("progress_callback_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def get_alerts_handler(camera_id: str):
    """Lista alertas de uma câmera."""
    try:
        from uuid import UUID

        limit = request.args.get("limit", 50, type=int)
        offset = request.args.get("offset", 0, type=int)
        alerts = get_inference_service().get_alerts(UUID(camera_id), limit, offset)
        return success(alerts)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_alerts_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
