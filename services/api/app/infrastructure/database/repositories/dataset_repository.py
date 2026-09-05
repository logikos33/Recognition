"""Repository: Datasets (pai) + Dataset Versions."""
import json
from typing import Any, Optional
from uuid import UUID

from app.constants import DatasetVersionStatus
from app.infrastructure.database.repositories.base import BaseRepository


class DatasetRepository(BaseRepository):
    """Queries SQL para tabelas datasets (096) e dataset_versions."""

    # --- Datasets (container pai — migration 096) ---

    def create_dataset(self, data: dict[str, Any]) -> dict[str, Any]:
        """Cria dataset pai (container lógico de versões), tenant-scoped."""
        return self._execute_mutation(
            "INSERT INTO datasets (tenant_id, module_code, name, description, created_by) "
            "VALUES (%s, COALESCE(%s, 'epi'), %s, %s, %s) RETURNING *",
            (
                str(data["tenant_id"]),
                data.get("module_code"),
                data["name"],
                data.get("description"),
                str(data["created_by"]) if data.get("created_by") else None,
            ),
        )  # type: ignore[return-value]

    def get_dataset_by_id(
        self, dataset_id: UUID, tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """Busca dataset pai por ID validando posse do tenant (C-01)."""
        return self._execute_one(
            "SELECT * FROM datasets WHERE id = %s AND tenant_id = %s",
            (str(dataset_id), str(tenant_id)),
        )

    def list_datasets(
        self, tenant_id: str, module_code: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Lista datasets do tenant, opcionalmente filtrados por módulo."""
        if module_code:
            return self._execute(
                "SELECT * FROM datasets WHERE tenant_id = %s AND module_code = %s "
                "ORDER BY created_at DESC",
                (str(tenant_id), module_code),
            )
        return self._execute(
            "SELECT * FROM datasets WHERE tenant_id = %s ORDER BY created_at DESC",
            (str(tenant_id),),
        )

    # --- Dataset Versions ---

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """Cria versão de dataset."""
        return self._execute_mutation(
            "INSERT INTO dataset_versions "
            "(user_id, version, frame_count, train_count, val_count, "
            "test_count, class_distribution, metadata_key) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s) RETURNING *",
            (
                str(data["user_id"]),
                data["version"],
                data["frame_count"],
                data["train_count"],
                data["val_count"],
                data["test_count"],
                json.dumps(data.get("class_distribution", {})),
                data.get("metadata_key"),
            ),
        )  # type: ignore[return-value]

    def create_version_v2(self, data: dict[str, Any]) -> dict[str, Any]:
        """Cria versão de dataset com linhagem completa (colunas da 096 — ajuste #9).

        Grava tenant_id, module_code, dataset_id, split, augmentations,
        coco_r2_key, export_format, status e created_by além das colunas
        legadas. Usada por build_dataset_version_v2 (status inicial 'building').
        """
        return self._execute_mutation(
            "INSERT INTO dataset_versions "
            "(user_id, version, frame_count, train_count, val_count, test_count, "
            " class_distribution, metadata_key, tenant_id, module_code, dataset_id, "
            " split, augmentations, coco_r2_key, export_format, status, created_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, COALESCE(%s, 'epi'), "
            "        %s, %s::jsonb, %s::jsonb, %s, %s, COALESCE(%s, 'ready'), %s) "
            "RETURNING *",
            (
                str(data["user_id"]),
                data["version"],
                data.get("frame_count", 0),
                data.get("train_count", 0),
                data.get("val_count", 0),
                data.get("test_count", 0),
                json.dumps(data.get("class_distribution", {})),
                data.get("metadata_key"),
                str(data["tenant_id"]),
                data.get("module_code"),
                str(data["dataset_id"]) if data.get("dataset_id") else None,
                json.dumps(data["split"]) if data.get("split") is not None else None,
                (
                    json.dumps(data["augmentations"])
                    if data.get("augmentations") is not None
                    else None
                ),
                data.get("coco_r2_key"),
                data.get("export_format"),
                str(data["status"]) if data.get("status") else None,
                str(data["created_by"]) if data.get("created_by") else None,
            ),
        )  # type: ignore[return-value]

    def update_version_status(
        self,
        version_id: UUID,
        tenant_id: str,
        status: str | DatasetVersionStatus,
        coco_r2_key: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Atualiza status do build (building→ready|error), tenant-scoped."""
        if coco_r2_key is not None:
            return self._execute_mutation(
                "UPDATE dataset_versions SET status = %s, coco_r2_key = %s "
                "WHERE id = %s AND tenant_id = %s RETURNING *",
                (str(status), coco_r2_key, str(version_id), str(tenant_id)),
            )
        return self._execute_mutation(
            "UPDATE dataset_versions SET status = %s "
            "WHERE id = %s AND tenant_id = %s RETURNING *",
            (str(status), str(version_id), str(tenant_id)),
        )

    def update_version_counts(
        self,
        version_id: UUID,
        tenant_id: str,
        frame_count: int,
        train_count: int,
        val_count: int,
        test_count: int,
    ) -> Optional[dict[str, Any]]:
        """Reescreve as contagens da versão, tenant-scoped.

        Um re-build reaproveita a row (get_pending_version) e reescreve o mesmo
        prefixo R2: sem isto, as contagens continuam sendo as da tentativa
        anterior e o banco descreve um artefato que não existe mais. O
        v9-freeze ficou com val=159 no banco enquanto o COCO declarava 553
        (#515) — e é o banco que o dispatch de treino lê.
        """
        return self._execute_mutation(
            "UPDATE dataset_versions SET frame_count = %s, train_count = %s, "
            "val_count = %s, test_count = %s "
            "WHERE id = %s AND tenant_id = %s RETURNING *",
            (
                frame_count, train_count, val_count, test_count,
                str(version_id), str(tenant_id),
            ),
        )

    def update_split_membership(
        self,
        version_id: UUID,
        tenant_id: str,
        membership: dict[str, list[str]],
    ) -> Optional[dict[str, Any]]:
        """Congela QUEM caiu em cada split — {"train":[ids],"val":[...],"test":[...]}.

        A coluna `split` só guarda a proporção pedida. Sem esta membresia o
        holdout é uma promessa: o split do build 42023066 saiu de um
        `random.shuffle` sem semente e não é reproduzível nem re-executando o
        código. Gravada no build, antes de 'ready' — a partir daí a versão é
        imutável e o holdout também.
        """
        return self._execute_mutation(
            "UPDATE dataset_versions SET split_membership = %s::jsonb "
            "WHERE id = %s AND tenant_id = %s RETURNING id",
            (json.dumps(membership), str(version_id), str(tenant_id)),
        )

    def get_holdout(
        self, version_id: UUID, preferencia: tuple[str, ...] = ("test", "val")
    ) -> Optional[dict[str, Any]]:
        """O holdout da versão pedida — independente de qual modelo o consome.

        Este é o ponto: `_resolve_holdout_split` escolhia o split pela contagem
        da dataset_version DO PRÓPRIO MODELO, e por isso o ranking histórico
        comparou modelos em provas diferentes. Aqui a entrada é o id do holdout
        e nada mais; dois modelos que pedem o mesmo id recebem a mesma lista.

        Retorna None se a versão não existe. `frame_ids=None` + `frozen=False`
        quando a versão é anterior à migration 131 (membresia irrecuperável) —
        ausência de congelamento nunca é devolvida como congelamento.
        """
        row = self._execute_one(
            "SELECT id, coco_r2_key, split_membership, test_count, val_count "
            "FROM dataset_versions WHERE id = %s",
            (str(version_id),),
        )
        if row is None:
            return None

        membership = row.get("split_membership") or {}
        if isinstance(membership, str):  # driver sem parse automático de jsonb
            membership = json.loads(membership)

        for nome in preferencia:
            frame_ids = membership.get(nome)
            if frame_ids:
                return {
                    "dataset_version_id": str(row["id"]),
                    "coco_r2_key": row.get("coco_r2_key"),
                    "split": nome,
                    "frame_ids": [str(f) for f in frame_ids],
                    "frozen": True,
                }

        # Sem membresia gravada: cai na contagem (comportamento legado), mas
        # devolve frozen=False para quem gravar a métrica registrar que a prova
        # não estava congelada.
        for nome in preferencia:
            if int(row.get(f"{nome}_count") or 0) > 0:
                return {
                    "dataset_version_id": str(row["id"]),
                    "coco_r2_key": row.get("coco_r2_key"),
                    "split": nome,
                    "frame_ids": None,
                    "frozen": False,
                }
        return None

    def get_versions_by_dataset(
        self, dataset_id: UUID, tenant_id: str
    ) -> list[dict[str, Any]]:
        """Lista versões de um dataset pai, tenant-scoped."""
        return self._execute(
            "SELECT * FROM dataset_versions "
            "WHERE dataset_id = %s AND tenant_id = %s ORDER BY created_at DESC",
            (str(dataset_id), str(tenant_id)),
        )

    def get_version_by_label(
        self, dataset_id: str, tenant_id: str, version: str
    ) -> Optional[dict[str, Any]]:
        """Versão mais recente com esse label, QUALQUER status.

        Usado pelo guard de imutabilidade (build sobre versão `ready` é
        recusado). Diferente de get_pending_version, que só enxerga
        building/error e por isso não via a versão pronta que estava sendo
        sobrescrita.
        """
        return self._execute_one(
            "SELECT * FROM dataset_versions "
            "WHERE dataset_id = %s AND tenant_id = %s AND version = %s "
            "ORDER BY created_at DESC LIMIT 1",
            (str(dataset_id), str(tenant_id), version),
        )

    def get_pending_version(
        self, dataset_id: str, tenant_id: str, version: str
    ) -> Optional[dict[str, Any]]:
        """Busca versão 'building'/'error' já existente com o mesmo label.

        Sem UNIQUE(dataset_id, version) no schema (096) — usado por
        build_dataset_version_v2 para reutilizar a row de uma tentativa
        anterior em vez de INSERTar de novo a cada retry do Celery (achado
        da revisão adversarial: retry após falha transiente no upload R2
        deixava a row original órfã em 'error' e criava outra com o MESMO
        label a cada nova tentativa).
        """
        return self._execute_one(
            "SELECT * FROM dataset_versions "
            "WHERE dataset_id = %s AND tenant_id = %s AND version = %s "
            "AND status IN ('building', 'error') "
            "ORDER BY created_at DESC LIMIT 1",
            (str(dataset_id), str(tenant_id), version),
        )

    def get_by_id(self, version_id: UUID) -> Optional[dict[str, Any]]:
        """Busca versão por ID."""
        return self._execute_one(
            "SELECT * FROM dataset_versions WHERE id = %s",
            (str(version_id),),
        )

    def get_by_user(self, user_id: UUID) -> list[dict[str, Any]]:
        """Lista versões do usuário."""
        return self._execute(
            "SELECT * FROM dataset_versions WHERE user_id = %s "
            "ORDER BY created_at DESC",
            (str(user_id),),
        )

    def get_latest(self, user_id: UUID) -> Optional[dict[str, Any]]:
        """Busca versão mais recente do usuário."""
        return self._execute_one(
            "SELECT * FROM dataset_versions WHERE user_id = %s "
            "ORDER BY created_at DESC LIMIT 1",
            (str(user_id),),
        )
