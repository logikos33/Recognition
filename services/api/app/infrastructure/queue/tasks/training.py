"""
Recognition — Training Dispatch Task.

Cadeia de dispatch (dispatch_training), task "treino não pode mentir"
(ADR-0060) + task "runner genérico RunPod" (substitui Vast.ai — decisão do
dono, `infrastructure/gpu/vast_client.py` deletado, a API console.vast.ai
nunca entregou treino real em produção):
  1. RunPod REST real (RUNPOD_API_KEY resolvível — integration store do
     tenant > env, ver resolve_runpod_api_key em infrastructure/gpu/runpod_client.py)
     — GPU de terceiro: SÓ dispara com opt-in explícito do tenant
     (training_third_party_cloud_enabled, checado em `_dispatch_runpod_train`).
     Sem dataset exportado (coco_r2_key ausente) também nunca simula — erro
     alto (ver `_get_runpod_training_context`). O ciclo de vida do pod
     (preço → teto de custo → criar → acompanhar → matar) vive no runner
     genérico `infrastructure/gpu/runpod_runner.py::run_runpod_job` — as três
     camadas de garantia de morte (trap local, watchdog Celery, reconciler
     celery-beat) estão documentadas lá.
  2. Edge (BLOQUEADO-HARDWARE, ver training_compute.EdgeProvider) — opt-in
     explícito via feature flag training_compute_target='edge' + edge_site
     cadastrado.
  3. Nenhum provedor real disponível (inclusive tenant configurado
     explicitamente com training_compute_target='local'): erro alto, job
     marcado 'failed' com mensagem clara — NUNCA um artefato fake passando
     por treino real. Ultralytics Hub e a simulação local (_simulate_training/
     LocalProvider) foram DELETADOS na task "treino não pode mentir" —
     mentiam sobre o resultado do treino. Ver docs/decisions/adr/ para o
     inventário completo do que foi removido e por quê.

Regra "nunca completed sem artefato verificável" (task "treino não pode
mentir"): todo caminho que persiste um job como 'completed' chama
`app.infrastructure.storage.verify_model_artifact` (HEAD/exists real no
storage) ANTES de gravar — ver o próprio `dispatch_training`,
`runpod_runner.run_runpod_job` (via `verify_completed_fn`) e
`app/api/v1/training/job_handlers.py::training_progress_callback_handler`.

Ver app/domain/services/integration_service.py → resolve_r2_credentials
para a precedência de credenciais R2.
"""
import contextlib
import json
import logging
import os
import secrets
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
from app.infrastructure.gpu.license_gate import assert_rfdetr_variant_allowed
from app.infrastructure.gpu.runpod_client import RunPodClient, resolve_runpod_api_key
from app.infrastructure.gpu.runpod_runner import JobKind, JobStoppedError, run_runpod_job
from app.infrastructure.gpu.training_compute import get_training_compute
from app.infrastructure.queue.celery_app import celery
from app.infrastructure.storage import verify_model_artifact
from app.infrastructure.storage.local_storage import get_storage

logger = logging.getLogger(__name__)

# Alias preservado (era a classe local `_JobStoppedError`): agora vive em
# `runpod_runner.py` (genérica — reusável por qualquer JobKind), mas o nome
# privado permanece aqui porque é isso que dispatch_training/testes importam.
# Job foi parado explicitamente (stop_job_handler) durante o dispatch.
#
# Achado da revisão adversarial (ainda válido com RunPod): sem essa
# distinção, um stop que chega entre o início do dispatch e a criação do pod
# (ou entre a criação e o próximo poll do watchdog) era tratado como falha
# genérica → update_job("failed", ...) sobrescrevia 'stopped' e o Celery
# reagendava dispatch_training (max_retries=1), provisionando um SEGUNDO
# pod GPU pago pra um job que o usuário já tinha cancelado.
# dispatch_training captura este tipo especificamente e NUNCA chama
# self.retry() para ele.
_JobStoppedError = JobStoppedError

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
_PROGRESS_TTL = 86400  # 24h

# ADR-0047 (estendida pela task "treino honesto" — achado C5): QUALQUER
# caminho que manda dados de treino a uma GPU de terceiro — RunPod REST
# real incluído, não só Ultralytics Hub e o fluxo legado Vast+Roboflow
# (deletados) — só dispara com opt-in EXPLÍCITO por tenant (feature flag),
# nunca só por uma env var estar setada no processo (isso valeria pra TODOS
# os tenants sem chave própria, achado da investigação C-04 da task-086).
_FEATURE_FLAG_THIRD_PARTY_CLOUD = "training_third_party_cloud_enabled"


