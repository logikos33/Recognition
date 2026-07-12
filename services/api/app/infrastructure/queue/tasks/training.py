"""
Recognition — Training Dispatch Task.

Cadeia de dispatch (dispatch_training):
  1. Vast.ai REST real (VAST_API_KEY resolvível — integration store do
     tenant > env, ver resolve_vast_api_key em infrastructure/gpu/vast_client.py)
  2. Ultralytics Hub (ULTRALYTICS_HUB_API_KEY configurado)
  3. Simulação (fallback funcional sem GPU, ~20s)

Ver app/domain/services/integration_service.py → resolve_r2_credentials/
test_vast_connection para a precedência de credenciais R2/Vast.ai.
"""
import contextlib
import json
import logging
import math
import os
import secrets
import time
import urllib.error
import urllib.request
import zipfile
from io import BytesIO
from typing import Any
from uuid import uuid4

import redis as _redis

from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.annotation_repository import (
    AnnotationRepository,
)
from app.infrastructure.database.repositories.training_repository import (
    TrainingRepository,
)
from app.infrastructure.gpu.vast_client import (
    VastAIClient,
    VastAIError,
    resolve_vast_api_key,
)
from app.infrastructure.queue.celery_app import celery
from app.infrastructure.storage.local_storage import get_storage

logger = logging.getLogger(__name__)


class _JobStoppedError(RuntimeError):
    """Job foi parado explicitamente (stop_job_handler) durante o dispatch.

    Achado da revisão adversarial: sem essa distinção, um stop que chega
    entre o início do dispatch e a criação da instância Vast.ai (ou entre a
    criação e o próximo poll do watchdog) era tratado como falha genérica
    → update_job("failed", ...) sobrescrevia 'stopped' e o Celery reagendava
    dispatch_training (max_retries=1), provisionando uma SEGUNDA instância
    GPU paga para um job que o usuário já tinha cancelado. dispatch_training
    captura este tipo especificamente e NUNCA chama self.retry() para ele.
    """

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
_PROGRESS_TTL = 86400  # 24h


def _publish_progress(job_id: str, payload: dict[str, Any]) -> None:
    """Publica progresso no Redis (SET para polling + PUBLISH para WebSocket bridge)."""
    try:
        r = _redis.from_url(_REDIS_URL, decode_responses=True)
        serialized = json.dumps(payload)
        r.setex(f"training_progress:{job_id}", _PROGRESS_TTL, serialized)
        r.publish(f"training_progress:{job_id}", serialized)
        r.close()
    except Exception as exc:
        logger.debug("publish_progress_failed: job=%s err=%s", job_id, exc)


