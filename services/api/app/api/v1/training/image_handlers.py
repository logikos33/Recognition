"""
Recognition — Training Image handlers.

GET  /api/training/images                    → galeria paginada de frames (imagens de treino)
POST /api/training/images/upload              → upload multipart batch de imagens (WS-A2)
GET  /api/training/active-learning/queue      → fila priorizada por incerteza (WS-B2)
GET  /api/training/images/facets              → contagens p/ painel de curadoria (migration 110)
POST /api/training/frames/curation            → curadoria em lote (active/duvida/excluida)
"""
import io
import logging
from datetime import datetime
from uuid import UUID, uuid4

from flask import request

from app.constants import CurationStatus, FrameSource, R2Prefix
from app.core.auth import get_current_user_id, get_tenant_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import error, success
from app.infrastructure.database.connection import DatabasePool
from app.infrastructure.database.repositories.frame_repository import FrameRepository
from app.infrastructure.storage.local_storage import get_storage
from app.infrastructure.storage.r2_storage import R2Storage

logger = logging.getLogger(__name__)

# Mesmo padrão de upload de imagens de videos/routes.py (_MAX_IMAGE_BYTES)
_ALLOWED_IMAGE_EXTS: frozenset = frozenset({"jpg", "jpeg", "png", "webp"})
_MAX_IMAGES_PER_BATCH = 50
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_CURATION_BATCH = 500

_VALID_SOURCE_FILTERS = frozenset(s.value for s in FrameSource)
_VALID_STATUS_FILTERS = frozenset({"unlabeled", "labeled", "reviewed"})
_VALID_CURATION_STATUS = frozenset(s.value for s in CurationStatus)


def _get_frame_repo() -> FrameRepository:
    pool = DatabasePool.get_instance()
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return FrameRepository(pool)


def _parse_camera_ids() -> "list[str] | None":
    """Lê o filtro multi-câmera do seletor de treinamento.

    Aceita tanto `camera_ids` repetido (`?camera_ids=a&camera_ids=b`) quanto
    CSV num único param (`?camera_ids=a,b`) — mesmo espírito de
    `dashboard_edge/routes.py` (CSV) + `events/routes.py._safe_list`
    (repetido), combinados aqui porque o front pode fazer qualquer um dos
    dois via URLSearchParams. Vazio/ausente → None (sem filtro multi —
    caller cai para o `camera_id` singular, se houver).
    """
    raw = request.args.getlist("camera_ids")
    if not raw:
        return None
    ids = [part.strip() for item in raw for part in item.split(",") if part.strip()]
    return ids or None