def _third_party_cloud_training_enabled(tenant_id: str | None) -> bool:
    """Opt-in explícito por tenant pra qualquer GPU de terceiro (RunPod REST
    real, Ultralytics Hub e Vast+Roboflow legado — ambos deletados).

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
        # provisioning do pod GPU).
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

        # WS-D1/ADR-0039: gate do RunPod é tenant-aware (resolve_runpod_api_key:
        # integration store do tenant > env), igual ao que o docstring do
        # módulo sempre alegou pro Vast.ai — mesmo comportamento preservado
        # na troca de provedor (tenant com chave SÓ no integration store,
        # sem RUNPOD_API_KEY no env, ainda dispara o dispatch real).
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
        # 'source' no resultado ('runpod' hoje — Hub, simulação e Vast.ai
        # foram deletados/substituídos).
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
            # quando o artefato É de fato um objeto R2 (fluxo runpod real —
            # model_path == r2_onnx_key, ver runpod_runner.run_runpod_job) —
            # nunca para hub/simulado, cujo model_path não aponta pra nenhum
            # artefato real.
            r2_onnx_key = model_path if origin == "runpod" else None
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
        logger.warning("job_tenant_lookup_failed: job=%s err=%s", job_id, exc)
        return None


_PRESIGNED_GET_TTL = 21600   # 6h — download do dataset pode esperar provisioning
_PRESIGNED_PUT_TTL = 28800   # 8h — uploads acontecem no fim do treino
_DEFAULT_PUBLIC_API_URL = "https://api-v3-production-2b22.up.railway.app"

# RF-DETR/YOLOX esperam pastas "train/valid/test" (padrão Roboflow) — o
# export da pipeline usa "train/val/test" (ver versioning_v2._SPLIT_NAMES).
_TRAIN_ZIP_SPLIT_NAMES = ("train", "val", "test")
_TRAIN_ZIP_FOLDER_ALIAS = {"val": "valid"}


def _build_training_dataset_zip(storage: Any, coco_prefix: str) -> bytes:
    """Empacota o COCO exportado (prefixo com train/val/test) num zip único.

    remote_train.py roda num pod efêmero sem credenciais R2 (só recebe
    presigned URLs, por desenho de segurança do ADR-0038) e baixa UM arquivo
    via GET + `zipfile.ZipFile(...).extractall(...)` — mas `coco_r2_key` é um
    PREFIXO (múltiplos objetos soltos), não um zip; um presigned GET nele não
    resolve pra nada baixável. Sem este empacotamento, todo dispatch real
    pro RunPod falharia no primeiro passo (download do dataset). Renomeia
    "val" → "valid" no zip (RFDETR/Roboflow-padrão) sem alterar o layout
    per-split já consumido por dataset_service.get_version_detail.
    """
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for split_name in _TRAIN_ZIP_SPLIT_NAMES:
            zip_folder = _TRAIN_ZIP_FOLDER_ALIAS.get(split_name, split_name)
            prefix = f"{coco_prefix}/{split_name}/"
            for key in storage.list_keys(prefix):
                data = storage.download_bytes(key)
                arcname = f"{zip_folder}/{key[len(prefix):]}"
                zf.writestr(arcname, data)
    return buf.getvalue()


def _get_runpod_training_context(job_id: str) -> dict[str, Any] | None:
    """Resolve o contexto do dispatch REST real (WS-A4, RunPod).

    Retorna None quando o fluxo real não é possível (sem API key resolvível
    ou job sem dataset_version com COCO exportado) — o caller levanta erro
    claro (nunca cai num fluxo alternativo silencioso, ADR-0017).

    Inclui `base_model`/`hyperparams` (migration 097) pro license gate
    (`assert_rfdetr_variant_allowed`, ADR-0044) — nenhuma variante RF-DETR
    fora do allowlist Apache 2.0 pode chegar até o pod.
    """
    try:
        pool = DatabasePool.get_instance()
        if pool is None:
            return None
        repo = TrainingRepository(pool)
        job = repo._execute_one(
            """SELECT tj.id, tj.dataset_version_id, tj.framework, tj.total_epochs,
                      tj.base_model, tj.hyperparams,
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
        api_key = resolve_runpod_api_key(tenant_id)
        if not api_key:
            return None
        hyperparams = job.get("hyperparams")
        if isinstance(hyperparams, str):
            with contextlib.suppress(ValueError):
                hyperparams = json.loads(hyperparams)
        return {
            "api_key": api_key,
            "tenant_id": tenant_id,
            "coco_r2_key": str(job["coco_r2_key"]),
            "framework": str(job.get("framework") or "rfdetr"),
            "base_model": job.get("base_model"),
            "hyperparams": hyperparams if isinstance(hyperparams, dict) else {},
        }
    except Exception as exc:
        logger.warning("runpod_context_lookup_failed: job=%s err=%s", job_id, exc)
        return None


