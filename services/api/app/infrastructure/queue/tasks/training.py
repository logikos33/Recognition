"""
Recognition — Training Dispatch Task.

Cadeia de dispatch (dispatch_training), task "treino não pode mentir"
(ADR-0060/ADR novo desta task — supersede o Hub e a simulação da ADR-0060):
  1. Vast.ai REST real (VAST_API_KEY resolvível — integration store do
     tenant > env, ver resolve_vast_api_key em infrastructure/gpu/vast_client.py)
     — GPU de terceiro (pode ser RunPod por baixo, investigação em curso):
     SÓ dispara com opt-in explícito do tenant (training_third_party_cloud_enabled,
     checado em `_dispatch_vast_ai`). Sem dataset exportado (coco_r2_key
     ausente) também nunca simula — erro alto (ver `_get_vast_context`).
  2. Edge (BLOQUEADO-HARDWARE, ver training_compute.EdgeProvider) — opt-in
     explícito via feature flag training_compute_target='edge' + edge_site
     cadastrado.
  3. Nenhum provedor real disponível (inclusive tenant configurado
     explicitamente com training_compute_target='local'): erro alto, job
     marcado 'failed' com mensagem clara — NUNCA um artefato fake passando
     por treino real. Ultralytics Hub e a simulação local (_simulate_training/
     LocalProvider) foram DELETADOS nesta task — mentiam sobre o resultado do
     treino (Hub sempre foi SaaS de terceiro fora do controle do tenant;
     simulação nunca treinou nada de verdade). Ver docs/decisions/adr/ (ADR
     desta task) para o inventário completo do que foi removido e por quê.

Regra "nunca completed sem artefato verificável" (mesma task): todo caminho
que persiste um job como 'completed' chama
`app.infrastructure.storage.verify_model_artifact` (HEAD/exists real no
storage) ANTES de gravar — ver o próprio `dispatch_training`, `_watch_vast_job`
e `app/api/v1/training/job_handlers.py::training_progress_callback_handler`.

Ver app/domain/services/integration_service.py → resolve_r2_credentials/
test_vast_connection para a precedência de credenciais R2/Vast.ai.
"""
import contextlib
import json
import logging
import os
import secrets
import time
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
from app.infrastructure.gpu.training_compute import get_training_compute
from app.infrastructure.gpu.vast_client import (
    VastAIClient,
    VastAIError,
    resolve_vast_api_key,
)
from app.infrastructure.queue.celery_app import celery
from app.infrastructure.storage import verify_model_artifact
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

# ADR-0047 (estendida pela task "treino honesto" — achado C5): QUALQUER
# caminho que manda dados de treino a uma GPU de terceiro — Vast.ai REST
# real incluído (pode ser RunPod por baixo, investigação em curso), não só
# Ultralytics Hub e o fluxo legado Vast+Roboflow (provision_and_train.sh) —
# só dispara com opt-in EXPLÍCITO por tenant (feature flag), nunca só por
# uma env var estar setada no processo (isso valeria pra TODOS os tenants
# sem chave própria, achado da investigação C-04 da task-086). Antes desta
# task, só Hub/legado eram gateados — o caminho Vast.ai REST real (o mais
# usado em produção) não tinha NENHUM gate de terceiro.
_FEATURE_FLAG_THIRD_PARTY_CLOUD = "training_third_party_cloud_enabled"


