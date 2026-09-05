"""
Recognition — Dataset Versioning Task.

Celery task: monta dataset YOLO versionado a partir de frames anotados.
Split por fonte de vídeo (não por frame individual).
"""
import json
import logging
import random
from uuid import UUID

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

_DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def _get_annotation_repo():
    from app.infrastructure.database.connection import DatabasePool
    from app.infrastructure.database.repositories.annotation_repository import AnnotationRepository
    return AnnotationRepository(DatabasePool.get_instance())


def _get_storage():
    from app.infrastructure.storage.local_storage import get_storage
    return get_storage()


@celery.task(
    bind=True, max_retries=2, queue="versioning",
    name="tasks.versioning.build_dataset_version",
)
def build_dataset_version(
    self,
    user_id: str,
    version: str,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
    test_ratio: float = 0.1,
) -> dict:
    """Monta dataset versionado com split por vídeo fonte.

    AI_NOTE: Split é feito por video_id (grupo), não por frame individual.
    Isso evita data leakage entre train/val/test de frames do mesmo vídeo.
    """
    try:
        logger.info("build_dataset_start: user=%s, version=%s", user_id, version)

        annotation_repo = _get_annotation_repo()

        # 0. Tenant do usuário — escopo de frames sem vídeo e INSERT final
        user_row = annotation_repo._execute_one(
            "SELECT tenant_id FROM users WHERE id = %s", (user_id,)
        )
        tenant_id = (
            str(user_row["tenant_id"])
            if user_row and user_row.get("tenant_id")
            else _DEFAULT_TENANT_ID
        )

        # 1. Buscar todos os frames anotados do usuário (preferindo validados)
        # AI_NOTE (A-2): LEFT JOIN — após a migration 094, video_id pode ser
        # NULL (frames de upload/auto-captura); INNER JOIN os excluiria
        # silenciosamente. Frames sem vídeo entram pelo escopo do tenant.
        #
        # ⛔ TRAVA HOLDOUT-ONLY (migration 133): `dataset_role = 'pool'`.
        # Esta task é LEGADA (a oficial é versioning_v2.build_dataset_version_v2)
        # e hoje nenhuma rota a dispara — mas ela continua REGISTRADA no Celery
        # (celery_app.py:152, fila 'versioning'), o que basta para alguém
        # chamá-la por nome. Trava que cobre um caminho e deixa outro aberto é
        # pior que trava nenhuma: dá confiança sem dar garantia.
        annotated_frames = annotation_repo._execute(
            """
            SELECT tf.id, tf.video_id, tf.filename, tf.r2_key, tf.frame_number,
                   tf.module_code,
                   tf.validated_at IS NOT NULL AS is_validated
            FROM training_frames tf
            LEFT JOIN training_videos tv ON tv.id = tf.video_id
            WHERE (tv.user_id = %s OR (tf.video_id IS NULL AND tf.tenant_id = %s))
              AND tf.is_annotated = TRUE
              AND tf.dataset_role = 'pool'
            ORDER BY tf.video_id, tf.frame_number
            """,
            (user_id, tenant_id),
        )

        if not annotated_frames:
            raise ValueError("Nenhum frame anotado encontrado para este usuário")

        if len(annotated_frames) < 5:
            raise ValueError(
                f"Frames insuficientes ({len(annotated_frames)}). Mínimo: 5"
            )

        # 2. Buscar classes do usuário
        classes = annotation_repo.get_classes_by_user(UUID(user_id))
        class_names = [c["name"] for c in classes]
        if not class_names:
            class_names = ["Objeto"]

        # 3. Agrupar por video_id e fazer split por grupo
        # AI_NOTE: agrupamento por vídeo garante que frames do mesmo vídeo
        # não apareçam em splits diferentes (evita data leakage). Frames sem
        # vídeo (upload/auto) formam grupos individuais por frame id.
        groups: dict[str, list] = {}
        for frame in annotated_frames:
            vid = (
                str(frame["video_id"])
                if frame.get("video_id")
                else f"frame:{frame['id']}"
            )
            groups.setdefault(vid, []).append(frame)

        video_ids = list(groups.keys())
        random.shuffle(video_ids)

        n = len(video_ids)
        n_train = max(1, int(n * train_ratio))
        n_val = max(1, int(n * val_ratio))

        train_vids = set(video_ids[:n_train])
        val_vids = set(video_ids[n_train:n_train + n_val])
        test_vids = set(video_ids[n_train + n_val:])

        # Distribuir frames por split
        splits: dict[str, list] = {"train": [], "val": [], "test": []}
        for vid_id, frames in groups.items():
            if vid_id in train_vids:
                splits["train"].extend(frames)
            elif vid_id in val_vids:
                splits["val"].extend(frames)
            elif vid_id in test_vids:
                splits["test"].extend(frames)

        # Garantir que val e test não ficam vazios (fallback para frames de train)
        if not splits["val"] and splits["train"]:
            cut = max(1, len(splits["train"]) // 5)
            splits["val"] = splits["train"][-cut:]
            splits["train"] = splits["train"][:-cut]
        if not splits["test"] and splits["val"]:
            splits["test"] = splits["val"][-1:]
            splits["val"] = splits["val"][:-1]

        # 4. Copiar imagens e labels para o layout do dataset (server-side)
        # AI_NOTE: filename/r2_key JÁ é a chave R2 completa
        # (frames/{user_id}/{video_id}/frame_NNNN.jpg — ver extraction.py);
        # o label espelha a chave trocando frames/→labels/ e a extensão
        # (ver annotation_service._export_yolo_labels). O destino usa o
        # frame id como stem para evitar colisão de frame_NNNN entre vídeos.
        storage = _get_storage()
        copy_errors: list[str] = []
        for split_name, frames in splits.items():
            for frame in frames:
                frame_id = str(frame["id"])
                frame_key = frame.get("r2_key") or frame["filename"]
                if "." in frame_key:
                    base, ext = frame_key.rsplit(".", 1)
                else:
                    base, ext = frame_key, "jpg"
                lbl_src = base.replace("frames/", "labels/", 1) + ".txt"
                img_dest = (
                    f"datasets/{user_id}/{version}/{split_name}/images/{frame_id}.{ext}"
                )
                lbl_dest = (
                    f"datasets/{user_id}/{version}/{split_name}/labels/{frame_id}.txt"
                )
                for src, dest in ((frame_key, img_dest), (lbl_src, lbl_dest)):
                    try:
                        storage.copy_object(src, dest)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("copy_skipped: src=%s, error=%s", src, exc)
                        copy_errors.append(f"{src} → {dest}: {exc}")

        # 5. Gerar dataset.yaml
        dataset_yaml = (
            f"# Dataset YOLO gerado por Recognition\n"
            f"# Versão: {version}\n"
            f"# Total frames: {len(annotated_frames)}\n"
            f"\n"
            f"nc: {len(class_names)}\n"
            f"names: {class_names!r}\n"
            f"\n"
            f"train: datasets/{user_id}/{version}/train/images\n"
            f"val: datasets/{user_id}/{version}/val/images\n"
            f"test: datasets/{user_id}/{version}/test/images\n"
        )

        # 6. Upload dataset.yaml para storage
        yaml_key = f"datasets/{user_id}/{version}/dataset.yaml"
        storage.upload_bytes(yaml_key, dataset_yaml.encode("utf-8"), "text/yaml")

        # 7. Registrar a versão em dataset_versions (bug: nunca INSERTava).
        # Colunas legadas (004) + tenant_id/module_code/status da 096.
        # SQL direto no padrão do arquivo: DatasetRepository.create ainda não
        # cobre as colunas da 096 (create_version_v2 chega no PR-2).
        module_code = next(
            (f.get("module_code") for f in annotated_frames if f.get("module_code")),
            None,
        ) or "epi"
        dv_row = annotation_repo._execute_mutation(
            """
            INSERT INTO dataset_versions
                (user_id, version, frame_count, train_count, val_count,
                 test_count, class_distribution, metadata_key,
                 tenant_id, module_code, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, 'ready')
            RETURNING id
            """,
            (
                user_id,
                version,
                len(annotated_frames),
                len(splits["train"]),
                len(splits["val"]),
                len(splits["test"]),
                json.dumps({}),
                yaml_key,
                tenant_id,
                module_code,
            ),
        )
        dataset_version_id = str(dv_row["id"]) if dv_row else None

        result = {
            "user_id": user_id,
            "version": version,
            "dataset_version_id": dataset_version_id,
            "tenant_id": tenant_id,
            "status": "completed",
            "total_frames": len(annotated_frames),
            "train_count": len(splits["train"]),
            "val_count": len(splits["val"]),
            "test_count": len(splits["test"]),
            "class_names": class_names,
            "dataset_yaml": dataset_yaml,
            "dataset_yaml_key": yaml_key,
            "copy_errors": copy_errors,
            "splits": {
                "train_ratio": train_ratio,
                "val_ratio": val_ratio,
                "test_ratio": test_ratio,
            },
        }

        logger.info(
            "build_dataset_done: user=%s, version=%s, total=%d, train=%d, val=%d, test=%d",
            user_id, version, len(annotated_frames),
            len(splits["train"]), len(splits["val"]), len(splits["test"]),
        )

        return result

    except ValueError as exc:
        logger.error("build_dataset_insufficient: user=%s, error=%s", user_id, exc)
        raise
    except Exception as exc:
        logger.error(
            "build_dataset_failed: user=%s, error=%s", user_id, exc, exc_info=True
        )
        raise self.retry(exc=exc, countdown=60) from exc