@celery.task(
    bind=True, max_retries=1, queue="training",
    name="tasks.training.dispatch_training",
)
def dispatch_training(
    self,
    job_id: str,
    dataset_version_id: str,
    model_size: str = "yolo26n",
    epochs: int = 50,
    imgsz: int = 640,
    batch: int = 16,
) -> dict:
    """Dispara treinamento YOLO26 via Ultralytics Hub ou simulação."""
    logger.info(
        "dispatch_training_start: job_id=%s model=%s epochs=%d",
        job_id, model_size, epochs,
    )

    pool = DatabasePool.get_instance()
    repo = AnnotationRepository(pool)

    def update_job(
        status: str,
        progress: int = 0,
        epoch: int = 0,
        metrics: dict | None = None,
        error_msg: str | None = None,
    ) -> None:
        # AND status != 'stopped': o dispatch NUNCA escreve 'stopped' aqui
        # (só stop_job_handler o faz) — este guard impede que um stop
        # concorrente seja revertido de volta para 'running'/'failed'
        # (achado da revisão: race com update_fn("running", ...) antes do
        # provisioning da instância Vast.ai).
        repo._execute_mutation_no_return(
            """UPDATE training_jobs
               SET status = %s,
                   progress = %s,
                   current_epoch = %s,
                   metrics = %s,
                   error_message = %s,
                   started_at = CASE
                       WHEN started_at IS NULL THEN NOW()
                       ELSE started_at
                   END,
                   completed_at = CASE
                       WHEN %s IN ('completed', 'failed') THEN NOW()
                       ELSE completed_at
                   END
               WHERE id = %s AND status != 'stopped'""",
            (
                status, progress, epoch,
                json.dumps(metrics or {}), error_msg,
                status,
                job_id,
            ),
        )
        _publish_progress(job_id, {
            "job_id": job_id,
            "stage": status,
            "progress": progress,
            "epoch": epoch,
            "metrics": metrics or {},
            "error": error_msg,
        })

    try:
        update_job("running", progress=0)

        vast_key = os.environ.get("VAST_API_KEY", "")
        hub_key = os.environ.get("ULTRALYTICS_HUB_API_KEY", "")

        if vast_key:
            logger.info("dispatch_training_vast: job_id=%s", job_id)
            result = _dispatch_vast_ai(job_id, model_size, epochs, imgsz, batch, update_job)
        elif hub_key:
            logger.info("dispatch_training_hub: job_id=%s", job_id)
            result = _dispatch_hub(
                job_id, dataset_version_id, model_size, epochs, imgsz, batch,
                hub_key, update_job,
            )
        else:
            logger.info(
                "dispatch_training_simulated: job_id=%s (sem VAST_API_KEY nem HUB_KEY)",
                job_id,
            )
            result = _simulate_training(job_id, model_size, epochs, update_job)

        model_path = result.get("model_path", f"models/{job_id}/best.pt")
        metrics = result.get("metrics", {})
        # Origem do treino (migration 090): cada branch de dispatch informa
        # 'source' no resultado ('ultralytics_hub' | 'simulated' | 'vast_ai').
        origin = result.get("source", "unknown")

        # Guarda anti-duplicação (ajuste vinculante #2): job_id não tem UNIQUE
        # e o bridge (socket_bridge._register_trained_model) também registra.
        existing = repo._execute_one(
            "SELECT id FROM trained_models WHERE job_id = %s LIMIT 1", (job_id,)
        )
        if existing:
            logger.info("dispatch_training_model_exists: job_id=%s — skip INSERT", job_id)
        else:
            repo._execute_mutation_no_return(
                """INSERT INTO trained_models
                   (id, user_id, job_id, name, model_path,
                    map50, precision, recall, is_active, created_at,
                    created_by, origin, tenant_id)
                   SELECT %s, tj.user_id, %s, %s, %s, %s, %s, %s, FALSE, NOW(),
                          tj.user_id, %s, u.tenant_id
                   FROM training_jobs tj
                   JOIN users u ON u.id = tj.user_id
                   WHERE tj.id = %s""",
                (
                    str(uuid4()), job_id,
                    f"YOLO26 {model_size} - Job {job_id[:8]}",
                    model_path,
                    metrics.get("mAP50", 0.0),
                    metrics.get("precision", 0.0),
                    metrics.get("recall", 0.0),
                    origin,
                    job_id,
                ),
            )

        update_job("completed", progress=100, epoch=epochs, metrics=metrics)
        logger.info("dispatch_training_completed: job_id=%s", job_id)
        return {"job_id": job_id, "status": "completed", "metrics": metrics}

    except _JobStoppedError as exc:
        # Job parado explicitamente via stop_job_handler — status e
        # callback_token já foram tratados por lá. NUNCA marcar 'failed'
        # (sobrescreveria 'stopped') nem reagendar (self.retry provisionaria
        # uma segunda instância GPU paga para um job já cancelado).
        logger.info("dispatch_training_stopped: job_id=%s msg=%s", job_id, exc)
        return {"job_id": job_id, "status": "stopped"}

    except Exception as exc:
        logger.error(
            "dispatch_training_failed: job_id=%s err=%s", job_id, exc, exc_info=True
        )
        with contextlib.suppress(Exception):
            update_job("failed", error_msg=str(exc)[:500])
        raise self.retry(exc=exc, countdown=30) from exc