def _third_party_cloud_training_enabled(tenant_id: str | None) -> bool:
    """Opt-in explícito por tenant pra qualquer GPU de terceiro (Vast.ai
    REST real, Ultralytics Hub, Vast+Roboflow legado).

    Fail-safe: qualquer erro de leitura (DB indisponível, tenant sem flags,
    tenant_id ausente) => False. Um erro aqui deve BLOQUEAR o caminho de
    risco (envio a terceiro), nunca liberá-lo — mesmo espírito do ADR-0017,
    aplicado ao inverso de onde ele normalmente se aplica.
    """
    if not tenant_id:
        return False
    try:
        from uuid import UUID  # noqa: PLC0415

        from app.infrastructure.database.repositories.tenant_settings_repository import (  # noqa: PLC0415,E501
            TenantSettingsRepository,
        )

        pool = DatabasePool.get_instance()
        if pool is None:
            return False
        flags = TenantSettingsRepository(pool).get_feature_flags(UUID(str(tenant_id)))
        return flags.get(_FEATURE_FLAG_THIRD_PARTY_CLOUD) is True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "third_party_cloud_flag_read_failed: tenant=%s err=%s", tenant_id, exc
        )
        return False


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

        # WS-D1/ADR-0039: gate do Vast.ai agora é tenant-aware
        # (resolve_vast_api_key: integration store do tenant > env), igual
        # ao que o docstring do módulo sempre alegou mas o código não fazia
        # — bug achado construindo a abstração TrainingCompute (tenant com
        # chave SÓ no integration store, sem VAST_API_KEY no env, nunca
        # disparava o dispatch real; caía direto pra hub/simulação).
        tenant_id = _get_job_tenant_id(job_id)
        compute = get_training_compute(tenant_id)
        logger.info(
            "dispatch_training_compute: job_id=%s provider=%s",
            job_id, type(compute).__name__,
        )
        result = compute.dispatch(
            job_id, dataset_version_id, model_size, epochs, imgsz, batch,
            update_job, tenant_id=tenant_id,
        )

        if result.get("status") == "running":
            # Dispatch assíncrono (hoje só EdgeProvider) — job fica
            # 'running' (já setado acima); sem trained_models ainda, a
            # finalização real depende de um callback que não existe
            # (BLOQUEADO-HARDWARE, ver ADR-0039).
            logger.info(
                "dispatch_training_async_pending: job_id=%s source=%s",
                job_id, result.get("source"),
            )
            return {"job_id": job_id, "status": "running", "source": result.get("source")}

        model_path = result.get("model_path", f"models/{job_id}/best.pt")
        metrics = result.get("metrics", {})
        # Origem do treino (migration 090): cada branch de dispatch informa
        # 'source' no resultado ('vast_ai' hoje — Hub e simulação foram
        # deletados na task "treino não pode mentir").
        origin = result.get("source", "unknown")

        # "Treino não pode mentir": nunca marcar completed/gravar trained_models
        # sem confirmar que o artefato existe DE FATO no storage (HEAD/exists
        # real — nunca confiar só no que o provider *diz* que produziu).
        # Achado desta task: antes, um provider podia relatar sucesso sem
        # nenhum artefato real (Hub com export falho, callback adulterado)
        # e o registry ganhava uma linha apontando pra um objeto inexistente.
        if not verify_model_artifact(tenant_id, model_path):
            raise RuntimeError(
                "Treino reportou sucesso mas o artefato do modelo não foi "
                f"confirmado no storage (r2_key={model_path!r}) — job={job_id} "
                "nunca registrado como completed sem artefato real."
            )

        # Guarda anti-duplicação (ajuste vinculante #2): job_id não tem UNIQUE
        # e o bridge (socket_bridge._register_trained_model) também registra.
        existing = repo._execute_one(
            "SELECT id FROM trained_models WHERE job_id = %s LIMIT 1", (job_id,)
        )
        if existing:
            logger.info("dispatch_training_model_exists: job_id=%s — skip INSERT", job_id)
        else:
            new_model_id = str(uuid4())
            # Linhagem (migration 098): framework vem do job (training_jobs.framework,
            # NOT NULL DEFAULT 'rfdetr' desde a 097); r2_onnx_key só é preenchido
            # quando o artefato É de fato um objeto R2 (fluxo vast_ai real —
            # model_path == r2_onnx_key, ver _watch_vast_job) — nunca para
            # hub/simulado, cujo model_path não aponta pra nenhum artefato real.
            r2_onnx_key = model_path if origin == "vast_ai" else None
            # C2 (task "treino honesto"): metrics (JSONB, migration 098 —
            # campo JSON já existente, sem migration nova) carrega o marcador
            # {'simulated': true, ...} pra artefatos simulados — indelével,
            # sobrevive independente de qualquer futura mudança em `origin`.
            repo._execute_mutation_no_return(
                """INSERT INTO trained_models
                   (id, user_id, job_id, name, model_path,
                    map50, precision, recall, is_active, created_at,
                    created_by, origin, tenant_id, framework,
                    r2_onnx_key, dataset_version_id, metrics)
                   SELECT %s, tj.user_id, %s, %s, %s, %s, %s, %s, FALSE, NOW(),
                          tj.user_id, %s, u.tenant_id, tj.framework, %s, %s, %s
                   FROM training_jobs tj
                   JOIN users u ON u.id = tj.user_id
                   WHERE tj.id = %s""",
                (
                    new_model_id, job_id,
                    f"YOLO26 {model_size} - Job {job_id[:8]}",
                    model_path,
                    metrics.get("mAP50", 0.0),
                    metrics.get("precision", 0.0),
                    metrics.get("recall", 0.0),
                    origin,
                    r2_onnx_key,
                    dataset_version_id,
                    json.dumps(metrics),
                    job_id,
                ),
            )
            # WS-C1 (best-effort): dispara avaliação campeão×desafiante do
            # modelo recém-criado. Nunca falha o job de treino — o modelo
            # criado aqui tipicamente não tem r2_onnx_key (coluna legada
            # model_path é reusada pro path do artefato nesta branch), a
            # task retorna status="error"/missing_onnx_key graciosamente
            # nesse caso (mesmo padrão de tasks/model_validation.py).
            #
            # Não há mais branch "simulated" a pular (task "treino não pode
            # mentir" — _simulate_training foi deletado): o artefato já foi
            # confirmado real no storage acima (verify_model_artifact), então
            # todo modelo que chega aqui é candidato legítimo a campeão.
            try:
                from app.infrastructure.queue.tasks.model_evaluation import (  # noqa: PLC0415,E501
                    evaluate_challenger_model,
                )
                evaluate_challenger_model.delay(new_model_id)
            except Exception as eval_exc:  # noqa: BLE001
                logger.warning(
                    "dispatch_training_eval_trigger_failed: model=%s err=%s",
                    new_model_id, eval_exc,
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
    tenant_id: str | None,
) -> dict:
    """Watchdog: poll da instância + do job até callback final ou timeout.

    NOTA (plano WS-A4): o loop bloqueia o worker Celery da fila 'training'
    com time.sleep — aceitável porque a fila é dedicada a treino (1 job por
    vez) e o custo real está na GPU remota, não nesta CPU. O progresso REAL
    chega via POST progress-callback (atualiza o DB); este loop é apenas
    watchdog de instância morta/timeout.

    Timeout: env VAST_TIMEOUT_SECONDS (default 7200s). Intervalo: env
    VAST_POLL_INTERVAL_SECONDS (default 60s).

    "Treino não pode mentir": mesmo com training_jobs.status='completed' (já
    escrito pelo callback — ver job_handlers.py, que faz sua PRÓPRIA
    verificação antes de gravar esse status), este watchdog reconfirma o
    artefato antes de repassar "completed" pra dispatch_training gravar
    trained_models — defesa em profundidade contra qualquer escrita direta
    de status que não passe pelo callback.
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
            if not verify_model_artifact(tenant_id, r2_onnx_key):
                raise RuntimeError(
                    f"Job {job_id} marcado completed mas o artefato não foi "
                    f"confirmado no storage (r2_key={r2_onnx_key}) — watchdog "
                    "recusa reportar sucesso sem artefato real."
                )
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
    r2_onnx_key = vast_onnx_artifact_key(tenant_id, job_id)
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

        return _watch_vast_job(client, repo, job_id, instance_id, r2_onnx_key, tenant_id)
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
    tenant_id: str | None = None,
) -> dict:
    """Dispara treinamento real na Vast.ai (WS-A4).

    Fluxo REST real quando o contexto completo existe (API key do tenant ou
    env + dataset_version com COCO exportado): presigned GET/PUTs, instância
    com onstart embutindo remote_train.py, watchdog poll e destroy garantido.

    C5/ADR-0047 (task "treino honesto"): Vast.ai É GPU de terceiro (pode ser
    RunPod por baixo — investigação em curso) — o fluxo REST real só dispara
    com o MESMO opt-in explícito (`training_third_party_cloud_enabled`) que
    já protegia Hub/legado. Achado desta task: antes, este era o único
    caminho de dispatch externo SEM nenhum gate — o mais usado em produção.

    C1/ADR-0017 (task "treino honesto"): dataset ausente (sem coco_r2_key
    resolvível) é erro alto com mensagem clara — NUNCA desvia para dataset de
    outra origem. O fluxo legado que fazia isso (`_dispatch_vast_ai_legacy`,
    que treinava no dataset PÚBLICO do Roboflow via provision_and_train.sh —
    achado: mascarava "seu dataset não foi exportado" treinando
    silenciosamente em dados de outra origem, tão desonesto quanto simulação)
    foi DELETADO na task "treino não pode mentir", junto com os scripts que
    ele invocava (training/vast/provision_and_train.sh, train_rfdetr.py,
    train_yolox.py, upload_and_register.py).
    """
    if not _third_party_cloud_training_enabled(tenant_id):
        raise RuntimeError(
            "Treino em nuvem de terceiro desabilitado para este tenant "
            f"(training_third_party_cloud_enabled=false) — caminho=vast_ai "
            f"job={job_id}"
        )
    ctx = _get_vast_context(job_id)
    if ctx is None:
        if not resolve_vast_api_key(tenant_id):
            raise RuntimeError(
                f"Nenhuma chave Vast.ai resolvível para o tenant — job={job_id}"
            )
        raise RuntimeError(
            f"Job {job_id}: dataset sem exportação COCO (coco_r2_key ausente "
            "no dataset_version vinculado) — não é possível treinar no "
            "Vast.ai. Exporte o dataset (build_dataset_version) antes de "
            "disparar o treino."
        )
    return _run_vast_remote_training(
        ctx, job_id, model_size, epochs, imgsz, batch, update_fn
    )


def vast_onnx_artifact_key(tenant_id: str | None, job_id: str) -> str:
    """Chave R2 determinística do ONNX de um job Vast.ai.

    Mesma fórmula usada no dispatch (`_run_vast_remote_training`, que injeta
    esta chave como R2_ONNX_KEY/UPLOAD_URL_ONNX na instância remota) e na
    reverificação pós-callback (`app/api/v1/training/job_handlers.py::
    training_progress_callback_handler`) — nunca duplicar como f-string solta
    em outro lugar (task "treino não pode mentir").
    """
    return f"models/{tenant_id}/vast/{job_id}/model.onnx"
