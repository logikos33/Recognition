"""
Recognition — Dataset Versioning v2 (COCO export, WS-A3).

build_dataset_version_v2: snapshot de frames rotulados do tenant (reviewed
primeiro), split por grupo — video_id quando existe; senão camera_id+dia
de captura (frames soltos de NVR, sem video_id — evita leakage entre
train/val/test quando frames quase-idênticos da mesma câmera no mesmo dia
cairiam em splits diferentes); 'frame:{id}' só como último recurso quando
nem video_id nem camera_id+data são resolvíveis (log de aviso — não
deveria acontecer com o schema atual). Conversão de anotações YOLO
normalizadas (cx/cy/w/h 0..1) para COCO absoluto via width/height do
frame (fallback: baixa a imagem do R2 e lê dimensões com PIL —
ThreadPoolExecutor(10), ajuste #11), upload para R2 em
{R2Prefix.DATASET_EXPORTS}/{tenant_id}/{dataset_id}/{version}/... e
INSERT em dataset_versions via DatasetRepository.create_version_v2 com
linhagem completa (status building→ready|error).

Corrige os bugs da task legada (versioning.py): key mismatch no copy e
ausência de INSERT. A task legada permanece para compat; esta é a oficial.
"""
import json
import logging
import random
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Any

from app.constants import DatasetVersionStatus, ExportFormat, R2Prefix
from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

_DIM_FALLBACK_WORKERS = 10
_SPLIT_NAMES = ("train", "val", "test")
_COCO_FILENAME = "_annotations.coco.json"


def _get_dataset_repo():
    from app.infrastructure.database.connection import DatabasePool
    from app.infrastructure.database.repositories.dataset_repository import (
        DatasetRepository,
    )
    return DatasetRepository(DatabasePool.get_instance())


def _get_annotation_repo():
    from app.infrastructure.database.connection import DatabasePool
    from app.infrastructure.database.repositories.annotation_repository import (
        AnnotationRepository,
    )
    return AnnotationRepository(DatabasePool.get_instance())


def _get_storage(tenant_id: str | None = None):
    from app.infrastructure.storage.local_storage import get_storage
    return get_storage(tenant_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snapshot_labeled_frames(
    annotation_repo, tenant_id: str, module_code: str
) -> list[dict[str, Any]]:
    """Snapshot de frames rotulados do tenant+módulo, reviewed primeiro.

    AI_NOTE (ajuste #4): LEFT JOIN training_videos — frames com video_id
    NULL (upload/auto/nvr) ENTRAM no snapshot; INNER JOIN os excluiria.

    camera_id + captured_at (fallback created_at) incluídos para o split
    por câmera/dia de frames soltos de NVR (video_id NULL) — ver
    _group_key.
    """
    return annotation_repo._execute(
        """
        SELECT tf.id, tf.video_id, tf.filename, tf.r2_key, tf.frame_number,
               tf.width, tf.height, tf.module_code, tf.camera_id,
               tf.captured_at, tf.created_at,
               (tf.validated_at IS NOT NULL) AS is_reviewed
          FROM training_frames tf
          LEFT JOIN training_videos tv ON tv.id = tf.video_id
         WHERE tf.tenant_id = %s
           AND tf.module_code = %s
           AND tf.is_annotated = TRUE
         ORDER BY (tf.validated_at IS NOT NULL) DESC,
                  tf.video_id, tf.frame_number
        """,
        (str(tenant_id), module_code),
    )


def _fetch_annotations(
    annotation_repo, tenant_id: str, module_code: str
) -> list[dict[str, Any]]:
    """Anotações YOLO (normalizadas) dos frames rotulados do tenant+módulo.

    Gate de procedência (D-39, migration 095): dataset de treino só recebe
    anotação HUMANA — direta (source='manual', default histórico da coluna;
    nenhum dado existente some) ou pré-anotação de IA APROVADA por humano
    (reviewed_by setado em accept_pre_annotations no aceite, ~annotation_
    repository.py linha 296). Uma pré-anotação sem revisão (reviewed_by
    NULL) nunca alimenta o treino.
    """
    rows = annotation_repo._execute(
        """
        SELECT a.frame_id, a.class_id, a.x_center, a.y_center,
               a.width, a.height, c.name AS class_name,
               a.source, a.reviewed_by
          FROM frame_annotations a
          JOIN yolo_classes c ON c.id = a.class_id
          JOIN training_frames tf ON tf.id = a.frame_id
         WHERE tf.tenant_id = %s
           AND tf.module_code = %s
           AND tf.is_annotated = TRUE
         ORDER BY a.frame_id, a.id
        """,
        (str(tenant_id), module_code),
    )
    return [
        row for row in rows
        if row.get("source", "manual") == "manual" or row.get("reviewed_by") is not None
    ]


def _frame_day(frame: dict[str, Any]) -> str | None:
    """Data (YYYY-MM-DD) de captura do frame: captured_at, fallback created_at.

    captured_at (TIMESTAMPTZ) é a data real de gravação NVR; created_at
    (TIMESTAMP, sempre presente — NOT NULL no schema) é quando o frame foi
    extraído/ingerido, usado só quando captured_at não veio preenchido.
    Aceita datetime (psycopg2/RealDictCursor) ou str (testes/defensivo).
    """
    value = frame.get("captured_at") or frame.get("created_at")
    if value is None:
        return None
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value)[:10] or None


