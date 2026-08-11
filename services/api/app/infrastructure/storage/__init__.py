"""
Recognition — Storage package helpers.

Task "treino não pode mentir": um único ponto de verdade pra confirmar que
um artefato de modelo existe DE FATO no storage (R2 ou local, conforme
`get_storage`) antes de qualquer caminho persistir um job de treino como
'completed' — ver app/infrastructure/queue/tasks/training.py e
app/api/v1/training/job_handlers.py.
"""
import logging

logger = logging.getLogger(__name__)


def verify_model_artifact(tenant_id: str | None, r2_key: str | None) -> bool:
    """Confirma via HEAD/exists real que um artefato de modelo existe no
    storage do tenant.

    Fail closed: `r2_key` ausente, objeto ausente OU qualquer erro ao
    verificar (credencial inválida, storage fora do ar) => False. Quem chama
    NUNCA deve marcar um job de treino como sucesso sem um True explícito
    daqui — "completed" só é honesto quando o artefato é confirmável, nunca
    quando o provider/callback apenas *diz* que produziu um.
    """
    if not r2_key:
        logger.warning("verify_model_artifact_no_key: tenant=%s", tenant_id)
        return False
    try:
        from app.infrastructure.storage.local_storage import get_storage  # noqa: PLC0415

        storage = get_storage(tenant_id)
        exists = storage.exists(r2_key)
        if not exists:
            logger.warning(
                "verify_model_artifact_missing: tenant=%s key=%s", tenant_id, r2_key
            )
        return exists
    except Exception as exc:  # noqa: BLE001 — qualquer falha de storage = não verificado
        logger.warning(
            "verify_model_artifact_failed: tenant=%s key=%s err=%s",
            tenant_id, r2_key, exc,
        )
        return False