def _read_remote_train_source() -> str:
    """Lê o runner self-contained embarcado no onstart (heredoc).

    O pod RunPod NÃO tem acesso ao repositório — o script inteiro é
    embutido no onstart em vez de baixado. Caminho preservado
    (`training/vast/remote_train.py`) — o executor é agnóstico de provedor
    GPU, só o nome do diretório é histórico (decisão do dono: não mover
    pra reduzir escopo/risco da troca Vast→RunPod).
    """
    from app.infrastructure.queue.tasks.repo_files import find_repo_file  # noqa: PLC0415

    return find_repo_file("training", "vast", "remote_train.py").read_text(
        encoding="utf-8"
    )


def _run_runpod_train_job(
    ctx: dict[str, Any],
    job_id: str,
    model_size: str,
    epochs: int,
    imgsz: int,
    batch: int,
    update_fn,
) -> dict:
    """Fluxo REST real RunPod: presigned URLs + `run_runpod_job` (runner
    genérico — preço/teto/onstart/create/watch/terminate/billing, ver
    `infrastructure/gpu/runpod_runner.py`) com a carga 'train'.

    O pod é SEMPRE terminado (garantido dentro de `run_runpod_job`, camada 2
    de garantia de morte) — nunca vaza GPU paga. callback_token é revogado
    (NULL) ao final, sucesso ou erro.
    """
    pool = DatabasePool.get_instance()
    repo = TrainingRepository(pool)

    tenant_id = ctx.get("tenant_id") or "unknown"
    framework = ctx.get("framework") or (
        "yolox" if "yolox" in model_size.lower() else "rfdetr"
    )

    # Token por-job (ajuste C-1 da crítica original Vast — ainda válido):
    # aleatório, revogável no stop.
    callback_token = secrets.token_urlsafe(48)
    repo._execute_mutation_no_return(
        "UPDATE training_jobs SET callback_token = %s, gpu_provider = 'runpod' "
        "WHERE id = %s",
        (callback_token, job_id),
    )

    storage = get_storage(tenant_id)
    zip_key = f"{ctx['coco_r2_key']}/dataset.zip"
    storage.upload_bytes(
        zip_key, _build_training_dataset_zip(storage, ctx["coco_r2_key"]),
        "application/zip",
    )
    dataset_url = storage.generate_presigned_download_url(
        zip_key, ttl=_PRESIGNED_GET_TTL
    )
    r2_onnx_key = runpod_onnx_artifact_key(tenant_id, job_id)
    artifact_prefix = f"models/{tenant_id}/runpod/{job_id}"
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

    client = RunPodClient(ctx["api_key"])

    # Recheca status ANTES de provisionar: fecha a janela de corrida em que
    # um stop concorrente (entre o início do dispatch e este ponto) seria
    # ignorado e um pod GPU pago criado para um job já cancelado (achado da
    # revisão adversarial original Vast — ainda válido).
    current = repo._execute_one(
        "SELECT status FROM training_jobs WHERE id = %s", (job_id,)
    )
    if (current or {}).get("status") == "stopped":
        raise JobStoppedError(
            f"Job {job_id} foi parado antes do provisioning — abortando sem criar pod"
        )

    def _poll_status() -> dict[str, Any]:
        job = repo._execute_one(
            "SELECT status, metrics FROM training_jobs WHERE id = %s", (job_id,)
        )
        raw_metrics = (job or {}).get("metrics") or {}
        if isinstance(raw_metrics, str):
            with contextlib.suppress(ValueError):
                raw_metrics = json.loads(raw_metrics)
        return {
            "status": (job or {}).get("status"),
            "metrics": raw_metrics if isinstance(raw_metrics, dict) else {},
        }

    def _persist_instance_ref(pod_id: str) -> None:
        repo._execute_mutation_no_return(
            "UPDATE training_jobs SET gpu_instance_ref = %s WHERE id = %s",
            (pod_id, job_id),
        )
        # Mesmo checkpoint de progresso que o fluxo Vast tinha logo após a
        # instância existir (pod criado, watchdog prestes a começar).
        update_fn("running", progress=5)

    def _verify_completed(_state: dict[str, Any]) -> bool:
        return verify_model_artifact(tenant_id, r2_onnx_key)

    update_fn("running", progress=2)
    try:
        result = run_runpod_job(
            kind=JobKind.TRAIN,
            job_id=job_id,
            client=client,
            executor_source=_read_remote_train_source(),
            executor_filename="remote_train.py",
            env=remote_env,
            poll_status_fn=_poll_status,
            persist_instance_ref_fn=_persist_instance_ref,
            verify_completed_fn=_verify_completed,
        )
        return {
            "model_path": r2_onnx_key,
            "metrics": result["metrics"],
            "source": "runpod",
        }
    finally:
        # SEMPRE: revogar o token (o pod já foi terminado dentro de
        # run_runpod_job — camada 2 de garantia de morte).
        with contextlib.suppress(Exception):
            repo._execute_mutation_no_return(
                "UPDATE training_jobs SET callback_token = NULL WHERE id = %s",
                (job_id,),
            )