def _parse_cursor() -> "tuple[str, str] | None":
    """Lê `before`/`before_id` — o (created_at, id) do último item já entregue.

    Os dois juntos ou nenhum: `before` sozinho pularia linha em empate de
    `created_at`, e `before_id` sozinho não diz nada. Formato de `before` é o
    ISO que o próprio endpoint devolve em `created_at` (o Postgres faz o cast).
    """
    before = (request.args.get("before") or "").strip()
    before_id = (request.args.get("before_id") or "").strip()
    if not before or not before_id:
        return None
    return (before, before_id)


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
      page             int  (default 1)
      page_size        int  (default 24, max 100)
      is_annotated     'true' | 'false' | omitido → todos
      order            'desc' | 'asc'  (default desc por created_at)
      source           'video' | 'upload' | 'auto' | 'nvr'  (WS-A2)
      status           'unlabeled' | 'labeled' | 'reviewed' (WS-A2, computado:
                       unlabeled = NOT is_annotated;
                       labeled   = is_annotated AND validated_at IS NULL;
                       reviewed  = validated_at IS NOT NULL)
      camera_id        UUID (migration 110 — curadoria)
      camera_ids       UUID(s) — multi-seleção do seletor de câmera do
                       treinamento (CSV num param ou repetido, ver
                       _parse_camera_ids). Quando presente tem PRIORIDADE
                       sobre camera_id (singular, mantido por compat).
      curation_status  'active' | 'duvida' | 'excluida' (migration 110).
                       Omitido → exclui 'excluida' por padrão; só aparece se
                       pedido explicitamente (curadoria nunca apaga frame).
      before           timestamp do último item já entregue (cursor keyset).
      before_id        UUID do último item já entregue. `before` e `before_id`
                       vêm SEMPRE juntos; presentes, `page` é ignorado e o
                       corte sai do WHERE em vez do OFFSET — a fila de
                       anotação encolhe enquanto é percorrida e o OFFSET
                       pulava metade do acervo em silêncio (ver `cursor` em
                       list_images_filtered).
      pending_review   'true' | 'false' | omitido (migration 111 — fila de
                       aprovação de propostas). 'true' filtra frames com
                       provenance='proposta' (sem frame_annotations, IA
                       ainda não revisada) E pre_annotation_review_status
                       IS NULL — proposta rejeitada some da fila (ver
                       AnnotationService.review_pre_annotation).

    Compat: sem source/status/camera_id/curation_status/pending_review o
    caminho legado (user-scoped via training_videos) é mantido byte a byte. Caminho
    tenant-scoped (default) tem cada frame com campos extras: source,
    r2_key, width, height, status, camera_id, curation_status, provenance,
    annotation_count.
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
        camera_id = request.args.get("camera_id")
        camera_ids = _parse_camera_ids()
        curation_status = request.args.get("curation_status")
        pending_review = request.args.get("pending_review", "").strip().lower() in (
            "1", "true", "yes",
        )
        # Fila da aba Classificar: só recorte de pessoa, nunca frame inteiro
        # (ver only_crops em FrameRepository.list_images_filtered).
        only_crops = request.args.get("only_crops", "").strip().lower() in (
            "1", "true", "yes",
        )
        # Cursor (keyset) da fila de classificação: `before`/`before_id` são o
        # (created_at, id) do ÚLTIMO item do lote anterior, na ordem do
        # servidor. Quando presentes, `page` é ignorado — ver o bloco `cursor`
        # em FrameRepository.list_images_filtered para o porquê (OFFSET sobre
        # conjunto que encolhe pulava metade do acervo em silêncio).
        cursor = _parse_cursor()
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
        if curation_status is not None and curation_status not in _VALID_CURATION_STATUS:
            return error(
                f"curation_status inválido: {curation_status!r} "
                f"(esperado: {sorted(_VALID_CURATION_STATUS)})",
                400,
            )
        if camera_id is not None:
            try:
                UUID(camera_id)
            except ValueError:
                return error("camera_id inválido (esperado UUID)", 400)
        if camera_ids is not None:
            for cid in camera_ids:
                try:
                    UUID(cid)
                except ValueError:
                    return error(f"camera_ids inválido (esperado UUID): {cid!r}", 400)
        if cursor is not None:
            try:
                UUID(cursor[1])
            except ValueError:
                return error("before_id inválido (esperado UUID)", 400)
            try:
                datetime.fromisoformat(cursor[0])
            except ValueError:
                return error(
                    "before inválido (esperado timestamp ISO-8601)", 400
                )

        repo = _get_frame_repo()

        # Default é o caminho tenant-scoped (era o legado user-scoped).
        #
        # O legado filtra por `tv.user_id` via INNER JOIN em training_videos, o
        # que causava DOIS problemas num pool de anotação de equipe:
        #   1. frame sem vídeo pai (source nvr/upload/auto tem video_id NULL
        #      desde a migration 094) era eliminado pelo JOIN — SEMPRE. Todo
        #      frame coletado do NVR era invisível na galeria, sem erro nenhum;
        #   2. frame de outro usuário do mesmo tenant ficava escondido, mesmo o
        #      pool sendo compartilhado pela equipe.
        #
        # Shape do retorno é o mesmo; list_images_filtered só ACRESCENTA campos
        # (source, r2_key, width, height, status, camera_id, curation_status).
        # C-01 preservado: escopo por tenant do JWT.
        #
        # `?legacy=1` mantém o caminho antigo pra quem depender do recorte por
        # usuário — sem isso não haveria como voltar atrás sem deploy. Filtros
        # de curadoria não existem no legado (camera_id/curation_status são
        # ignorados nesse ramo).
        use_legacy = request.args.get("legacy", "").strip().lower() in ("1", "true", "yes")

        if use_legacy:
            result = repo.get_by_user_paginated(
                user_id=UUID(str(user_id)),
                page=page,
                page_size=page_size,
                is_annotated=is_annotated,
                order=order,
            )
        else:
            result = repo.list_images_filtered(
                tenant_id=get_tenant_id(),
                page=page,
                page_size=page_size,
                source=source,
                status=status,
                is_annotated=is_annotated,
                order=order,
                camera_id=camera_id,
                camera_ids=camera_ids,
                curation_status=curation_status,
                pending_review=pending_review or None,
                only_crops=only_crops or None,
                cursor=cursor,
            )

        # Serialise UUIDs (video_id/camera_id podem ser NULL)
        for frame in result.get("frames", []):
            frame["id"] = str(frame["id"])
            frame["video_id"] = (
                str(frame["video_id"]) if frame.get("video_id") else None
            )
            frame["camera_id"] = (
                str(frame["camera_id"]) if frame.get("camera_id") else None
            )

        # Presigned URL para o browser carregar a miniatura direto do R2 —
        # a tag <img> não envia Authorization, então o endpoint autenticado
        # de bytes (/api/training/frames/<id>/image) sempre 401 nela.
        # Mesmo padrão de get_video_frames_handler (video_handlers.py).
        storage = get_storage()
        if isinstance(storage, R2Storage):
            for frame in result.get("frames", []):
                try:
                    frame["url"] = storage.generate_presigned_download_url(
                        frame["filename"], ttl=3600, response_content_type="image/jpeg"
                    )
                except Exception as url_exc:  # noqa: BLE001
                    logger.warning(
                        "presigned_url_failed frame=%s: %s", frame.get("id"), url_exc
                    )
                    frame["url"] = None

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
    tenant_id do JWT. Upload SEMPRE antes do INSERT — nunca cria linha no
    banco apontando para objeto que não chegou a existir no R2; se o INSERT
    falhar depois do upload ter sucedido, o objeto órfão é removido
    (best-effort).

    Resposta:
      - Todos os arquivos falharam → 400 (nada persistido).
      - Falha parcial → 207, com `failed_files: [{filename, reason}]`
        explícito (o front não pode confundir com sucesso total).
      - Todos os arquivos válidos → 201 (comportamento original).

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
        failed_files: list[dict] = []

        for i, file in enumerate(files):
            fname = file.filename or f"arquivo_{i}"
            ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
            if ext not in _ALLOWED_IMAGE_EXTS:
                failed_files.append({"filename": fname, "reason": "extensão não suportada"})
                continue

            data = file.read()
            if not data:
                failed_files.append({"filename": fname, "reason": "arquivo vazio"})
                continue
            if len(data) > _MAX_IMAGE_BYTES:
                failed_files.append({
                    "filename": fname,
                    "reason": "arquivo excede o tamanho máximo permitido",
                })
                continue

            dimensions = _image_dimensions(data)
            if dimensions is None:
                failed_files.append({
                    "filename": fname,
                    "reason": "bytes não formam uma imagem válida",
                })
                continue
            width, height = dimensions

            r2_key = f"{R2Prefix.TRAINING_IMAGES}/{tenant_id}/upload/{uuid4()}.{ext}"
            content_type = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

            # Upload PRIMEIRO: só faz INSERT se o objeto já existe no R2 —
            # nunca o inverso. Uma linha em training_frames sem objeto
            # correspondente é dado mentindo (galeria mostra frame que não
            # pode ser aberto).
            try:
                storage.upload_bytes(r2_key, data, content_type)
            except Exception as exc:
                logger.error(
                    "upload_training_image_storage_error: i=%d file=%s err=%s",
                    i, fname, exc, exc_info=True,
                )
                failed_files.append({
                    "filename": fname,
                    "reason": "falha ao enviar para o armazenamento",
                })
                continue

            try:
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
                logger.error(
                    "upload_training_image_db_error: i=%d file=%s r2_key=%s err=%s",
                    i, fname, r2_key, exc, exc_info=True,
                )
                # Objeto já subiu mas o INSERT falhou — remove o órfão do R2
                # (best-effort: falha de limpeza não é grave, já que sem
                # linha no banco não há frame fantasma pro front mostrar).
                try:
                    storage.delete(r2_key)
                except Exception as cleanup_exc:  # noqa: BLE001
                    logger.warning(
                        "upload_training_image_cleanup_failed: r2_key=%s err=%s",
                        r2_key, cleanup_exc,
                    )
                failed_files.append({
                    "filename": fname,
                    "reason": "falha ao registrar no banco",
                })
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
            logger.error(
                "upload_training_images_all_failed: tenant=%s batch=%d failures=%s",
                tenant_id, len(files), failed_files,
            )
            return error(
                "Nenhuma imagem foi salva — todos os arquivos do lote falharam",
                400,
            )

        # 207 (Multi-Status) quando há falha parcial: 201 sinalizaria sucesso
        # total, e o front não pode confundir "5 de 8 subiram" com "8 de 8".
        status_code = 201 if not failed_files else 207
        logger.info(
            "upload_training_images_done: tenant=%s uploaded=%d failed=%d status=%d",
            tenant_id,
            len(images),
            len(failed_files),
            status_code,
        )
        return success(
            {
                "uploaded": len(images),
                "failed": len(failed_files),
                "failed_files": failed_files,
                "images": images,
            },
            status=status_code,
        )

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("upload_training_images_error: %s", exc, exc_info=True)
        return error("Erro ao processar imagens", 500)