def _group_key(frame: dict[str, Any]) -> str:
    """Grupo de split — sem leakage entre train/val/test.

    Prioridade: video_id (vídeo inteiro em um único split) > camera_id +
    dia de captura (frames soltos de NVR — mesma câmera no mesmo dia tende
    a ter frames quase-idênticos; separar entre splits vazaria informação)
    > 'frame:{id}' como último recurso, quando não há video_id nem
    camera_id+data resolvíveis — não deveria acontecer com o schema atual
    (training_frames sempre tem camera_id ou video_id), mas não pode
    quebrar o build; loga aviso porque o split volta a ser efetivamente
    por imagem para esse frame.
    """
    if frame.get("video_id"):
        return str(frame["video_id"])

    camera_id = frame.get("camera_id")
    day = _frame_day(frame)
    if camera_id and day:
        return f"cam:{camera_id}:{day}"

    logger.warning(
        "split_group_key_fallback_frame_id: frame_id=%s sem video_id nem "
        "camera_id+data resolvíveis — split por imagem individual (risco "
        "de leakage entre splits para este frame)",
        frame.get("id"),
    )
    return f"frame:{frame['id']}"


def _split_by_group(
    frames: list[dict[str, Any]], split: dict[str, float]
) -> dict[str, list[dict[str, Any]]]:
    """Split por grupo (sem leakage: frames do mesmo vídeo no mesmo split)."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for frame in frames:
        groups.setdefault(_group_key(frame), []).append(frame)

    group_keys = list(groups.keys())
    random.shuffle(group_keys)  # noqa: S311 — split de dataset, não cripto

    n = len(group_keys)
    n_train = max(1, int(n * split.get("train", 0.7)))
    n_val = int(n * split.get("val", 0.2))
    train_keys = set(group_keys[:n_train])
    val_keys = set(group_keys[n_train:n_train + n_val])

    splits: dict[str, list[dict[str, Any]]] = {s: [] for s in _SPLIT_NAMES}
    for key, group_frames in groups.items():
        if key in train_keys:
            splits["train"].extend(group_frames)
        elif key in val_keys:
            splits["val"].extend(group_frames)
        else:
            splits["test"].extend(group_frames)

    # Fallbacks: garantir val/test não-vazios quando há frames suficientes
    if not splits["val"] and len(splits["train"]) > 1:
        cut = max(1, len(splits["train"]) // 5)
        splits["val"] = splits["train"][-cut:]
        splits["train"] = splits["train"][:-cut]
    if not splits["test"] and len(splits["val"]) > 1:
        splits["test"] = splits["val"][-1:]
        splits["val"] = splits["val"][:-1]
    return splits


def _resolve_dimensions(
    frames: list[dict[str, Any]], storage
) -> tuple[list[dict[str, Any]], list[str]]:
    """Preenche width/height ausentes lendo a imagem do R2 com PIL.

    AI_NOTE (ajuste #11): fallback concorrente — ThreadPoolExecutor(10)
    para não serializar HTTP GETs no R2. Frames irresolvíveis são
    descartados (COCO exige dimensões absolutas).
    """
    missing = [f for f in frames if not f.get("width") or not f.get("height")]
    errors: list[str] = []
    if missing:
        from PIL import Image

        def _fetch(frame: dict[str, Any]) -> str | None:
            key = frame.get("r2_key") or frame.get("filename")
            try:
                data = storage.download_bytes(key)
                with Image.open(BytesIO(data)) as img:
                    frame["width"], frame["height"] = img.size
                return None
            except Exception as exc:  # noqa: BLE001
                return f"{frame['id']} ({key}): {exc}"

        with ThreadPoolExecutor(max_workers=_DIM_FALLBACK_WORKERS) as pool:
            for err in pool.map(_fetch, missing):
                if err:
                    errors.append(err)
                    logger.warning("dim_fallback_failed: %s", err)

    kept = [f for f in frames if f.get("width") and f.get("height")]
    return kept, errors


def _frame_ext(frame: dict[str, Any]) -> str:
    key = frame.get("r2_key") or frame.get("filename") or ""
    if "." in key.rsplit("/", 1)[-1]:
        return key.rsplit(".", 1)[-1]
    return "jpg"


def _yolo_to_coco_bbox(
    ann: dict[str, Any], width: int, height: int
) -> list[float]:
    """YOLO normalizado (cx, cy, w, h em 0..1) → COCO absoluto [x, y, w, h]."""
    w = float(ann["width"]) * width
    h = float(ann["height"]) * height
    x = float(ann["x_center"]) * width - w / 2
    y = float(ann["y_center"]) * height - h / 2
    return [round(x, 2), round(y, 2), round(w, 2), round(h, 2)]


def _build_coco_split(
    frames: list[dict[str, Any]],
    anns_by_frame: dict[str, list[dict[str, Any]]],
    categories: list[dict[str, Any]],
    cat_id_by_class: dict[int, int],
    version: str,
) -> dict[str, Any]:
    """Monta o JSON COCO de um split."""
    images: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    ann_id = 1
    for image_id, frame in enumerate(frames, start=1):
        images.append(
            {
                "id": image_id,
                "file_name": f"{frame['id']}.{_frame_ext(frame)}",
                "width": int(frame["width"]),
                "height": int(frame["height"]),
            }
        )
        for ann in anns_by_frame.get(str(frame["id"]), []):
            bbox = _yolo_to_coco_bbox(ann, int(frame["width"]), int(frame["height"]))
            annotations.append(
                {
                    "id": ann_id,
                    "image_id": image_id,
                    "category_id": cat_id_by_class[ann["class_id"]],
                    "bbox": bbox,
                    "area": round(bbox[2] * bbox[3], 2),
                    "iscrowd": 0,
                }
            )
            ann_id += 1
    return {
        "info": {"description": f"Recognition dataset {version}"},
        "licenses": [],
        "categories": categories,
        "images": images,
        "annotations": annotations,
    }


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@celery.task(
    bind=True, max_retries=2, queue="versioning",
    name="tasks.versioning_v2.build_dataset_version_v2",
)
def build_dataset_version_v2(
    self,
    tenant_id: str,
    dataset_id: str,
    user_id: str,
    version: str,
    split: dict[str, float] | None = None,
    augmentations: dict[str, Any] | None = None,
    export_format: str = ExportFormat.COCO.value,
    module_code: str = "epi",
) -> dict[str, Any]:
    """Build oficial de dataset_version com export COCO por split."""
    split = split or {"train": 0.7, "val": 0.2, "test": 0.1}
    version_id: str | None = None
    dataset_repo = _get_dataset_repo()

    try:
        logger.info(
            "build_dataset_v2_start: tenant=%s dataset=%s version=%s",
            tenant_id, dataset_id, version,
        )
        annotation_repo = _get_annotation_repo()
        storage = _get_storage(tenant_id)

        # 1. Snapshot de frames rotulados (reviewed primeiro)
        frames = _snapshot_labeled_frames(annotation_repo, tenant_id, module_code)
        if not frames:
            raise ValueError(
                "Nenhum frame rotulado encontrado para o tenant/módulo"
            )

        # 2. Anotações YOLO normalizadas por frame
        annotations = _fetch_annotations(annotation_repo, tenant_id, module_code)
        anns_by_frame: dict[str, list[dict[str, Any]]] = {}
        for ann in annotations:
            anns_by_frame.setdefault(str(ann["frame_id"]), []).append(ann)

        # 3. Dimensões absolutas (fallback R2+PIL concorrente)
        frames, dim_errors = _resolve_dimensions(frames, storage)
        if not frames:
            raise ValueError(
                "Nenhum frame com dimensões resolvíveis para export COCO"
            )

        # 4. Split por grupo (sem leakage)
        splits = _split_by_group(frames, split)

        # 5. Categorias e distribuição de classes
        seen: dict[int, str] = {}
        for ann in annotations:
            seen.setdefault(ann["class_id"], ann["class_name"])
        cat_id_by_class = {
            class_id: idx
            for idx, class_id in enumerate(sorted(seen), start=1)
        }
        categories = [
            {"id": cat_id_by_class[cid], "name": seen[cid], "supercategory": "none"}
            for cid in sorted(seen)
        ]
        kept_ids = {str(f["id"]) for f in frames}
        class_distribution: dict[str, int] = {}
        for ann in annotations:
            if str(ann["frame_id"]) in kept_ids:
                name = ann["class_name"]
                class_distribution[name] = class_distribution.get(name, 0) + 1

        # 6. INSERT com linhagem completa — status 'building' (ajuste #9)
        base_key = f"{R2Prefix.DATASET_EXPORTS}/{tenant_id}/{dataset_id}/{version}"
        # Reaproveita a row de um retry anterior (mesmo dataset_id+version+
        # tenant, status building/error) em vez de INSERTar de novo — sem
        # UNIQUE constraint no schema, cada retry do Celery criaria uma row
        # duplicada com o mesmo label, órfã da primeira tentativa.
        existing = dataset_repo.get_pending_version(dataset_id, tenant_id, version)
        if existing:
            version_id = str(existing["id"])
            row = dataset_repo.update_version_status(
                existing["id"], tenant_id, DatasetVersionStatus.BUILDING.value
            ) or existing
            logger.info(
                "build_dataset_v2_reusing_version: version_id=%s (retry)", version_id
            )
        else:
            row = dataset_repo.create_version_v2(
                {
                    "user_id": user_id,
                    "version": version,
                    "frame_count": len(frames),
                    "train_count": len(splits["train"]),
                    "val_count": len(splits["val"]),
                    "test_count": len(splits["test"]),
                    "class_distribution": class_distribution,
                    "metadata_key": None,
                    "tenant_id": tenant_id,
                    "module_code": module_code,
                    "dataset_id": dataset_id,
                    "split": split,
                    "augmentations": augmentations,
                    "coco_r2_key": None,
                    "export_format": export_format,
                    "status": DatasetVersionStatus.BUILDING.value,
                    "created_by": user_id,
                }
            )
            version_id = str(row["id"])

        # 7. Copiar imagens + upload dos COCO por split
        copy_errors: list[str] = []
        for split_name in _SPLIT_NAMES:
            split_frames = splits[split_name]
            for frame in split_frames:
                src = frame.get("r2_key") or frame.get("filename")
                dest = f"{base_key}/{split_name}/{frame['id']}.{_frame_ext(frame)}"
                try:
                    storage.copy_object(src, dest)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("copy_skipped: src=%s err=%s", src, exc)
                    copy_errors.append(f"{src} → {dest}: {exc}")

            coco = _build_coco_split(
                split_frames, anns_by_frame, categories, cat_id_by_class, version
            )
            storage.upload_bytes(
                f"{base_key}/{split_name}/{_COCO_FILENAME}",
                json.dumps(coco).encode("utf-8"),
                "application/json",
            )

        # 8. building → ready (grava prefixo R2 dos COCO)
        dataset_repo.update_version_status(
            row["id"], tenant_id, DatasetVersionStatus.READY.value,
            coco_r2_key=base_key,
        )

        result = {
            "dataset_version_id": version_id,
            "dataset_id": dataset_id,
            "tenant_id": tenant_id,
            "version": version,
            "status": DatasetVersionStatus.READY.value,
            "coco_r2_key": base_key,
            "total_frames": len(frames),
            "train_count": len(splits["train"]),
            "val_count": len(splits["val"]),
            "test_count": len(splits["test"]),
            "class_distribution": class_distribution,
            "categories": [c["name"] for c in categories],
            "copy_errors": copy_errors,
            "dimension_errors": dim_errors,
        }
        logger.info(
            "build_dataset_v2_done: version_id=%s total=%d train=%d val=%d test=%d",
            version_id, len(frames),
            len(splits["train"]), len(splits["val"]), len(splits["test"]),
        )
        return result

    except ValueError as exc:
        logger.error(
            "build_dataset_v2_invalid: tenant=%s dataset=%s err=%s",
            tenant_id, dataset_id, exc,
        )
        _mark_error(dataset_repo, version_id, tenant_id)
        raise
    except Exception as exc:
        logger.error(
            "build_dataset_v2_failed: tenant=%s dataset=%s err=%s",
            tenant_id, dataset_id, exc, exc_info=True,
        )
        _mark_error(dataset_repo, version_id, tenant_id)
        raise self.retry(exc=exc, countdown=60) from exc


def _mark_error(dataset_repo, version_id: str | None, tenant_id: str) -> None:
    """Marca a versão como 'error' (best-effort — nunca mascara a exceção)."""
    if not version_id:
        return
    try:
        dataset_repo.update_version_status(
            version_id, tenant_id, DatasetVersionStatus.ERROR.value
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "build_dataset_v2_mark_error_failed: version=%s err=%s",
            version_id, exc,
        )
