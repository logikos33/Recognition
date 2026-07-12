"""
Recognition — Dataset Service.

Lógica de versionamento de datasets para treinamento YOLO (legado) +
datasets pai tenant-scoped e builds COCO v2 (WS-A3, migration 096).
"""
import logging
from typing import Any
from uuid import UUID

from app.constants import DatasetVersionStatus
from app.core.exceptions import NotFoundError
from app.infrastructure.database.repositories.dataset_repository import (
    DatasetRepository,
)

logger = logging.getLogger(__name__)

_SPLIT_KEYS = ("train", "val", "test")
_SPLIT_TOLERANCE = 0.01
_DEFAULT_SPLIT = {"train": 0.7, "val": 0.2, "test": 0.1}


def _stringify_ids(row: dict[str, Any]) -> dict[str, Any]:
    """Converte campos UUID conhecidos para str (JSON-safe e consistente)."""
    for key in ("id", "dataset_id", "tenant_id", "user_id", "created_by"):
        if row.get(key) is not None:
            row[key] = str(row[key])
    return row


class DatasetService:
    """Use cases de dataset versioning."""

    def __init__(self, dataset_repo: DatasetRepository) -> None:
        self._dataset_repo = dataset_repo

    # ------------------------------------------------------------------
    # Datasets pai (container lógico — migration 096, WS-A3)
    # ------------------------------------------------------------------

    def create_dataset(
        self,
        tenant_id: str,
        name: str,
        description: str | None = None,
        module_code: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Cria dataset pai tenant-scoped. Raises ValueError se nome inválido."""
        name = (name or "").strip()
        if not name:
            raise ValueError("Campo 'name' é obrigatório")
        if len(name) > 255:
            raise ValueError("Campo 'name' excede 255 caracteres")
        if module_code is not None and len(module_code) > 50:
            raise ValueError("Campo 'module_code' excede 50 caracteres")

        row = self._dataset_repo.create_dataset(
            {
                "tenant_id": tenant_id,
                "module_code": module_code,
                "name": name,
                "description": description,
                "created_by": created_by,
            }
        )
        return _stringify_ids(row)

    def list_datasets(
        self, tenant_id: str, module_code: str | None = None
    ) -> list[dict[str, Any]]:
        """Lista datasets do tenant (filtro opcional por módulo)."""
        rows = self._dataset_repo.list_datasets(tenant_id, module_code)
        return [_stringify_ids(r) for r in rows]

    def get_dataset(
        self, dataset_id: UUID, tenant_id: str
    ) -> dict[str, Any] | None:
        """Busca dataset pai validando posse do tenant (C-01)."""
        row = self._dataset_repo.get_dataset_by_id(dataset_id, tenant_id)
        return _stringify_ids(row) if row else None

    def list_dataset_versions(
        self, dataset_id: UUID, tenant_id: str
    ) -> list[dict[str, Any]]:
        """Lista versões de um dataset pai, tenant-scoped."""
        rows = self._dataset_repo.get_versions_by_dataset(dataset_id, tenant_id)
        return [_stringify_ids(r) for r in rows]

    def next_version_label(self, dataset_id: UUID, tenant_id: str) -> str:
        """Próximo rótulo sequencial de versão do dataset (v1, v2, ...)."""
        existing = self._dataset_repo.get_versions_by_dataset(dataset_id, tenant_id)
        return f"v{len(existing) + 1}"

    @staticmethod
    def validate_split(split: dict[str, Any] | None) -> dict[str, float]:
        """Valida e normaliza o split {train, val, test}.

        Default: {train: 0.7, val: 0.2, test: 0.1}. Raises ValueError.
        """
        if split is None:
            return dict(_DEFAULT_SPLIT)
        if not isinstance(split, dict):
            raise ValueError("Campo 'split' deve ser objeto {train, val, test}")

        unknown = set(split) - set(_SPLIT_KEYS)
        if unknown:
            raise ValueError(f"Chaves inválidas em 'split': {sorted(unknown)}")

        normalized: dict[str, float] = {}
        for key in _SPLIT_KEYS:
            raw = split.get(key, 0)
            try:
                value = float(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"split.{key} deve ser numérico") from exc
            if value < 0 or value > 1:
                raise ValueError(f"split.{key} deve estar entre 0 e 1")
            normalized[key] = value

        if normalized["train"] <= 0:
            raise ValueError("split.train deve ser > 0")
        if abs(sum(normalized.values()) - 1.0) > _SPLIT_TOLERANCE:
            raise ValueError("split deve somar 1.0 (train + val + test)")
        return normalized

    def get_version_detail(
        self, version_id: UUID, tenant_id: str
    ) -> dict[str, Any] | None:
        """Detalhe de uma dataset_version + presigned GET dos COCO por split.

        Retorna None se a versão não existe ou pertence a outro tenant (C-01).
        Presigned URLs só quando status='ready' e coco_r2_key presente.
        """
        row = self._dataset_repo.get_by_id(version_id)
        if row is None:
            return None
        if row.get("tenant_id") is None or str(row["tenant_id"]) != str(tenant_id):
            return None

        detail = _stringify_ids(row)
        coco_files: dict[str, dict[str, str]] = {}
        if (
            str(detail.get("status")) == DatasetVersionStatus.READY.value
            and detail.get("coco_r2_key")
        ):
            from app.infrastructure.storage.local_storage import get_storage

            storage = get_storage()
            prefix = str(detail["coco_r2_key"]).rstrip("/")
            for split_name in _SPLIT_KEYS:
                key = f"{prefix}/{split_name}/_annotations.coco.json"
                try:
                    coco_files[split_name] = {
                        "key": key,
                        "url": storage.generate_presigned_download_url(key),
                    }
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "presign_coco_failed: version=%s split=%s err=%s",
                        version_id, split_name, exc,
                    )
        detail["coco_files"] = coco_files
        return detail

    # ------------------------------------------------------------------
    # Versões (legado — pré-096)
    # ------------------------------------------------------------------

    def create_version(
        self,
        user_id: UUID,
        version: str,
        frame_count: int,
        train_count: int,
        val_count: int,
        test_count: int,
        class_distribution: dict[str, int],
        metadata_key: str | None = None,
    ) -> dict:
        """Cria nova versão de dataset."""
        data = {
            "user_id": user_id,
            "version": version,
            "frame_count": frame_count,
            "train_count": train_count,
            "val_count": val_count,
            "test_count": test_count,
            "class_distribution": class_distribution,
            "metadata_key": metadata_key,
        }
        result = self._dataset_repo.create(data)
        result["id"] = str(result["id"])
        return result

    def list_versions(self, user_id: UUID) -> list[dict]:
        """Lista versões de dataset do usuário."""
        versions = self._dataset_repo.get_by_user(user_id)
        for v in versions:
            v["id"] = str(v["id"])
        return versions

    def get_version(self, version_id: UUID) -> dict:
        """Busca versão por ID."""
        version = self._dataset_repo.get_by_id(version_id)
        if not version:
            raise NotFoundError("Dataset version", str(version_id))
        version["id"] = str(version["id"])
        return version

    def get_latest(self, user_id: UUID) -> dict | None:
        """Busca versão mais recente do usuário."""
        version = self._dataset_repo.get_latest(user_id)
        if version:
            version["id"] = str(version["id"])
        return version