def _dispatch_hub(
    job_id: str,
    dataset_version_id: str,
    model_size: str,
    epochs: int,
    imgsz: int,
    batch: int,
    hub_api_key: str,
    update_fn,
) -> dict:
    """Dispatch direto para Ultralytics Hub REST API.

    Faz polling no Hub até completar. Sem dependências extras — usa urllib.
    """
    base = "https://hub.ultralytics.com/v1"
    auth = f"Bearer {hub_api_key}"

    def hub_post(path: str, body: dict) -> dict:
        payload = json.dumps(body).encode()
        req = urllib.request.Request(  # noqa: S310
            f"{base}{path}",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": auth},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            return json.loads(resp.read().decode())

    def hub_get(path: str) -> dict:
        req = urllib.request.Request(  # noqa: S310
            f"{base}{path}",
            headers={"Authorization": auth},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            return json.loads(resp.read().decode())

    try:
        # Criar modelo no Hub (dataset já foi uploadado pelo training-service)
        # Neste fallback Celery usamos dataset_version_id como referência
        model_data = hub_post("/models", {
            "meta": {"name": f"epi-celery-{job_id[:8]}"},
            "data": {
                "datasetId": dataset_version_id,
                "modelType": model_size,
                "trainArgs": {"epochs": epochs, "batch": batch, "imgsz": imgsz, "task": "detect"},
            },
        })
        model_id = model_data["data"]["id"]
        logger.info("hub_celery_model_created: job=%s model_id=%s", job_id, model_id)

        # Iniciar training
        hub_post(f"/models/{model_id}/deploy", {})

    except Exception as exc:
        logger.warning(
            "hub_celery_dispatch_failed: job=%s err=%s — fallback simulado", job_id, exc
        )
        return _simulate_training(job_id, model_size, epochs, update_fn)

    # Polling
    poll_interval = 30
    max_polls = int(epochs * 90 / poll_interval) + 60
    start_time = time.time()

    for poll_num in range(max_polls):
        time.sleep(poll_interval)

        try:
            m = hub_get(f"/models/{model_id}")
            model_info = m.get("data", {})
        except Exception as exc:
            logger.warning("hub_poll_failed: job=%s poll=%d err=%s", job_id, poll_num, exc)
            continue

        raw_status = model_info.get("status", "created")
        current_epoch = model_info.get("epoch", 0)
        elapsed = time.time() - start_time
        est_total = max(epochs * 60, 60)
        progress = min(95, int((elapsed / est_total) * 100))

        if raw_status in ("training", "queued", "created"):
            raw_m = model_info.get("metrics") or {}
            metrics = {
                "mAP50": float(raw_m.get("mAP50", 0.0)),
                "precision": float(raw_m.get("precision", 0.0)),
                "recall": float(raw_m.get("recall", 0.0)),
                "loss": float(raw_m.get("loss", 0.0)),
            }
            update_fn("running", progress=progress, epoch=current_epoch, metrics=metrics)

        elif raw_status in ("trained", "exported"):
            raw_m = model_info.get("metrics") or {}
            metrics = {
                "mAP50": float(raw_m.get("mAP50", 0.0)),
                "precision": float(raw_m.get("precision", 0.0)),
                "recall": float(raw_m.get("recall", 0.0)),
                "loss": float(raw_m.get("loss", 0.0)),
            }
            logger.info("hub_celery_completed: job=%s", job_id)
            return {
                "model_path": f"models/{job_id}/best.pt",
                "metrics": metrics,
                "source": "ultralytics_hub",
            }

        elif raw_status in ("failed", "stopped", "canceled"):
            raise RuntimeError(f"Hub training {raw_status}: job={job_id}")

    raise RuntimeError(f"Hub training timed out after {max_polls} polls: job={job_id}")


def _get_job_tenant_id(job_id: str) -> str | None:
    """tenant_id REAL do job (training_jobs.tenant_id, fallback users.tenant_id)."""
    try:
        pool = DatabasePool.get_instance()
        repo = AnnotationRepository(pool)
        row = repo._execute_one(
            """SELECT COALESCE(tj.tenant_id, u.tenant_id) AS tenant_id
               FROM training_jobs tj
               LEFT JOIN users u ON u.id = tj.user_id
               WHERE tj.id = %s""",
            (job_id,),
        )
        return str(row["tenant_id"]) if row and row.get("tenant_id") else None
    except Exception as exc:
        logger.warning("vast_ai_tenant_lookup_failed: job=%s err=%s", job_id, exc)
        return None


_PRESIGNED_GET_TTL = 21600   # 6h — download do dataset pode esperar provisioning
_PRESIGNED_PUT_TTL = 28800   # 8h — uploads acontecem no fim do treino
_DEFAULT_PUBLIC_API_URL = "https://api-v3-production-2b22.up.railway.app"

# RF-DETR/YOLOX esperam pastas "train/valid/test" (padrão Roboflow) — o
# export da pipeline usa "train/val/test" (ver versioning_v2._SPLIT_NAMES).
_VAST_ZIP_SPLIT_NAMES = ("train", "val", "test")
_VAST_ZIP_FOLDER_ALIAS = {"val": "valid"}


def _build_vast_dataset_zip(storage: Any, coco_prefix: str) -> bytes:
    """Empacota o COCO exportado (prefixo com train/val/test) num zip único.

    remote_train.py roda numa instância efêmera sem credenciais R2 (só
    recebe presigned URLs, por desenho de segurança do ADR-0038) e baixa UM
    arquivo via GET + `zipfile.ZipFile(...).extractall(...)` — mas
    `coco_r2_key` é um PREFIXO (múltiplos objetos soltos), não um zip; um
    presigned GET nele não resolve pra nada baixável. Sem este empacotamento,
    todo dispatch real pro Vast.ai falharia no primeiro passo (download do
    dataset). Renomeia "val" → "valid" no zip (RFDETR/Roboflow-padrão) sem
    alterar o layout per-split já consumido por dataset_service.get_version_detail.
    """
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for split_name in _VAST_ZIP_SPLIT_NAMES:
            zip_folder = _VAST_ZIP_FOLDER_ALIAS.get(split_name, split_name)
            prefix = f"{coco_prefix}/{split_name}/"
            for key in storage.list_keys(prefix):
                data = storage.download_bytes(key)
                arcname = f"{zip_folder}/{key[len(prefix):]}"
                zf.writestr(arcname, data)
    return buf.getvalue()


def _get_vast_context(job_id: str) -> dict[str, Any] | None:
    """Resolve o contexto do dispatch REST real (WS-A4).

    Retorna None quando o fluxo real não é possível (sem API key resolvível
    ou job sem dataset_version com COCO exportado) — o caller cai no fluxo
    legado/simulação, preservando o comportamento provado pelos testes PR-1.
    """
    try:
        pool = DatabasePool.get_instance()
        if pool is None:
            return None
        repo = TrainingRepository(pool)
        job = repo._execute_one(
            """SELECT tj.id, tj.dataset_version_id, tj.framework, tj.total_epochs,
                      COALESCE(tj.tenant_id, u.tenant_id) AS tenant_id,
                      dv.coco_r2_key
               FROM training_jobs tj
               LEFT JOIN users u ON u.id = tj.user_id
               LEFT JOIN dataset_versions dv ON dv.id = tj.dataset_version_id
               WHERE tj.id = %s""",
            (job_id,),
        )
        if not job or not job.get("coco_r2_key"):
            return None
        tenant_id = str(job["tenant_id"]) if job.get("tenant_id") else None
        api_key = resolve_vast_api_key(tenant_id)
        if not api_key:
            return None
        return {
            "api_key": api_key,
            "tenant_id": tenant_id,
            "coco_r2_key": str(job["coco_r2_key"]),
            "framework": str(job.get("framework") or "rfdetr"),
        }
    except Exception as exc:
        logger.warning("vast_context_lookup_failed: job=%s err=%s", job_id, exc)
        return None


def _read_remote_train_source() -> str:
    """Lê o runner self-contained embarcado no onstart (heredoc).

    A instância Vast NÃO tem acesso ao repositório — o script inteiro é
    embutido no onstart em vez de baixado.
    """
    from pathlib import Path  # noqa: PLC0415

    path = (
        Path(__file__).resolve().parents[6] / "training" / "vast" / "remote_train.py"
    )
    return path.read_text(encoding="utf-8")


def _build_vast_onstart(env: dict[str, str], remote_source: str) -> str:
    """Monta o onstart: embute remote_train.py via heredoc + exports + exec.

    Presigned URLs são URL-encoded (sem aspas simples) — exports com aspas
    simples são seguros contra expansão de shell.
    """
    exports = "\n".join(f"export {key}='{value}'" for key, value in env.items())
    return (
        "#!/bin/bash\n"
        "set -e\n"
        "cd /root\n"
        "cat > /root/remote_train.py <<'RECOGNITION_REMOTE_TRAIN_EOF'\n"
        f"{remote_source}\n"
        "RECOGNITION_REMOTE_TRAIN_EOF\n"
        f"{exports}\n"
        "nohup python3 /root/remote_train.py > /root/remote_train.log 2>&1 &\n"
    )


def _watch_vast_job(
    client: VastAIClient,
    repo: TrainingRepository,
    job_id: str,
    instance_id: int | str,
    r2_onnx_key: str,
) -> dict:
    """Watchdog: poll da instância + do job até callback final ou timeout.

    NOTA (plano WS-A4): o loop bloqueia o worker Celery da fila 'training'
    com time.sleep — aceitável porque a fila é dedicada a treino (1 job por
    vez) e o custo real está na GPU remota, não nesta CPU. O progresso REAL
    chega via POST progress-callback (atualiza o DB); este loop é apenas
    watchdog de instância morta/timeout.

    Timeout: env VAST_TIMEOUT_SECONDS (default 7200s). Intervalo: env
    VAST_POLL_INTERVAL_SECONDS (default 60s).
    """
    timeout = int(os.environ.get("VAST_TIMEOUT_SECONDS", "7200"))
    interval = int(os.environ.get("VAST_POLL_INTERVAL_SECONDS", "60"))
    deadline = time.monotonic() + timeout
    dead_polls = 0

    while time.monotonic() < deadline:
        time.sleep(interval)

        job = repo._execute_one(
            "SELECT status, metrics FROM training_jobs WHERE id = %s", (job_id,)
        )
        status = (job or {}).get("status")
        if status == "completed":
            raw_metrics = (job or {}).get("metrics") or {}
            if isinstance(raw_metrics, str):
                with contextlib.suppress(ValueError):
                    raw_metrics = json.loads(raw_metrics)
            metrics = raw_metrics if isinstance(raw_metrics, dict) else {}
            return {
                "model_path": r2_onnx_key,
                "metrics": metrics,
                "source": "vast_ai",
            }
        if status == "stopped":
            raise _JobStoppedError(f"Job {job_id} foi parado durante o watchdog")
        if status == "failed":
            raise RuntimeError(f"Treinamento vast_ai {status}: job={job_id}")

        try:
            instance = client.get_instance_status(instance_id)
            actual = str(instance.get("actual_status", ""))
        except VastAIError as exc:
            logger.warning(
                "vast_watchdog_poll_failed: job=%s instance=%s err=%s",
                job_id, instance_id, exc,
            )
            continue

        if actual in ("exited", "stopped", "offline"):
            dead_polls += 1
            if dead_polls >= 3:
                raise RuntimeError(
                    f"Instância Vast.ai terminou sem callback final: "
                    f"job={job_id} instance={instance_id} status={actual}"
                )
        else:
            dead_polls = 0

    raise RuntimeError(f"Timeout vast_ai após {timeout}s: job={job_id}")


def _run_vast_remote_training(
    ctx: dict[str, Any],
    job_id: str,
    model_size: str,
    epochs: int,
    imgsz: int,
    batch: int,
    update_fn,
) -> dict:
    """Fluxo REST real: presigned URLs + instância com onstart + watchdog.

    destroy_instance SEMPRE roda (try/finally) — nunca vazar GPU paga.
    callback_token é revogado (NULL) ao final, sucesso ou erro.
    """
    pool = DatabasePool.get_instance()
    repo = TrainingRepository(pool)

    tenant_id = ctx.get("tenant_id") or "unknown"
    framework = ctx.get("framework") or (
        "yolox" if "yolox" in model_size.lower() else "rfdetr"
    )

    # Token por-job (ajuste C-1 da crítica): aleatório, revogável no stop.
    callback_token = secrets.token_urlsafe(48)
    repo._execute_mutation_no_return(
        "UPDATE training_jobs SET callback_token = %s, gpu_provider = 'vast_ai' "
        "WHERE id = %s",
        (callback_token, job_id),
    )

    storage = get_storage(tenant_id)
    zip_key = f"{ctx['coco_r2_key']}/dataset.zip"
    storage.upload_bytes(
        zip_key, _build_vast_dataset_zip(storage, ctx["coco_r2_key"]),
        "application/zip",
    )
    dataset_url = storage.generate_presigned_download_url(
        zip_key, ttl=_PRESIGNED_GET_TTL
    )
    artifact_prefix = f"models/{tenant_id}/vast/{job_id}"
    r2_onnx_key = f"{artifact_prefix}/model.onnx"
    r2_weights_key = f"{artifact_prefix}/weights.pth"
    r2_metrics_key = f"{artifact_prefix}/metrics.json"

    base_url = os.environ.get("PUBLIC_API_URL", _DEFAULT_PUBLIC_API_URL).rstrip("/")
    callback_url = f"{base_url}/api/v1/training/jobs/{job_id}/progress-callback"

    remote_env = {
        "DATASET_URL": dataset_url,
        "FRAMEWORK": framework,
        "EPOCHS": str(epochs),
        "BATCH": str(batch),
        "IMGSZ": str(imgsz),
        "CALLBACK_URL": callback_url,
        "CALLBACK_TOKEN": callback_token,
        "UPLOAD_URL_ONNX": storage.generate_presigned_upload_url(
            r2_onnx_key, content_type="application/octet-stream",
            ttl=_PRESIGNED_PUT_TTL,
        ),
        "UPLOAD_URL_WEIGHTS": storage.generate_presigned_upload_url(
            r2_weights_key, content_type="application/octet-stream",
            ttl=_PRESIGNED_PUT_TTL,
        ),
        "UPLOAD_URL_METRICS": storage.generate_presigned_upload_url(
            r2_metrics_key, content_type="application/json",
            ttl=_PRESIGNED_PUT_TTL,
        ),
        "R2_ONNX_KEY": r2_onnx_key,
    }
    onstart = _build_vast_onstart(remote_env, _read_remote_train_source())

    client = VastAIClient(ctx["api_key"])
    update_fn("running", progress=2)

    # Recheca status ANTES de provisionar: fecha a janela de corrida em que
    # um stop concorrente (entre o início do dispatch e este ponto) seria
    # ignorado e uma instância GPU paga criada para um job já cancelado
    # (achado da revisão adversarial). update_fn acima não sobrescreve
    # 'stopped' (guard na UPDATE), então esta leitura reflete o stop real.
    current = repo._execute_one(
        "SELECT status FROM training_jobs WHERE id = %s", (job_id,)
    )
    if (current or {}).get("status") == "stopped":
        raise _JobStoppedError(
            f"Job {job_id} foi parado antes do provisioning — abortando sem criar instância"
        )

    offers = client.search_offers()
    if not offers:
        raise RuntimeError(
            "Nenhuma oferta GPU (RTX 4090/3090) dentro do price-cap VAST_PRICE_CAP"
        )

    instance_id: int | str | None = None
    try:
        created = client.create_instance(
            offers[0]["id"],
            onstart=onstart,
            label=f"recognition-train-{job_id[:8]}",
        )
        instance_id = created["new_contract"]
        repo._execute_mutation_no_return(
            "UPDATE training_jobs SET gpu_instance_ref = %s WHERE id = %s",
            (str(instance_id), job_id),
        )
        logger.info(
            "vast_rest_instance_started: job=%s instance=%s offer=%s dph=%s",
            job_id, instance_id, offers[0].get("id"), offers[0].get("dph_total"),
        )
        update_fn("running", progress=5)

        return _watch_vast_job(client, repo, job_id, instance_id, r2_onnx_key)
    finally:
        # SEMPRE: destruir instância (não vazar GPU paga) e revogar token.
        if instance_id is not None:
            with contextlib.suppress(Exception):
                client.destroy_instance(instance_id)
        with contextlib.suppress(Exception):
            repo._execute_mutation_no_return(
                "UPDATE training_jobs SET callback_token = NULL WHERE id = %s",
                (job_id,),
            )


def _dispatch_vast_ai(
    job_id: str,
    model_size: str,
    epochs: int,
    imgsz: int,
    batch: int,
    update_fn,
) -> dict:
    """Dispara treinamento real na Vast.ai (WS-A4).

    Fluxo REST real quando o contexto completo existe (API key do tenant ou
    env + dataset_version com COCO exportado): presigned GET/PUTs, instância
    com onstart embutindo remote_train.py, watchdog poll e destroy garantido.

    Fallback (contexto incompleto): fluxo legado via provision_and_train.sh;
    sem o script → simulação. Comportamento provado pelos testes do PR-1.
    """
    ctx = _get_vast_context(job_id)
    if ctx is None:
        logger.warning(
            "PENDENCIA: vast_ai sem contexto REST (sem API key resolvível ou "
            "job sem dataset COCO) — job=%s usando fluxo legado/simulação",
            job_id,
        )
        return _dispatch_vast_ai_legacy(
            job_id, model_size, epochs, imgsz, batch, update_fn
        )
    return _run_vast_remote_training(
        ctx, job_id, model_size, epochs, imgsz, batch, update_fn
    )


def _dispatch_vast_ai_legacy(
    job_id: str,
    model_size: str,
    epochs: int,
    imgsz: int,
    batch: int,
    update_fn,
) -> dict:
    """Fluxo legado: treinamento na Vast.ai via provision_and_train.sh.

    Requer: VAST_API_KEY, ROBOFLOW_API_KEY, R2_* env vars.
    O shell script faz todo o ciclo: provisionar GPU → treinar → baixar ONNX → destruir.
    Pode levar 30-90 min dependendo da GPU.
    """
    import subprocess  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    script_path = (
        Path(__file__).resolve().parents[6] / "training" / "vast" / "provision_and_train.sh"
    )
    if not script_path.exists():
        logger.warning(
            "PENDENCIA: provision_and_train.sh ausente (%s) — job=%s caindo "
            "em simulação", script_path, job_id,
        )
        return _simulate_training(job_id, model_size, epochs, update_fn)

    output_dir = Path(tempfile.mkdtemp(prefix=f"vast_train_{job_id[:8]}_"))

    env = os.environ.copy()
    env.update({
        "MODEL": "both" if "both" in model_size.lower() else (
            "yolox" if "yolox" in model_size.lower() else "rfdetr"
        ),
        "EPOCHS": str(epochs),
        "BATCH": str(batch),
        "IMGSZ": str(imgsz),
        "OUTPUT_DIR": str(output_dir),
    })

    update_fn("running", progress=5)
    logger.info("vast_ai_start: job_id=%s script=%s out=%s", job_id, script_path, output_dir)

    proc = subprocess.run(
        ["bash", str(script_path)],
        env=env,
        text=True,
        capture_output=True,
        timeout=7200,  # 2h timeout máximo
    )

    if proc.returncode != 0:
        logger.error("vast_ai_failed: job=%s stderr=%s", job_id, proc.stderr[-2000:])
        raise RuntimeError(
            f"provision_and_train.sh falhou (rc={proc.returncode}): {proc.stderr[-500:]}"
        )

    update_fn("running", progress=90)

    # Ler métricas geradas pelo script
    metrics_file = output_dir / "metrics.json"
    metrics: dict = {}
    if metrics_file.exists():
        try:
            raw = json.loads(metrics_file.read_text())
            # metrics.json pode ter estrutura {yolox: {...}, rfdetr: {...}} ou flat
            if "yolox" in raw or "rfdetr" in raw:
                flat: dict = {}
                for sub in raw.values():
                    if isinstance(sub, dict):
                        flat.update(sub)
                metrics = flat
            else:
                metrics = raw
        except Exception as exc:
            logger.warning("vast_ai_metrics_parse_failed: %s", exc)

    # Localizar ONNX gerado
    onnx_files = list(output_dir.glob("*.onnx"))
    model_key = ""
    if onnx_files:
        model_key = str(metrics.get("r2_key") or "")
        if not model_key:
            # metrics.json sem r2_key: nunca inventar chave de outro tenant —
            # usar o tenant REAL do job ou registrar parcialmente (sem chave).
            tenant_id = _get_job_tenant_id(job_id)
            logger.warning(
                "vast_ai_sem_r2_key: job=%s tenant=%s — artefato sem r2_key — registro parcial",
                job_id, tenant_id,
            )
            if tenant_id:
                model_key = f"models/{tenant_id}/vast/{job_id}.onnx"

    logger.info(
        "vast_ai_completed: job=%s onnx=%d files metrics=%s",
        job_id, len(onnx_files), metrics,
    )

    return {
        "model_path": model_key,
        "metrics": {
            "mAP50": metrics.get("map50", 0.0),
            "precision": metrics.get("precision", 0.0),
            "recall": metrics.get("recall_no_helmet", 0.0),
            **{k: v for k, v in metrics.items() if k not in ("map50", "precision", "recall")},
        },
        "source": "vast_ai",
    }


def _simulate_training(
    job_id: str,
    model_size: str,
    epochs: int,
    update_fn,
) -> dict:
    """Simula treinamento com 10 steps (~20s). Fallback sem GPU."""
    steps = 10
    sleep_per_step = 2

    for step in range(1, steps + 1):
        time.sleep(sleep_per_step)
        progress = int((step / steps) * 100)
        epoch = int((step / steps) * epochs)
        t = step / steps
        metrics = {
            "mAP50":     round(0.3 + 0.5 * t + 0.05 * math.sin(t * 10), 4),
            "precision": round(0.4 + 0.4 * t, 4),
            "recall":    round(0.35 + 0.45 * t, 4),
            "loss":      round(1.5 * (1 - 0.8 * t), 4),
        }
        update_fn("running", progress=progress, epoch=epoch, metrics=metrics)
        logger.debug(
            "simulate_step: job=%s step=%d/%d progress=%d%%",
            job_id, step, steps, progress,
        )

    return {
        "model_path": f"models/{job_id}/best.pt",
        "metrics": {"mAP50": 0.78, "precision": 0.82, "recall": 0.74, "loss": 0.31},
        "source": "simulated",
    }
