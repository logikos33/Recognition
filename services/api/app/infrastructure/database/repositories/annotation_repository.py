"""Repository: Frame Annotations + YOLO Classes."""
from typing import Any
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class AnnotationRepository(BaseRepository):
    """Queries SQL para frame_annotations e yolo_classes."""

    # --- YOLO Classes ---

    def create_class(
        self,
        user_id: UUID,
        name: str,
        color: str = "#3b82f6",
        *,
        tenant_id: "UUID | str",
        module_code: "str | None" = None,
    ) -> dict[str, Any]:
        """Cria classe YOLO, tenant-scoped (migration 093).

        tenant_id é OBRIGATÓRIO e explícito (keyword-only, sem default) —
        fail-closed, mesmo padrão do #313/#315 (docs/security/
        tenant-context-sweep.md). Versão anterior tinha um COALESCE com uma
        subquery que buscava tenant_id na tabela de usuários pelo id do
        usuário: sob contexto assumido (superadmin operando via
        POST /tenants/<id>/assume) essa subquery resolve o tenant DE CASA do
        usuário, não o tenant do CONTEXTO da requisição — o mesmo
        anti-padrão corrigido em frame_repository.get_by_id_and_user/
        mark_validated. O único caller vivo (TenantClassService.create_class)
        sempre recebe get_tenant_id() do handler e propaga aqui; não há mais
        fallback silencioso.

        module_code omitido → 'epi' (default do schema) — isso NÃO é o mesmo
        anti-padrão: não deriva identidade de tenant, só um valor de
        categoria.
        """
        return self._execute_mutation(
            "INSERT INTO yolo_classes (user_id, name, color, tenant_id, module_code) "
            "VALUES (%s, %s, %s, %s, COALESCE(%s, 'epi')) RETURNING *",
            (
                str(user_id),
                name,
                color,
                str(tenant_id),
                module_code,
            ),
        )  # type: ignore[return-value]

    def get_classes_by_user(self, user_id: UUID) -> list[dict[str, Any]]:
        """Lista classes do usuário (legado — preferir get_classes_for_tenant)."""
        return self._execute(
            "SELECT * FROM yolo_classes WHERE user_id = %s ORDER BY id",
            (str(user_id),),
        )

    def get_classes_for_tenant(
        self,
        tenant_id: str,
        user_id: "UUID | None" = None,
        module_code: str = "epi",
    ) -> list[dict[str, Any]]:
        """Lista classes do tenant+módulo, com fallback user_id p/ legado (093).

        Linhas anteriores ao backfill da 093 podem ter tenant_id NULL — o
        fallback via user_id garante que o dono continue vendo suas classes.
        """
        if user_id is not None:
            return self._execute(
                "SELECT * FROM yolo_classes "
                "WHERE (tenant_id = %s OR (tenant_id IS NULL AND user_id = %s)) "
                "AND module_code = %s ORDER BY id",
                (str(tenant_id), str(user_id), module_code),
            )
        return self._execute(
            "SELECT * FROM yolo_classes "
            "WHERE tenant_id = %s AND module_code = %s ORDER BY id",
            (str(tenant_id), module_code),
        )

    def get_classes_with_counts(
        self,
        tenant_id: str,
        user_id: "UUID | None" = None,
        module_code: str = "epi",
    ) -> list[dict[str, Any]]:
        """Lista classes do tenant+módulo com contagem de anotações (WS-A1).

        annotation_count = amostras em frame_annotations por classe.
        Mesmo escopo/fallback legado de get_classes_for_tenant.
        """
        if user_id is not None:
            return self._execute(
                "SELECT c.*, COUNT(a.id) AS annotation_count "
                "FROM yolo_classes c "
                "LEFT JOIN frame_annotations a ON a.class_id = c.id "
                "WHERE (c.tenant_id = %s OR (c.tenant_id IS NULL AND c.user_id = %s)) "
                "AND c.module_code = %s GROUP BY c.id ORDER BY c.id",
                (str(tenant_id), str(user_id), module_code),
            )
        return self._execute(
            "SELECT c.*, COUNT(a.id) AS annotation_count "
            "FROM yolo_classes c "
            "LEFT JOIN frame_annotations a ON a.class_id = c.id "
            "WHERE c.tenant_id = %s AND c.module_code = %s "
            "GROUP BY c.id ORDER BY c.id",
            (str(tenant_id), module_code),
        )

    def get_class_for_tenant(
        self,
        class_id: int,
        tenant_id: str,
        user_id: "UUID | None" = None,
    ) -> "dict[str, Any] | None":
        """Busca classe por id no escopo do tenant (fallback user_id p/ legado)."""
        if user_id is not None:
            return self._execute_one(
                "SELECT * FROM yolo_classes WHERE id = %s "
                "AND (tenant_id = %s OR (tenant_id IS NULL AND user_id = %s))",
                (class_id, str(tenant_id), str(user_id)),
            )
        return self._execute_one(
            "SELECT * FROM yolo_classes WHERE id = %s AND tenant_id = %s",
            (class_id, str(tenant_id)),
        )

    def update_class(
        self,
        class_id: int,
        tenant_id: str,
        name: "str | None" = None,
        color: "str | None" = None,
        user_id: "UUID | None" = None,
    ) -> "dict[str, Any] | None":
        """Renomeia/recolore classe no escopo do tenant. None → mantém valor.

        Retorna a row atualizada ou None se a classe não pertence ao tenant.
        """
        if user_id is not None:
            return self._execute_mutation(
                "UPDATE yolo_classes "
                "SET name = COALESCE(%s, name), color = COALESCE(%s, color) "
                "WHERE id = %s "
                "AND (tenant_id = %s OR (tenant_id IS NULL AND user_id = %s)) "
                "RETURNING *",
                (name, color, class_id, str(tenant_id), str(user_id)),
            )
        return self._execute_mutation(
            "UPDATE yolo_classes "
            "SET name = COALESCE(%s, name), color = COALESCE(%s, color) "
            "WHERE id = %s AND tenant_id = %s RETURNING *",
            (name, color, class_id, str(tenant_id)),
        )

    def count_annotations_for_class(self, class_id: int) -> int:
        """Conta anotações em frame_annotations que referenciam a classe."""
        row = self._execute_one(
            "SELECT COUNT(*) AS n FROM frame_annotations WHERE class_id = %s",
            (class_id,),
        )
        return int(row["n"]) if row else 0

    def delete_class(
        self,
        class_id: int,
        tenant_id: str,
        user_id: "UUID | None" = None,
    ) -> int:
        """Deleta classe SEM anotações vinculadas (guarda NOT EXISTS).

        A guarda no SQL fecha a janela TOCTOU entre o count e o delete —
        sem ela, o ON DELETE CASCADE do schema destruiria anotações criadas
        entre a checagem e o DELETE. Retorna rowcount (0 = não deletou).
        """
        if user_id is not None:
            return self._execute_mutation_no_return(
                "DELETE FROM yolo_classes c WHERE c.id = %s "
                "AND (c.tenant_id = %s OR (c.tenant_id IS NULL AND c.user_id = %s)) "
                "AND NOT EXISTS ("
                "SELECT 1 FROM frame_annotations a WHERE a.class_id = c.id)",
                (class_id, str(tenant_id), str(user_id)),
            )
        return self._execute_mutation_no_return(
            "DELETE FROM yolo_classes c WHERE c.id = %s AND c.tenant_id = %s "
            "AND NOT EXISTS ("
            "SELECT 1 FROM frame_annotations a WHERE a.class_id = c.id)",
            (class_id, str(tenant_id)),
        )

    # --- Annotations ---

    def create_annotation(
        self,
        frame_id: UUID,
        class_id: int,
        x_center: float,
        y_center: float,
        width: float,
        height: float,
        class_name: "str | None" = None,
        module_code: "str | None" = None,
    ) -> dict[str, Any]:
        """Cria anotação de bounding box."""
        return self._execute_mutation(
            "INSERT INTO frame_annotations "
            "(frame_id, class_id, x_center, y_center, width, height, "
            "class_name, module_code) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
            (
                str(frame_id), class_id, x_center, y_center, width, height,
                class_name, module_code,
            ),
        )  # type: ignore[return-value]

    def get_by_frame(self, frame_id: UUID) -> list[dict[str, Any]]:
        """Lista anotações de um frame.

        class_name/module_code são armazenados na própria linha (task-077) —
        NUNCA reconstruídos via JOIN em yolo_classes (tabela legada de
        "classes customizadas" por usuário, sem relação com o índice do
        módulo usado aqui; ver task-077/078).
        """
        return self._execute(
            "SELECT * FROM frame_annotations "
            "WHERE frame_id = %s ORDER BY created_at",
            (str(frame_id),),
        )

    def delete_by_frame(self, frame_id: UUID) -> int:
        """Deleta todas as anotações de um frame (para re-anotar)."""
        return self._execute_mutation_no_return(
            "DELETE FROM frame_annotations WHERE frame_id = %s",
            (str(frame_id),),
        )

    def save_batch(
        self,
        frame_id: UUID,
        annotations: list[dict[str, Any]],
        user_id: "UUID | str | None" = None,
    ) -> int:
        """Salva batch de anotações (delete + insert) em transação única.

        AI_NOTE: US-027 — operação atômica: DELETE + INSERTs na mesma conexão.
        Rollback automático preserva anotações anteriores em caso de falha parcial.

        class_name/module_code (task-077) vêm do payload validado pelo
        service (AnnotationService._validate_class) — a fonte da verdade é a
        classe que o usuário escolheu no frontend, não um JOIN reconstruído.

        Proveniência (migration 095): grava source='manual' + created_by=
        user_id explicitamente — este é o caminho de save humano (via
        AnnotationInterface.jsx), nunca 'pre_annotation' (esse é
        accept_pre_annotations, INSERT puro, não delete-then-insert).
        user_id é opcional (chamadas internas/Celery sem contexto de
        usuário deixam created_by NULL, honesto — sem fallback silencioso).
        """
        created_by = str(user_id) if user_id is not None else None

        def _transaction(conn, cur) -> int:
            cur.execute(
                "DELETE FROM frame_annotations WHERE frame_id = %s",
                (str(frame_id),),
            )
            count = 0
            for ann in annotations:
                cur.execute(
                    "INSERT INTO frame_annotations "
                    "(frame_id, class_id, x_center, y_center, width, height, "
                    "class_name, module_code, source, created_by) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'manual', %s)",
                    (
                        str(frame_id),
                        ann["class_id"],
                        ann["x_center"],
                        ann["y_center"],
                        ann["width"],
                        ann["height"],
                        ann["class_name"],
                        ann["module_code"],
                        created_by,
                    ),
                )
                count += 1
            return count

        return self._execute_in_transaction(_transaction)

    def accept_pre_annotations(
        self, frame_id: UUID, annotations: list[dict[str, Any]], user_id: UUID
    ) -> int:
        """Aceita sugestões de pré-anotação (WS-B4): INSERT puro (não
        delete-then-insert como save_batch) — nunca apaga anotações humanas
        já existentes no frame, só adiciona as sugestões aceitas.

        source='pre_annotation' + created_by/reviewed_by=user_id (migration
        095) — quem aceita a sugestão está, no mesmo ato, revisando-a.

        class_name (task-077) vem do label bruto da sugestão de IA
        (get_frame_annotations); module_code fica NULL aqui deliberadamente —
        este fluxo legado identifica classes via yolo_classes (por usuário),
        não via module_classes, e inventar um module_code seria uma
        suposição não verificada (mesmo espírito de "sem fallback
        silencioso" — melhor NULL honesto do que um valor errado).
        """

        def _transaction(conn, cur) -> int:
            count = 0
            for ann in annotations:
                cur.execute(
                    "INSERT INTO frame_annotations "
                    "(frame_id, class_id, x_center, y_center, width, height, "
                    "class_name, source, created_by, reviewed_by) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, 'pre_annotation', %s, %s)",
                    (
                        str(frame_id),
                        ann["class_id"],
                        ann["x_center"],
                        ann["y_center"],
                        ann["width"],
                        ann["height"],
                        ann.get("class_name"),
                        str(user_id),
                        str(user_id),
                    ),
                )
                count += 1
            return count

        return self._execute_in_transaction(_transaction)