def _dispatch_runpod_train(
    job_id: str,
    model_size: str,
    epochs: int,
    imgsz: int,
    batch: int,
    update_fn,
    tenant_id: str | None = None,
) -> dict:
    """Dispara treinamento real no RunPod (WS-A4, substitui `_dispatch_vast_ai`).

    Fluxo REST real quando o contexto completo existe (API key do tenant ou
    env + dataset_version com COCO exportado): presigned GET/PUTs, pod com
    onstart embutindo remote_train.py, watchdog + terminate garantido — tudo
    via `_run_runpod_train_job`/`infrastructure/gpu/runpod_runner.py`.

    C5/ADR-0047 (task "treino honesto"): RunPod É GPU de terceiro — o fluxo
    REST real só dispara com o MESMO opt-in explícito
    (`training_third_party_cloud_enabled`) que já protegia Hub/legado/Vast.

    C1/ADR-0017 (task "treino honesto"): dataset ausente (sem coco_r2_key
    resolvível) é erro alto com mensagem clara — NUNCA desvia para dataset de
    outra origem.

    ADR-0044 (decisão do dono): valida a variante RF-DETR (base_model/
    hyperparams) contra o allowlist Apache 2.0 ANTES de qualquer chamada de
    rede — `assert_rfdetr_variant_allowed` levanta `RfdetrLicenseError`
    (subclasse de `ValueError`, capturada como falha genérica por
    `dispatch_training`) pra qualquer variante XL/2XL (PML, não Apache).
    """
    if not _third_party_cloud_training_enabled(tenant_id):
        raise RuntimeError(
            "Treino em nuvem de terceiro desabilitado para este tenant "
            f"(training_third_party_cloud_enabled=false) — caminho=runpod "
            f"job={job_id}"
        )
    ctx = _get_runpod_training_context(job_id)
    if ctx is None:
        if not resolve_runpod_api_key(tenant_id):
            raise RuntimeError(
                f"Nenhuma chave RunPod resolvível para o tenant — job={job_id}"
            )
        raise RuntimeError(
            f"Job {job_id}: dataset sem exportação COCO (coco_r2_key ausente "
            "no dataset_version vinculado) — não é possível treinar no "
            "RunPod. Exporte o dataset (build_dataset_version) antes de "
            "disparar o treino."
        )
    assert_rfdetr_variant_allowed(
        ctx["framework"], base_model=ctx.get("base_model"), hyperparams=ctx.get("hyperparams"),
    )
    return _run_runpod_train_job(
        ctx, job_id, model_size, epochs, imgsz, batch, update_fn
    )


def runpod_onnx_artifact_key(tenant_id: str | None, job_id: str) -> str:
    """Chave R2 determinística do ONNX de um job RunPod.

    Mesma fórmula usada no dispatch (`_run_runpod_train_job`, que injeta
    esta chave como R2_ONNX_KEY/UPLOAD_URL_ONNX no pod remoto) e na
    reverificação pós-callback (`app/api/v1/training/job_handlers.py::
    training_progress_callback_handler`) — nunca duplicar como f-string solta
    em outro lugar (task "treino não pode mentir").
    """
    return f"models/{tenant_id}/runpod/{job_id}/model.onnx"
