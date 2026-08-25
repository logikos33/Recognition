"""Repository: Frame Annotations + YOLO Classes."""
from typing import Any
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository

#: Casas decimais para decidir "a mesma caixa". Coordenada normalizada com 6
#: casas distingue meio pixel num frame de 2 megapixels — fino o bastante para
#: qualquer ajuste humano real e grosso o bastante para o ruído de ida e volta
#: entre float do Postgres, JSON e float do Python.
_CASAS_GEOMETRIA = 6


def _chave_geometrica(
    class_name: Any, x_center: Any, y_center: Any, width: Any, height: Any,
) -> tuple:
    """Identidade de uma caixa para efeito de "o humano mexeu nela?".

    Caixa não tocada volta do frontend com a MESMA coordenada; movida ou
    redimensionada volta diferente. É esse o critério para herdar (ou perder)
    a proveniência no save — ver save_batch.
    """
    return (
        str(class_name),
        round(float(x_center), _CASAS_GEOMETRIA),
        round(float(y_center), _CASAS_GEOMETRIA),
        round(float(width), _CASAS_GEOMETRIA),
        round(float(height), _CASAS_GEOMETRIA),
    )


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
        exclude_archived: bool = False,
        order_by_curation: bool = False,
    ) -> list[dict[str, Any]]:
        """Lista classes do tenant+módulo, com fallback user_id p/ legado (093).

        Linhas anteriores ao backfill da 093 podem ter tenant_id NULL — o
        fallback via user_id garante que o dono continue vendo suas classes.

        `exclude_archived` (migration 110): omite classes arquivadas
        (archived_at IS NOT NULL) — usado pelo anotador (ModuleService.
        get_classes), que não deve oferecer classe aposentada para escolha.
        Callers de gestão (TenantClassService.list_classes, validação em
        annotation_service) continuam vendo tudo por padrão (False).

        `order_by_curation`: ORDER BY display_order NULLS LAST, id — em vez
        da ordem crua por id — para o painel de curadoria respeitar a ordem
        que o tenant escolheu.

        `archived_clause`/`order_clause` vêm de flags booleanas (não de
        input do usuário) — só fragmentos SQL estáticos, nunca string
        interpolada a partir de request; os únicos valores de usuário na
        query continuam indo por parâmetro (%s).
        """
        archived_clause = " AND archived_at IS NULL" if exclude_archived else ""
        order_clause = "display_order NULLS LAST, id" if order_by_curation else "id"
        if user_id is not None:
            return self._execute(
                "SELECT * FROM yolo_classes "
                "WHERE (tenant_id = %s OR (tenant_id IS NULL AND user_id = %s)) "
                f"AND module_code = %s{archived_clause} ORDER BY {order_clause}",
                (str(tenant_id), str(user_id), module_code),
            )
        return self._execute(
            "SELECT * FROM yolo_classes "
            f"WHERE tenant_id = %s AND module_code = %s{archived_clause} "
            f"ORDER BY {order_clause}",
            (str(tenant_id), module_code),
        )

    def get_usage_counts_by_tenant(self, tenant_id: str) -> dict[int, int]:
        """Conta anotações por class_id, escopado ao tenant via JOIN training_frames.

        class_id em frame_annotations é um inteiro solto (sem FK — migration
        103): índice 0-based de module_classes (catálogo, reaproveitado por
        TODOS os tenants) OU id namespaced de yolo_classes (class_namespace.
        TENANT_CLASS_ID_OFFSET + id, único globalmente — ver class_namespace.py).
        Para classes de catálogo o mesmo inteiro aparece em vários tenants — o
        JOIN em training_frames.tenant_id garante que a contagem devolvida é
        só deste tenant, não do módulo inteiro.
        """
        rows = self._execute(
            "SELECT fa.class_id, COUNT(*) AS n "
            "FROM frame_annotations fa "
            "JOIN training_frames tf ON tf.id = fa.frame_id "
            "WHERE tf.tenant_id = %s "
            "GROUP BY fa.class_id",
            (str(tenant_id),),
        )
        return {int(row["class_id"]): int(row["n"]) for row in rows}

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

    # Mesmo universo do export de treino (_fetch_annotations,
    # versioning_v2.py:105): só anotação HUMANA (source='manual') ou
    # pré-anotação APROVADA (reviewed_by NOT NULL); frame anotado, não excluído
    # na curadoria (110), classe não arquivada (110). Decodifica o offset de
    # namespace de classe (class_namespace.TENANT_CLASS_ID_OFFSET = 100000)
    # exatamente como o export. Fragmento ESTÁTICO — os únicos valores de
    # request (tenant_id, module_code) entram por %s, nunca por f-string.
    # "Tela que conta diferente do export mente."
    _COVERAGE_UNIVERSE = """
          FROM frame_annotations a
          JOIN yolo_classes c
            ON c.id = CASE WHEN a.class_id >= 100000
                            THEN a.class_id - 100000 ELSE a.class_id END
          JOIN training_frames tf ON tf.id = a.frame_id
     LEFT JOIN public.cameras pc
            ON pc.id = tf.camera_id AND pc.tenant_id = tf.tenant_id
         WHERE tf.tenant_id = %s AND tf.module_code = %s
           AND tf.is_annotated = TRUE AND tf.curation_status <> 'excluida'
           AND c.archived_at IS NULL
           AND (COALESCE(a.source, 'manual') = 'manual' OR a.reviewed_by IS NOT NULL)
    """

    def get_coverage_matrix(
        self, tenant_id: str, module_code: str = "epi"
    ) -> dict[str, Any]:
        """Matriz classe × câmera de anotações, contada IGUAL ao export.

        Devolve blocos crus (o serviço de cobertura monta metas/ranking):
          - classes: classes ativas do tenant+módulo (archived_at IS NULL),
            na ordem do anotador — inclui classe com ZERO anotação.
          - cameras: universo de câmeras (public.cameras do tenant) + frames
            disponíveis para anotar (não anotados) — inclui câmera com ZERO.
          - cells: por classe × câmera → caixas e imagens (só células > 0).
          - camera_rollup: por câmera → caixas, imagens, classes distintas,
            dias distintos, última anotação.
          - provenance: por classe → humana × auto_aprovada.
          - orphans: caixas cujo class_id não resolve (descartadas em silêncio
            pelo export — aqui a tela AVISA, migration 103).
          - archived_excluded: classes arquivadas com caixas (confirmam que
            NÃO vazam para a contagem).
          - totals: caixas e imagens no universo do export (deve bater).

        LEFT JOIN em public.cameras (não INNER): frame sem câmera resolvível
        continua na contagem → o total permanece idêntico ao export, e a caixa
        cai no balde '(sem câmera)' em vez de sumir.
        """
        p = (str(tenant_id), module_code)

        cells = self._execute(
            "SELECT c.id AS class_id, c.name AS class_name, c.color, "
            "c.display_order, tf.camera_id, "
            "COALESCE(pc.name, '(sem câmera)') AS camera_name, "
            "COUNT(*) AS boxes, COUNT(DISTINCT a.frame_id) AS images "
            + self._COVERAGE_UNIVERSE
            + " GROUP BY c.id, c.name, c.color, c.display_order, "
            "tf.camera_id, pc.name",
            p,
        )
        camera_rollup = self._execute(
            "SELECT tf.camera_id, COALESCE(pc.name, '(sem câmera)') AS camera_name, "
            "COUNT(*) AS boxes, COUNT(DISTINCT a.frame_id) AS images, "
            "COUNT(DISTINCT c.id) AS classes, "
            "COUNT(DISTINCT (COALESCE(tf.captured_at, tf.created_at)::date)) AS days, "
            "MAX(a.created_at) AS last_annotation "
            + self._COVERAGE_UNIVERSE
            + " GROUP BY tf.camera_id, pc.name",
            p,
        )
        provenance = self._execute(
            "SELECT c.id AS class_id, "
            "COUNT(*) FILTER (WHERE COALESCE(a.source, 'manual') = 'manual') AS humana, "
            "COUNT(*) FILTER (WHERE COALESCE(a.source, 'manual') <> 'manual') AS auto_aprovada "
            + self._COVERAGE_UNIVERSE
            + " GROUP BY c.id",
            p,
        )
        totals = self._execute_one(
            "SELECT COUNT(*) AS boxes, COUNT(DISTINCT a.frame_id) AS images "
            + self._COVERAGE_UNIVERSE,
            p,
        )
        classes = self._execute(
            "SELECT id AS class_id, name AS class_name, color, display_order "
            "FROM yolo_classes "
            "WHERE tenant_id = %s AND module_code = %s AND archived_at IS NULL "
            "ORDER BY display_order NULLS LAST, id",
            p,
        )
        cameras = self._execute(
            "SELECT pc.id AS camera_id, pc.name AS camera_name, pc.is_active, "
            "COUNT(tf.id) FILTER "
            "(WHERE NOT tf.is_annotated AND COALESCE(tf.curation_status, '') <> 'excluida') "
            "AS available_frames "
            "FROM public.cameras pc "
            "LEFT JOIN training_frames tf "
            "ON tf.camera_id = pc.id AND tf.tenant_id = pc.tenant_id "
            "AND tf.module_code = %s "
            "WHERE pc.tenant_id = %s "
            "GROUP BY pc.id, pc.name, pc.is_active",
            (module_code, str(tenant_id)),
        )
        orphans = self._execute(
            "SELECT a.class_id, a.class_name, "
            "COALESCE(pc.name, '(sem câmera)') AS camera_name, COUNT(*) AS boxes "
            "FROM frame_annotations a "
            "JOIN training_frames tf ON tf.id = a.frame_id "
            "LEFT JOIN public.cameras pc "
            "ON pc.id = tf.camera_id AND pc.tenant_id = tf.tenant_id "
            "LEFT JOIN yolo_classes c "
            "ON c.id = CASE WHEN a.class_id >= 100000 "
            "THEN a.class_id - 100000 ELSE a.class_id END "
            "WHERE tf.tenant_id = %s AND tf.module_code = %s "
            "AND tf.is_annotated = TRUE AND tf.curation_status <> 'excluida' "
            "AND c.id IS NULL "
            "GROUP BY a.class_id, a.class_name, pc.name",
            p,
        )
        archived_excluded = self._execute(
            "SELECT c.name AS class_name, COUNT(*) AS boxes "
            "FROM frame_annotations a "
            "JOIN yolo_classes c "
            "ON c.id = CASE WHEN a.class_id >= 100000 "
            "THEN a.class_id - 100000 ELSE a.class_id END "
            "JOIN training_frames tf ON tf.id = a.frame_id "
            "WHERE tf.tenant_id = %s AND tf.module_code = %s "
            "AND tf.is_annotated = TRUE AND tf.curation_status <> 'excluida' "
            "AND c.archived_at IS NOT NULL "
            "GROUP BY c.name",
            p,
        )
        return {
            "classes": classes,
            "cameras": cameras,
            "cells": cells,
            "camera_rollup": camera_rollup,
            "provenance": provenance,
            "orphans": orphans,
            "archived_excluded": archived_excluded,
            "totals": totals or {"boxes": 0, "images": 0},
        }

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

    _PATCHABLE_CLASS_COLUMNS = ("name", "color", "display_order")

    def patch_class(
        self,
        class_id: int,
        tenant_id: str,
        fields: dict[str, Any],
    ) -> "dict[str, Any] | None":
        """Atualiza campos parciais de yolo_classes no escopo do tenant
        (PATCH /classes/<id>, migration 110).

        `fields` é um subconjunto de {name, color, display_order, archived}
        já validado pelo service — só as chaves PRESENTES são atualizadas
        (chave ausente = não mexe na coluna). `archived` (bool) mapeia para
        archived_at = NOW()/NULL. Colunas vêm de uma whitelist fixa
        (_PATCHABLE_CLASS_COLUMNS, não de string do usuário); valores sempre
        via parâmetro (%s). Retorna None se a classe não é do tenant (nunca
        toca em module_classes — catálogo global sem contraparte aqui).
        """
        set_parts: list[str] = []
        params: list[Any] = []
        for col in self._PATCHABLE_CLASS_COLUMNS:
            if col in fields:
                set_parts.append(f"{col} = %s")
                params.append(fields[col])
        if "archived" in fields:
            set_parts.append("archived_at = NOW()" if fields["archived"] else "archived_at = NULL")

        if not set_parts:
            return self.get_class_for_tenant(class_id, tenant_id)

        params.extend([class_id, str(tenant_id)])
        return self._execute_mutation(
            f"UPDATE yolo_classes SET {', '.join(set_parts)} "
            "WHERE id = %s AND tenant_id = %s RETURNING *",
            tuple(params),
        )

    def count_annotations_for_class(self, class_id: int) -> int:
        """Conta anotações em frame_annotations que referenciam class_id.

        ATENÇÃO: `class_id` aqui é o valor EFETIVAMENTE gravado em
        frame_annotations.class_id — para classe de catálogo (module_classes)
        é o índice 0-based do módulo; para classe custom do tenant
        (yolo_classes) é o id NAMESPACED (class_namespace.
        namespace_tenant_class_id), não o id cru da tabela (migration 103
        removeu a FK; frame_annotations nunca referenciou o id cru de
        yolo_classes — ver docstring da 103). Callers de classe do tenant
        devem passar o id namespaced (ver TenantClassService.delete_class).
        """
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
        referenced_class_id: "int | None" = None,
    ) -> int:
        """Deleta classe SEM anotações vinculadas (guarda NOT EXISTS).

        A guarda no SQL fecha a janela TOCTOU entre o count e o delete.
        Retorna rowcount (0 = não deletou).

        `referenced_class_id`: id efetivamente usado em frame_annotations.
        class_id para esta classe — NAMESPACED para classe do tenant (ver
        count_annotations_for_class). Default None cai no `class_id` cru
        (comportamento legado) — SUBESTIMA o uso real de uma classe do
        tenant, então callers de classe do tenant devem sempre informar o
        valor namespaced (TenantClassService.delete_class já faz isso).
        """
        check_id = referenced_class_id if referenced_class_id is not None else class_id
        if user_id is not None:
            return self._execute_mutation_no_return(
                "DELETE FROM yolo_classes c WHERE c.id = %s "
                "AND (c.tenant_id = %s OR (c.tenant_id IS NULL AND c.user_id = %s)) "
                "AND NOT EXISTS ("
                "SELECT 1 FROM frame_annotations a WHERE a.class_id = %s)",
                (class_id, str(tenant_id), str(user_id), check_id),
            )
        return self._execute_mutation_no_return(
            "DELETE FROM yolo_classes c WHERE c.id = %s AND c.tenant_id = %s "
            "AND NOT EXISTS ("
            "SELECT 1 FROM frame_annotations a WHERE a.class_id = %s)",
            (class_id, str(tenant_id), check_id),
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
            # Proveniência das caixas que este save NÃO mexeu (#536). O
            # delete-then-insert reescrevia TODA linha como source='manual':
            # abrir o estúdio num frame de proposta aceita e salvar sem tocar
            # em nada convertia geometria do MODELO em "desenhada por humano",
            # e o gate de procedência do treino perdia a única informação que
            # ele usa para decidir. Medido no RVB antes do fix: 403 caixas
            # 'manual' com coordenadas idênticas às de uma proposta do mesmo
            # frame (v10_base 195, v9_best 187, propositor 21).
            #
            # Caixa que o humano não tocou tem coordenada IDÊNTICA — é essa a
            # definição de "não tocou". Casar por igualdade exata (após
            # arredondar o ruído de float) mantém a proveniência antiga; caixa
            # movida, redimensionada ou nova entra como manual, que é o certo:
            # aí a geometria passou pela mão de gente.
            cur.execute(
                "SELECT class_name, x_center, y_center, width, height, "
                "       source, reviewed_by, proposal_batch_id, "
                "       proposal_model_id, proposal_confidence "
                "  FROM frame_annotations WHERE frame_id = %s",
                (str(frame_id),),
            )
            anterior = {
                _chave_geometrica(r[0], r[1], r[2], r[3], r[4]): r[5:]
                for r in cur.fetchall()
            }

            cur.execute(
                "DELETE FROM frame_annotations WHERE frame_id = %s",
                (str(frame_id),),
            )
            count = 0
            for ann in annotations:
                herdado = anterior.get(_chave_geometrica(
                    ann["class_name"], ann["x_center"], ann["y_center"],
                    ann["width"], ann["height"],
                ))
                source, reviewed_by, lote, modelo, confianca = (
                    herdado if herdado else ("manual", None, None, None, None)
                )
                cur.execute(
                    "INSERT INTO frame_annotations "
                    "(frame_id, class_id, x_center, y_center, width, height, "
                    "class_name, module_code, source, created_by, reviewed_by, "
                    "proposal_batch_id, proposal_model_id, proposal_confidence) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        str(frame_id),
                        ann["class_id"],
                        ann["x_center"],
                        ann["y_center"],
                        ann["width"],
                        ann["height"],
                        ann["class_name"],
                        ann["module_code"],
                        source,
                        created_by,
                        reviewed_by,
                        lote,
                        modelo,
                        confianca,
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

        migration 111: estampa training_frames.pre_annotation_review_status
        = 'accepted' NA MESMA TRANSAÇÃO dos INSERTs — fecha a fila de
        aprovação (?pending_review=true em list_images_filtered) no mesmo
        commit que criou as anotações, sem round-trip extra e sem janela
        onde o frame apareceria "aprovado" (tem frame_annotations) mas
        ainda "pendente" (review_status IS NULL) para outro request lendo
        entre as duas operações.
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
            if count > 0:
                cur.execute(
                    "UPDATE training_frames "
                    "SET pre_annotation_review_status = 'accepted', "
                    "    pre_annotation_reviewed_by = %s, "
                    "    pre_annotation_reviewed_at = NOW() "
                    "WHERE id = %s",
                    (str(user_id), str(frame_id)),
                )
            return count

        return self._execute_in_transaction(_transaction)

    # ------------------------------------------------------------------
    # Propagação semeada (migration 112) — sementes DEFAULT do pool
    # ------------------------------------------------------------------

    def get_manual_annotations_for_frames(
        self, frame_ids: "list[UUID | str]"
    ) -> "list[dict[str, Any]]":
        """Anotações humanas (`source='manual'`) dos frames dados — usado
        pra resolver as sementes DEFAULT da propagação semeada quando o
        caller não informa `seed_frame_ids` explícito: "todas as anotações
        humanas dos frames dentro do MESMO critério do pool" (mission da
        task). `frame_id` é retornado como string (não indexado por classe
        aqui — o caller agrupa). `::uuid[]` obrigatório (mesmo achado de
        `frame_repository.update_curation_status`)."""
        if not frame_ids:
            return []
        return self._execute(
            "SELECT frame_id, class_id, class_name, x_center, y_center, "
            "width, height "
            "FROM frame_annotations "
            "WHERE frame_id = ANY(%s::uuid[]) AND source = 'manual' "
            "ORDER BY frame_id, created_at",
            ([str(fid) for fid in frame_ids],),
        )
