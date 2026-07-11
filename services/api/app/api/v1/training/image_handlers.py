"""
Recognition — Training Image handlers.

GET  /api/training/images         → galeria paginada de frames (imagens de treino)
POST /api/training/images/upload  → upload multipart batch de imagens (WS-A2)
"""
import io
import logging
from uuid import UUID, uuid4

from flask import request

from app.constants import FrameSource, R2Prefix
from app.core.auth import get_current_user_id, get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.frame_repository import FrameRepository
from app.infrastructure.storage.local_storage import get_storage

logger = logging.getLogger(__name__)

# Mesmo padrão de upload de imagens de videos/routes.py (_MAX_IMAGE_BYTES)
_ALLOWED_IMAGE_EXTS: frozenset = frozenset({"jpg", "jpeg", "png", "webp"})
_MAX_IMAGES_PER_BATCH = 50
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB

_VALID_SOURCE_FILTERS = frozenset(s.value for s in FrameSource)
_VALID_STATUS_FILTERS = frozenset({"unlabeled", "labeled", "reviewed"})


def _get_frame_repo() -> FrameRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return FrameRepository(pool)


def _image_dimensions(data: bytes) -> "tuple[int, int] | None":
    """Extrai (width, height) via PIL. None se bytes não formam imagem válida."""
    try:
        from PIL import Image  # noqa: PLC0415 — lazy: PIL só é necessário no upload

        with Image.open(io.BytesIO(data)) as img:
            return int(img.size[0]), int(img.size[1])
    except Exception:
        return None


def list_training_images_handler():
    """Lista imagens de treino com paginação e filtros.

    Query params:
      page          int  (default 1)
      page_size     int  (default 24, max 100)
      is_annotated  'true' | 'false' | omitido → todos
      order         'desc' | 'asc'  (default desc por created_at)
      source        'video' | 'upload' | 'auto' | 'nvr'  (WS-A2)
      status        'unlabeled' | 'labeled' | 'reviewed' (WS-A2, computado:
                    unlabeled = NOT is_annotated;
                    labeled   = is_annotated AND validated_at IS NULL;
                    reviewed  = validated_at IS NOT NULL)

    Compat: sem source/status o caminho legado (user-scoped via
    training_videos) é mantido byte a byte. Com source/status a listagem é
    tenant-scoped (frames de upload/auto não têm vídeo pai) e cada frame
    ganha campos extras: source, r2_key, width, height, status.
    """
    try:
        user_id = get_current_user_id()

        page = max(1, request.args.get("page", 1, type=int))
        page_size = min(100, max(1, request.args.get("page_size", 24, type=int)))
        order = request.args.get("order", "desc")
        if order not in ("asc", "desc"):
            order = "desc"

        is_annotated_param = request.args.get("is_annotated")
        is_annotated: bool | None = None
        if is_annotated_param == "true":
            is_annotated = True
        elif is_annotated_param == "false":
            is_annotated = False

        source = request.args.get("source")
        status = request.args.get("status")
        if source is not None and source not in _VALID_SOURCE_FILTERS:
            return error(
                f"source inválido: {source!r} "
                f"(esperado: {sorted(_VALID_SOURCE_FILTERS)})",
                400,
            )
        if status is not None and status not in _VALID_STATUS_FILTERS:
            return error(
                f"status inválido: {status!r} "
                f"(esperado: {sorted(_VALID_STATUS_FILTERS)})",
                400,
            )

        repo = _get_frame_repo()

        if source is not None or status is not None:
            # Caminho novo (WS-A2): tenant-scoped, LEFT JOIN, status computado
            result = repo.list_images_filtered(
                tenant_id=get_tenant_id(),
                page=page,
                page_size=page_size,
                source=source,
                status=status,
                is_annotated=is_annotated,
                order=order,
            )
        else:
            # Caminho legado — mantém compat total do retorno atual
            result = repo.get_by_user_paginated(
                user_id=UUID(str(user_id)),
                page=page,
                page_size=page_size,
                is_annotated=is_annotated,
                order=order,
            )

        # Serialise UUIDs (video_id pode ser NULL desde a migration 094)
        for frame in result.get("frames", []):
            frame["id"] = str(frame["id"])
            frame["video_id"] = (
                str(frame["video_id"]) if frame.get("video_id") else None
            )

        return success(result)

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("list_training_images_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def upload_training_images_handler():
    """Upload multipart batch de imagens de treino (WS-A2).

    Campo multipart: files (aceita também files[]). Opcional: module_code.
    Validações: extensão (jpg/jpeg/png/webp), tamanho (≤10 MB), lote (≤50),
    bytes precisam decodificar como imagem (PIL — também extrai width/height).

    Cada imagem válida: upload R2 em
    training-images/{tenant_id}/upload/{uuid}.{ext} (R2Prefix.TRAINING_IMAGES)
    e INSERT em training_frames com source='upload', video_id=NULL,
    tenant_id do JWT.

    Gate de permissão (@require_training_role('write')) aplicado na rota —
    ver wiring em routes.py.
    """
    try:
        user_id = get_current_user_id()
        tenant_id = get_tenant_id()

        files = request.files.getlist("files") or request.files.getlist("files[]")
        if not files:
            return error("Campo 'files' obrigatório (multipart)", 400)
        if len(files) > _MAX_IMAGES_PER_BATCH:
            return error(
                f"Máximo de {_MAX_IMAGES_PER_BATCH} imagens por upload", 400
            )

        module_code = request.form.get("module_code") or None

        storage = get_storage()
        repo = _get_frame_repo()

        images: list[dict] = []
        failed = 0

        for i, file in enumerate(files):
            fname = file.filename or ""
            ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
            if ext not in _ALLOWED_IMAGE_EXTS:
                failed += 1
                continue

            data = file.read()
            if not data or len(data) > _MAX_IMAGE_BYTES:
                failed += 1
                continue

            dimensions = _image_dimensions(data)
            if dimensions is None:
                failed += 1
                continue
            width, height = dimensions

            r2_key = f"{R2Prefix.TRAINING_IMAGES}/{tenant_id}/upload/{uuid4()}.{ext}"
            content_type = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

            try:
                storage.upload_bytes(r2_key, data, content_type)
                frame = repo.create(
                    video_id=None,
                    frame_number=i,
                    filename=r2_key,
                    timestamp_seconds=None,
                    source=FrameSource.UPLOAD,
                    r2_key=r2_key,
                    width=width,
                    height=height,
                    tenant_id=tenant_id,
                    module_code=module_code,
                    user_id=user_id,
                )
            except Exception as exc:
                logger.warning(
                    "upload_training_image_error: i=%d err=%s", i, exc
                )
                failed += 1
                continue

            images.append({
                "id": str(frame["id"]),
                "r2_key": frame.get("r2_key") or r2_key,
                "filename": frame.get("filename") or r2_key,
                "source": str(frame.get("source") or FrameSource.UPLOAD),
                "width": frame.get("width"),
                "height": frame.get("height"),
                "module_code": frame.get("module_code"),
            })

        if not images:
            return error("Nenhuma imagem válida no lote", 400)

        logger.info(
            "upload_training_images_done: tenant=%s uploaded=%d failed=%d",
            tenant_id,
            len(images),
            failed,
        )
        return success(
            {"uploaded": len(images), "failed": failed, "images": images},
            status=201,
        )

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("upload_training_images_error: %s", exc, exc_info=True)
        return error("Erro ao processar imagens", 500)