def active_learning_queue_handler():
    """Fila de active learning (WS-B2, ADR-0031): frames não rotulados
    priorizados por incerteza (model_confidence ASC — quanto menos confiante
    a detecção ao vivo que gerou o frame, maior a prioridade de rotulagem).

    Query params:
      module   str  (default 'epi')
      limit    int  (default 20, max 100)
    """
    try:
        tenant_id = get_tenant_id()
        module_code = request.args.get("module", "epi")
        limit = min(100, max(1, request.args.get("limit", 20, type=int)))

        repo = _get_frame_repo()
        frames = repo.list_unlabeled_by_uncertainty(tenant_id, module_code, limit)

        for frame in frames:
            frame["id"] = str(frame["id"])
            frame["video_id"] = str(frame["video_id"]) if frame.get("video_id") else None
            frame["camera_id"] = str(frame["camera_id"]) if frame.get("camera_id") else None

        return success({"frames": frames, "total": len(frames), "module": module_code})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("active_learning_queue_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def get_image_facets_handler():
    """Contagens por câmera e por status para o painel de curadoria (migration 110).

    Query params (mesmos filtros da galeria, todos opcionais — cada faceta
    respeita os filtros das OUTRAS dimensões, nunca o da própria, ver
    FrameRepository.get_facets):
      source            'video' | 'upload' | 'auto' | 'nvr'
      camera_id         UUID
      camera_ids        UUID(s) — multi-seleção (CSV ou repetido, ver
                        _parse_camera_ids); prioridade sobre camera_id.
      curation_status   'active' | 'duvida' | 'excluida'

    Resposta: {"cameras": [{"camera_id", "camera_name", "count"}, ...],
               "status": {"nao_anotado", "anotado", "duvida", "excluida"}}
    """
    try:
        tenant_id = get_tenant_id()

        source = request.args.get("source")
        camera_id = request.args.get("camera_id")
        camera_ids = _parse_camera_ids()
        curation_status = request.args.get("curation_status")
        if source is not None and source not in _VALID_SOURCE_FILTERS:
            return error(
                f"source inválido: {source!r} "
                f"(esperado: {sorted(_VALID_SOURCE_FILTERS)})",
                400,
            )
        if curation_status is not None and curation_status not in _VALID_CURATION_STATUS:
            return error(
                f"curation_status inválido: {curation_status!r} "
                f"(esperado: {sorted(_VALID_CURATION_STATUS)})",
                400,
            )
        if camera_id is not None:
            try:
                UUID(camera_id)
            except ValueError:
                return error("camera_id inválido (esperado UUID)", 400)
        if camera_ids is not None:
            for cid in camera_ids:
                try:
                    UUID(cid)
                except ValueError:
                    return error(f"camera_ids inválido (esperado UUID): {cid!r}", 400)

        repo = _get_frame_repo()
        facets = repo.get_facets(
            tenant_id=tenant_id,
            source=source,
            camera_id=camera_id,
            camera_ids=camera_ids,
            curation_status=curation_status,
        )
        return success(facets)
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("get_image_facets_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)


def curate_frames_handler():
    """Curadoria em lote (migration 110): marca frames como active/duvida/excluida.

    Body: {"frame_ids": ["<uuid>", ...], "status": "active"|"duvida"|"excluida"}

    Escopo por tenant do JWT (get_tenant_id()) — ids de outro tenant são
    silenciosamente ignorados (não entram no `updated`, sem 404/403 — C-01,
    evita vazar existência de frame de outro tenant). Nunca deleta a linha:
    curadoria é só um campo de estado (⛔ nunca apagar caixas).
    """
    try:
        tenant_id = get_tenant_id()
        user_id = get_current_user_id()
        data = request.get_json() or {}

        frame_ids = data.get("frame_ids")
        status = data.get("status")

        if not isinstance(frame_ids, list) or not frame_ids:
            return error("frame_ids deve ser uma lista não vazia de UUIDs", 400)
        if len(frame_ids) > _MAX_CURATION_BATCH:
            return error(
                f"Máximo de {_MAX_CURATION_BATCH} frames por lote de curadoria", 400
            )
        if status not in _VALID_CURATION_STATUS:
            return error(
                f"status inválido: {status!r} "
                f"(esperado: {sorted(_VALID_CURATION_STATUS)})",
                400,
            )

        clean_ids: list[UUID] = []
        for fid in frame_ids:
            try:
                clean_ids.append(UUID(str(fid)))
            except (ValueError, AttributeError, TypeError):
                return error(f"frame_id inválido (esperado UUID): {fid!r}", 400)

        repo = _get_frame_repo()
        updated = repo.update_curation_status(
            frame_ids=clean_ids,
            status=status,
            tenant_id=tenant_id,
            updated_by=user_id,
        )
        logger.info(
            "frames_curated: tenant=%s status=%s requested=%d updated=%d",
            tenant_id, status, len(clean_ids), updated,
        )
        return success({"updated": updated})
    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("curate_frames_error: %s", exc, exc_info=True)
        return error("Erro interno", 500)
