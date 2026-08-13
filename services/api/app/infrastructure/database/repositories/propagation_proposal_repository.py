"""Repository: propagation_proposals (migration 118 — ledger por-proposta).

Fonte da verdade por-proposta das pré-anotações de propagação/busca. O JSONB
legado `training_frames.pre_annotations` passa a ser uma PROJEÇÃO DERIVADA —
`_rebuild_projection` reconstrói (jsonb_agg das linhas ainda 'pending' do
frame) a cada mutação de linha, na MESMA transação. Isso mantém a fila
legada (`FrameRepository._PENDING_PROPOSAL_CONDITION`, `list_images_
filtered`, provenance='proposta', estúdio de anotação) funcionando sem
alteração — ela só lê o JSONB, nunca esta tabela diretamente.

Segurança: todo método de escopo múltiplo escopa por `tenant_id` no próprio
WHERE (ADR-0017, C-01); item único inexistente/cross-tenant → None (o
handler converte pra 404, nunca 403 — nunca vaza existência).
"""
import json
from typing import Any
from uuid import UUID

from app.infrastructure.database.repositories.base import BaseRepository


class PropagationProposalRepository(BaseRepository):
    """Queries SQL para public.propagation_proposals."""

    # Whitelist de colunas ORDER BY — nunca interpolar `sort`/`order` crus
    # do request (viriam de querystring do usuário).
    _SORT_COLUMNS: "dict[str, str]" = {
        "confidence": "pp.confidence",
        "class_name": "pp.class_name",
        "created_at": "pp.created_at",
    }
    _ORDER_DIRECTIONS: "dict[str, str]" = {"asc": "ASC", "desc": "DESC"}

    # Reconstrução da projeção JSONB (contrato — usar em TODA mutação de
    # linha, na MESMA transação do UPDATE/DELETE/INSERT que a motivou).
    # Quando não sobra nenhuma linha 'pending' do frame, pre_annotations
    # vira '[]' e o frame sai sozinho da fila legada (_PENDING_PROPOSAL_
    # CONDITION), sem precisar tocar pre_annotation_review_status.
    _REBUILD_PROJECTION_SQL = (
        "UPDATE training_frames tf SET pre_annotations = COALESCE(("
        "  SELECT jsonb_agg(jsonb_build_object("
        "    'bbox', pp.bbox, 'class', pp.class_name, 'confidence', pp.confidence"
        "  ) ORDER BY pp.confidence DESC NULLS LAST, pp.id) "
        "  FROM propagation_proposals pp "
        "  WHERE pp.frame_id = tf.id AND pp.status = 'pending'"
        "), '[]'::jsonb) "
        "WHERE tf.id = ANY(%s::uuid[]) AND tf.tenant_id = %s"
    )

    def _rebuild_projection(
        self, cur: Any, frame_ids: "list[UUID | str]", tenant_id: "UUID | str",
    ) -> None:
        """Reconstrói pre_annotations dos frames dados — SÓ dentro de uma
        transação já aberta (`cur` de `_execute_in_transaction`), nunca
        standalone (sempre acompanha a mutação de linha que a motivou)."""
        if not frame_ids:
            return
        cur.execute(
            self._REBUILD_PROJECTION_SQL,
            ([str(fid) for fid in frame_ids], str(tenant_id)),
        )

    def _build_conditions(
        self,
        tenant_id: "UUID | str",
        *,
        status: "str | None" = None,
        job_id: "UUID | str | None" = None,
        class_names: "list[str] | None" = None,
        confidence_min: "float | None" = None,
        confidence_max: "float | None" = None,
        camera_ids: "list[UUID | str] | None" = None,
    ) -> "tuple[list[str], list[Any]]":
        """Fragmentos WHERE whitelisted + params — reusado por list_proposals
        (contagem/página) e pela faceta by_class (mesmo filtro, sem paginar).
        Só fragmentos estáticos entram na string; todo valor do usuário vai
        em params (%s)."""
        conditions = ["pp.tenant_id = %s"]
        params: "list[Any]" = [str(tenant_id)]

        if status is not None:
            conditions.append("pp.status = %s")
            params.append(status)
        if job_id is not None:
            conditions.append("pp.job_id = %s")
            params.append(str(job_id))
        if class_names:
            conditions.append("pp.class_name = ANY(%s)")
            params.append([str(c) for c in class_names])
        if confidence_min is not None:
            conditions.append("pp.confidence >= %s")
            params.append(confidence_min)
        if confidence_max is not None:
            conditions.append("pp.confidence <= %s")
            params.append(confidence_max)
        if camera_ids:
            conditions.append("tf.camera_id = ANY(%s::uuid[])")
            params.append([str(c) for c in camera_ids])

        return conditions, params

    def list_proposals(
        self,
        tenant_id: "UUID | str",
        *,
        status: str = "pending",
        job_id: "UUID | str | None" = None,
        class_names: "list[str] | None" = None,
        confidence_min: "float | None" = None,
        confidence_max: "float | None" = None,
        camera_ids: "list[UUID | str] | None" = None,
        sort: str = "confidence",
        order: str = "asc",
        page: int = 1,
        page_size: int = 60,
    ) -> "dict[str, Any]":
        """Grade de triagem paginada — JOIN training_frames (r2_key/width/
        height/camera_id, sem presigned URL: isso é responsabilidade do
        handler, mesmo padrão de list_training_images_handler).

        `facets.by_class` é a contagem PENDING por classe no MESMO escopo
        (job_id/confidence/camera_ids), mas SEM paginar e SEM filtrar por
        `class_names` — a própria dimensão da faceta nunca filtra por si
        mesma (mesmo princípio de FrameRepository.get_facets: escolher uma
        classe não pode zerar a contagem das demais na UI) e sempre conta
        'pending' independente do `status` pedido pro grid (é o contador
        "quanto falta triar" da tela).
        """
        offset = (max(1, page) - 1) * page_size

        conditions, params = self._build_conditions(
            tenant_id,
            status=status,
            job_id=job_id,
            class_names=class_names,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            camera_ids=camera_ids,
        )
        where = " AND ".join(conditions)

        count_row = self._execute_one(
            "SELECT COUNT(*) AS total FROM propagation_proposals pp "
            "JOIN training_frames tf ON tf.id = pp.frame_id "
            f"WHERE {where}",
            tuple(params),
        )
        total = int(count_row["total"]) if count_row else 0

        sort_col = self._SORT_COLUMNS.get(sort, self._SORT_COLUMNS["confidence"])
        order_dir = self._ORDER_DIRECTIONS.get(order, "ASC")
        nulls = " NULLS LAST" if sort_col == "pp.confidence" else ""

        rows = self._execute(
            "SELECT pp.id, pp.frame_id, pp.job_id, pp.class_name, pp.confidence, "
            "pp.bbox, pp.status, pp.source, "
            "tf.r2_key, tf.width, tf.height, tf.camera_id "
            "FROM propagation_proposals pp "
            "JOIN training_frames tf ON tf.id = pp.frame_id "
            f"WHERE {where} "
            f"ORDER BY {sort_col} {order_dir}{nulls}, pp.id "
            "LIMIT %s OFFSET %s",
            tuple(params + [page_size, offset]),
        )

        proposals = [
            {
                "id": str(row["id"]),
                "frame_id": str(row["frame_id"]),
                "job_id": str(row["job_id"]) if row.get("job_id") else None,
                "class_name": row["class_name"],
                "confidence": row["confidence"],
                "bbox": row["bbox"],
                "status": row["status"],
                "source": row["source"],
                "frame": {
                    "r2_key": row.get("r2_key"),
                    "width": row.get("width"),
                    "height": row.get("height"),
                    "camera_id": str(row["camera_id"]) if row.get("camera_id") else None,
                },
            }
            for row in rows
        ]

        facet_conditions, facet_params = self._build_conditions(
            tenant_id,
            status="pending",
            job_id=job_id,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            camera_ids=camera_ids,
        )
        facet_where = " AND ".join(facet_conditions)
        facet_rows = self._execute(
            "SELECT pp.class_name, COUNT(*) AS count "
            "FROM propagation_proposals pp "
            "JOIN training_frames tf ON tf.id = pp.frame_id "
            f"WHERE {facet_where} "
            "GROUP BY pp.class_name ORDER BY count DESC",
            tuple(facet_params),
        )
        by_class = [
            {"class_name": r["class_name"], "count": int(r["count"])} for r in facet_rows
        ]

        return {
            "proposals": proposals,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
            "facets": {"by_class": by_class},
        }

    def reject_batch(
        self,
        tenant_id: "UUID | str",
        reviewed_by: "UUID | str",
        *,
        reason: str,
        proposal_ids: "list[UUID | str] | None" = None,
        frame_ids: "list[UUID | str] | None" = None,
        job_id: "UUID | str | None" = None,
        class_names: "list[str] | None" = None,
        confidence_lt: "float | None" = None,
    ) -> "dict[str, Any]":
        """Rejeita em lote as propostas PENDING que casam o AND de todos os
        filtros dados, tenant-scoped, numa única transação — depois
        reconstrói a projeção de cada frame afetado.

        Guarda defensiva (backstop — o handler já valida isso ANTES de
        chamar, "nunca rejeitar tudo por acidente"): sem NENHUM filtro além
        de tenant/status, recusa com ValueError em vez de rejeitar a fila
        inteira do tenant silenciosamente.
        """
        conditions = ["tenant_id = %s", "status = 'pending'"]
        params: "list[Any]" = [str(tenant_id)]

        if proposal_ids:
            conditions.append("id = ANY(%s::uuid[])")
            params.append([str(i) for i in proposal_ids])
        if frame_ids:
            conditions.append("frame_id = ANY(%s::uuid[])")
            params.append([str(i) for i in frame_ids])
        if job_id is not None:
            conditions.append("job_id = %s")
            params.append(str(job_id))
        if class_names:
            conditions.append("class_name = ANY(%s)")
            params.append([str(c) for c in class_names])
        if confidence_lt is not None:
            conditions.append("confidence < %s")
            params.append(confidence_lt)

        if len(conditions) == 2:
            raise ValueError(
                "reject_batch exige ao menos um filtro de escopo "
                "(proposal_ids, frame_ids, job_id, class_names ou confidence_lt)"
            )

        where = " AND ".join(conditions)

        def _txn(conn: Any, cur: Any) -> "dict[str, Any]":  # noqa: ARG001
            cur.execute(
                "UPDATE propagation_proposals SET status = 'rejected', "
                "reject_reason = %s, reviewed_by = %s, reviewed_at = NOW() "
                f"WHERE {where} "
                "RETURNING frame_id",
                tuple([reason, str(reviewed_by), *params]),
            )
            rows = cur.fetchall()
            affected_frames = sorted({str(r["frame_id"]) for r in rows})
            self._rebuild_projection(cur, affected_frames, tenant_id)
            return {
                "rejected_count": len(rows),
                "affected_frame_count": len(affected_frames),
                "affected_frames": affected_frames,
            }

        return self._execute_in_transaction(_txn)

    def reject_one(
        self,
        tenant_id: "UUID | str",
        reviewed_by: "UUID | str",
        proposal_id: "UUID | str",
        reason: str = "selection",
    ) -> "dict[str, Any] | None":
        """Rejeita uma única proposta PENDING do tenant (grade: X). None se
        não existe, é de outro tenant, ou já não está mais pending — o
        handler converte pra 404 (C-01, nunca vaza qual dos casos é)."""

        def _txn(conn: Any, cur: Any) -> "dict[str, Any] | None":  # noqa: ARG001
            cur.execute(
                "UPDATE propagation_proposals SET status = 'rejected', "
                "reject_reason = %s, reviewed_by = %s, reviewed_at = NOW() "
                "WHERE id = %s AND tenant_id = %s AND status = 'pending' "
                "RETURNING id, frame_id, status",
                (reason, str(reviewed_by), str(proposal_id), str(tenant_id)),
            )
            row = cur.fetchone()
            if row is None:
                return None
            self._rebuild_projection(cur, [row["frame_id"]], tenant_id)
            return dict(row)

        return self._execute_in_transaction(_txn)

    def get_proposal(
        self, tenant_id: "UUID | str", proposal_id: "UUID | str",
    ) -> "dict[str, Any] | None":
        """Busca uma proposta por id, tenant-scoped, com module_code do
        frame hospedeiro (usado pelo resolvedor de class_id do accept —
        AnnotationService.accept_proposal). None = inexistente ou de outro
        tenant (C-01, sem distinção)."""
        return self._execute_one(
            "SELECT pp.*, tf.module_code "
            "FROM propagation_proposals pp "
            "JOIN training_frames tf ON tf.id = pp.frame_id "
            "WHERE pp.id = %s AND pp.tenant_id = %s",
            (str(proposal_id), str(tenant_id)),
        )

    def mark_accepted(
        self,
        tenant_id: "UUID | str",
        proposal_id: "UUID | str",
        status: str,
        reviewed_by: "UUID | str",
    ) -> "dict[str, Any] | None":
        """Estampa 'accepted'/'corrected' numa proposta PENDING e reconstrói
        a projeção do frame — chamado pelo service DEPOIS de resolver
        class_id e ANTES do INSERT em frame_annotations (accept_proposal),
        pra nunca gravar uma anotação órfã de uma proposta que uma corrida
        concorrente já resolveu (None aqui = já não estava mais pending)."""

        def _txn(conn: Any, cur: Any) -> "dict[str, Any] | None":  # noqa: ARG001
            cur.execute(
                "UPDATE propagation_proposals SET status = %s, "
                "reviewed_by = %s, reviewed_at = NOW() "
                "WHERE id = %s AND tenant_id = %s AND status = 'pending' "
                "RETURNING id, frame_id, status",
                (status, str(reviewed_by), str(proposal_id), str(tenant_id)),
            )
            row = cur.fetchone()
            if row is None:
                return None
            self._rebuild_projection(cur, [row["frame_id"]], tenant_id)
            return dict(row)

        return self._execute_in_transaction(_txn)

    def replace_frame_proposals(
        self,
        frame_id: "UUID | str",
        tenant_id: "UUID | str",
        job_id: "UUID | str | None",
        proposals: "list[dict[str, Any]]",
        source: str = "propagation",
    ) -> int:
        """Sincroniza as linhas do ledger com o payload que `apply_
        propagation_proposals`/`append_pre_annotations` acabou de gravar no
        JSONB do frame (propagation_handlers.py::propagation_callback_
        handler) — DELETE das linhas 'pending' antigas do frame + INSERT das
        novas. NUNCA apaga linha já 'accepted'/'rejected'/'corrected' (dado
        de avaliação permanente). Standalone (própria transação) — chamado
        1x por frame no loop do callback, mesmo padrão de apply_propagation_
        proposals. Não reconstrói a projeção: o JSONB já É exatamente este
        payload (apply_propagation_proposals faz REPLACE, não merge)."""

        def _txn(conn: Any, cur: Any) -> int:  # noqa: ARG001
            cur.execute(
                "DELETE FROM propagation_proposals "
                "WHERE frame_id = %s AND tenant_id = %s AND status = 'pending'",
                (str(frame_id), str(tenant_id)),
            )
            for idx, p in enumerate(proposals):
                cur.execute(
                    "INSERT INTO propagation_proposals "
                    "(tenant_id, frame_id, job_id, source, class_name, "
                    "confidence, bbox, proposal_index, status) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, 'pending')",
                    (
                        str(tenant_id),
                        str(frame_id),
                        str(job_id) if job_id else None,
                        source,
                        p.get("class"),
                        p.get("confidence"),
                        json.dumps(p.get("bbox")),
                        idx,
                    ),
                )
            return len(proposals)

        return self._execute_in_transaction(_txn)

    def mark_frame_rows_status(
        self,
        frame_id: "UUID | str",
        tenant_id: "UUID | str",
        status: str,
        reviewed_by: "UUID | str | None",
        reason: "str | None" = None,
    ) -> int:
        """Sync do estúdio legado (whole-frame): marca TODAS as linhas
        'pending' do frame como accepted/rejected e reconstrói a projeção —
        usado por FrameRepository.mark_pre_annotation_review e
        AnnotationRepository.accept_pre_annotations pra manter o ledger
        por-proposta (migration 118) em dia com o veredito por-frame
        (migration 111), senão a rejeição em lote por classe/confiança da
        grade nova ficaria cega pras propostas resolvidas pelo caminho
        antigo. Retorna quantas linhas foram marcadas."""

        def _txn(conn: Any, cur: Any) -> int:  # noqa: ARG001
            cur.execute(
                "UPDATE propagation_proposals SET status = %s, "
                "reviewed_by = %s, reviewed_at = NOW(), reject_reason = %s "
                "WHERE frame_id = %s AND tenant_id = %s AND status = 'pending'",
                (
                    status,
                    str(reviewed_by) if reviewed_by else None,
                    reason,
                    str(frame_id),
                    str(tenant_id),
                ),
            )
            count = cur.rowcount
            if count > 0:
                self._rebuild_projection(cur, [frame_id], tenant_id)
            return count

        return self._execute_in_transaction(_txn)
