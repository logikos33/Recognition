"""
Recognition — Demo Video Service.

Gerencia upload, listagem e exclusão de vídeos demo para modo demonstração.
ISOLAMENTO CRÍTICO: get_for_camera() retorna None para qualquer role != superadmin.
Clientes nunca veem vídeos demo no lugar do feed real.
"""
import logging
import uuid
from typing import Any

from app.constants import R2Prefix
from app.core.exceptions import AuthorizationError, ValidationError
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.demo_video_repository import DemoVideoRepository
from app.infrastructure.storage.local_storage import get_storage

logger = logging.getLogger(__name__)

# Tamanho máximo de upload: 100 MB
_MAX_FILE_SIZE = 100 * 1024 * 1024
_ALLOWED_MIME = {"video/mp4"}


def _get_repo() -> DemoVideoRepository:
    """Retorna instância do repository com pool singleton."""
    pool = DatabasePool.get_instance()
    return DemoVideoRepository(pool)


def upload(
    file_data: bytes,
    content_type: str,
    module: str,
    user_role: str,
    user_id: str | None = None,
    camera_id: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """
    Faz upload de um vídeo demo no R2 e registra no banco.

    Restrições de segurança:
    - Apenas superadmin pode fazer upload (lança AuthorizationError caso contrário)
    - Aceita apenas video/mp4, máximo 100 MB
    """
    # Isolamento: somente superadmin pode fazer upload de vídeos demo
    if user_role != "superadmin":
        raise AuthorizationError("Upload de vídeo demo restrito a superadmin")

    # Validação de MIME type
    if content_type not in _ALLOWED_MIME:
        raise ValidationError(f"Tipo de arquivo não permitido: {content_type}. Use video/mp4.")

    # Validação de tamanho
    file_size = len(file_data)
    if file_size > _MAX_FILE_SIZE:
        raise ValidationError(
            f"Arquivo muito grande: {file_size / 1024 / 1024:.1f}MB (máximo 100MB)"
        )

    # Gera chave única no R2 com prefixo do módulo
    r2_key = f"{R2Prefix.DEMO_VIDEOS}/{module}/{uuid.uuid4()}.mp4"

    # Upload para R2 (ou LocalStorage em dev)
    storage = get_storage()
    storage.upload_bytes(r2_key, file_data, content_type)

    # Gera URL de download (presigned ou pública dependendo do storage)
    r2_url = storage.generate_presigned_download_url(r2_key, ttl=365 * 24 * 3600)

    # Persiste no banco
    repo = _get_repo()
    record = repo.create(
        module=module,
        r2_key=r2_key,
        r2_url=r2_url,
        camera_id=camera_id,
        label=label,
        file_size_bytes=file_size,
        uploaded_by=user_id,
    )

    logger.info(
        "demo_video_uploaded: id=%s module=%s camera_id=%s size=%d",
        record["id"] if record else None, module, camera_id, file_size,
    )
    return record  # type: ignore[return-value]


def list_videos(
    module: str | None = None,
    camera_id: str | None = None,
) -> list[dict[str, Any]]:
    """Lista vídeos demo ativos. Requer verificação de role no handler (superadmin)."""
    repo = _get_repo()
    return repo.list_active(module=module, camera_id=camera_id)


def get_for_camera(camera_id: str, user_role: str, module: str | None = None) -> dict[str, Any] | None:
    """
    Retorna vídeo demo ativo para uma câmera, OU None.

    ISOLAMENTO CRÍTICO: sempre retorna None se o role não for superadmin.
    Desta forma, mesmo que exista um vídeo demo no banco, clientes jamais o recebem.
    """
    if user_role != "superadmin":
        return None

    repo = _get_repo()
    record = repo.get_for_camera(camera_id, module=module)
    if record is None:
        return None

    # Gerar URL fresca a cada requisição usando o r2_key salvo.
    # Evita 503 por URLs presignadas stale ou com credenciais desatualizadas.
    try:
        storage = get_storage()
        record = dict(record)
        record["r2_url"] = storage.generate_presigned_download_url(
            record["r2_key"], ttl=3600
        )
    except Exception as exc:
        logger.warning("demo_video: could not refresh presigned URL for key=%s: %s", record.get("r2_key"), exc)

    return record


def delete(video_id: int, user_role: str) -> bool:
    """Soft-delete de um vídeo demo. Apenas superadmin pode excluir."""
    if user_role != "superadmin":
        raise AuthorizationError("Exclusão de vídeo demo restrita a superadmin")

    repo = _get_repo()
    deleted = repo.soft_delete(video_id)
    if deleted:
        logger.info("demo_video_deleted: id=%d", video_id)
    return deleted
