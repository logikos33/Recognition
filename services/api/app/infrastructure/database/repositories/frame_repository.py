"""Repository: Training Frames."""
import json
from datetime import date, datetime
from itertools import zip_longest
from typing import Any
from uuid import UUID

from app.constants import FrameSource
from app.infrastructure.database.repositories.base import BaseRepository

_INSERT_COLUMNS = (
    "video_id, frame_number, filename, timestamp_seconds, source, r2_key, "
    "camera_id, recorder_id, width, height, model_confidence, captured_at, "
    "tenant_id, module_code"
)

# tenant_id NUNCA pode nascer NULL silenciosamente: as queries de auto-training
# e active-learning filtram WHERE tenant_id = %s e linhas órfãs ficam
# invisíveis. Fallback: explícito → tenant do user → tenant do dono do vídeo.
_TENANT_COALESCE = (
    "COALESCE(%(tenant_id)s::uuid, "
    "(SELECT tenant_id FROM users WHERE id = %(user_id)s::uuid), "
    "(SELECT u.tenant_id FROM training_videos v "
    "JOIN users u ON u.id = v.user_id WHERE v.id = %(video_id)s::uuid))"
)


class FrameRepository(BaseRepository):
    """Queries SQL para tabela training_frames."""

    def create(
        self,
        video_id: UUID | None,
        frame_number: int,
        filename: str,
        timestamp_seconds: float | None = None,
        *,
        source: str = FrameSource.VIDEO,
        r2_key: str | None = None,
        camera_id: UUID | None = None,
        recorder_id: UUID | None = None,
        width: int | None = None,
        height: int | None = None,
        model_confidence: float | None = None,
        captured_at: datetime | None = None,
        tenant_id: UUID | str | None = None,
        module_code: str | None = None,
        user_id: UUID | str | None = None,
    ) -> dict[str, Any]:
        """Cria registro de frame (multi-fonte desde migration 094).

        video_id é opcional (frames de upload/auto-captura/NVR não têm vídeo pai).
        Defaults retrocompatíveis: callers legados (video_id, frame_number,
        filename, timestamp_seconds) continuam funcionando — source='video',
        r2_key=filename (chave R2 legada), module_code='epi' (default do schema).
        tenant_id cai para o tenant do user_id ou do dono do vídeo quando não
        informado (linha com tenant NULL é invisível às queries tenant-scoped).
        """
        return self._execute_mutation(
            f"INSERT INTO training_frames ({_INSERT_COLUMNS}) "
            "VALUES (%(video_id)s, %(frame_number)s, %(filename)s, "
            "%(timestamp_seconds)s, %(source)s, %(r2_key)s, %(camera_id)s, "
            f"%(recorder_id)s, %(width)s, %(height)s, %(model_confidence)s, "
            f"%(captured_at)s, {_TENANT_COALESCE}, "
            "COALESCE(%(module_code)s, 'epi')) RETURNING *",
            {
                "video_id": str(video_id) if video_id else None,
                "frame_number": frame_number,
                "filename": filename,
                "timestamp_seconds": timestamp_seconds,
                "source": str(source),
                "r2_key": r2_key or filename,
                "camera_id": str(camera_id) if camera_id else None,
                "recorder_id": str(recorder_id) if recorder_id else None,
                "width": width,
                "height": height,
                "model_confidence": model_confidence,
                "captured_at": captured_at,
                "tenant_id": str(tenant_id) if tenant_id else None,
                "user_id": str(user_id) if user_id else None,
                "module_code": module_code,
            },
        )  # type: ignore[return-value]

    def create_bulk(self, frames: list[dict[str, Any]]) -> int:
        """Insere múltiplos frames. Retorna count.

        Cada dict precisa de frame_number e filename; demais chaves são
        opcionais com os mesmos defaults de create(). executemany com
        placeholders nomeados exige lista de DICTS (não tuplas) — bug
        latente corrigido (antes: [(f,) for f in frames]).
        """
        rows = [self._with_bulk_defaults(f) for f in frames]
        return self._execute_many(
            f"INSERT INTO training_frames ({_INSERT_COLUMNS}) "
            "VALUES (%(video_id)s, %(frame_number)s, %(filename)s, "
            "%(timestamp_seconds)s, %(source)s, %(r2_key)s, %(camera_id)s, "
            "%(recorder_id)s, %(width)s, %(height)s, %(model_confidence)s, "
            f"%(captured_at)s, {_TENANT_COALESCE}, "
            "COALESCE(%(module_code)s, 'epi'))",
            rows,  # type: ignore[arg-type]
        )

    @staticmethod
    def _with_bulk_defaults(frame: dict[str, Any]) -> dict[str, Any]:
        """Normaliza um dict de frame para o INSERT bulk (defaults retrocompat)."""
        def _opt_str(value: Any) -> str | None:
            return str(value) if value else None

        return {
            "video_id": _opt_str(frame.get("video_id")),
            "frame_number": frame["frame_number"],
            "filename": frame["filename"],
            "timestamp_seconds": frame.get("timestamp_seconds"),
            "source": str(frame.get("source") or FrameSource.VIDEO),
            "r2_key": frame.get("r2_key") or frame["filename"],
            "camera_id": _opt_str(frame.get("camera_id")),
            "recorder_id": _opt_str(frame.get("recorder_id")),
            "width": frame.get("width"),
            "height": frame.get("height"),
            "model_confidence": frame.get("model_confidence"),
            "captured_at": frame.get("captured_at"),
            "tenant_id": _opt_str(frame.get("tenant_id")),
            "user_id": _opt_str(frame.get("user_id")),
            "module_code": frame.get("module_code"),
        }

    def get_by_id(self, frame_id: UUID) -> dict[str, Any] | None:
        """Busca frame por ID sem verificação de posse.

        INTERNAL USE ONLY — use get_by_id_and_user() in API handlers.
        Safe for Celery tasks where user context is not available.
        """
        return self._execute_one(
            "SELECT * FROM training_frames WHERE id = %s",
            (str(frame_id),),
        )

    def get_by_video(self, video_id: UUID) -> list[dict[str, Any]]:
        """Lista frames de um vídeo."""
        return self._execute(
            "SELECT * FROM training_frames WHERE video_id = %s "
            "ORDER BY frame_number ASC",
            (str(video_id),),
        )

    def get_next_unannotated(self, video_id: UUID) -> dict[str, Any] | None:
        """Busca próximo frame não anotado (FIFO)."""
        return self._execute_one(
            "SELECT * FROM training_frames "
            "WHERE video_id = %s AND is_annotated = FALSE "
            "ORDER BY frame_number ASC LIMIT 1",
            (str(video_id),),
        )

    def mark_annotated(self, frame_id: UUID) -> dict[str, Any] | None:
        """Marca frame como anotado."""
        return self._execute_mutation(
            "UPDATE training_frames SET is_annotated = TRUE "
            "WHERE id = %s RETURNING *",
            (str(frame_id),),
        )

    def update_quality_status(
        self,
        frame_id: UUID,
        status: str,
        scores: dict | None = None,
    ) -> "dict[str, Any] | None":
        """Atualiza quality_status e quality_scores do frame."""
        return self._execute_mutation(
            "UPDATE training_frames SET quality_status = %s, quality_scores = %s "
            "WHERE id = %s RETURNING *",
            (status, json.dumps(scores or {}), str(frame_id)),
        )

    def get_approved_by_video(self, video_id: UUID) -> "list[dict[str, Any]]":
        """Lista frames aprovados no filtro de qualidade."""
        return self._execute(
            "SELECT * FROM training_frames "
            "WHERE video_id = %s AND quality_status != 'rejected' "
            "ORDER BY frame_number ASC",
            (str(video_id),),
        )

    def count_by_status(self, video_id: UUID) -> dict[str, int]:
        """Conta frames por status de anotação."""
        rows = self._execute(
            "SELECT is_annotated, COUNT(*) as count "
            "FROM training_frames WHERE video_id = %s "
            "GROUP BY is_annotated",
            (str(video_id),),
        )
        result = {"annotated": 0, "pending": 0, "total": 0}
        for row in rows:
            if row["is_annotated"]:
                result["annotated"] = row["count"]
            else:
                result["pending"] = row["count"]
        result["total"] = result["annotated"] + result["pending"]
        return result

    # AI_NOTE: US-021 — Surface pre-annotations from JSONB for AnnotationInterface
    def get_pre_annotations(self, frame_id: UUID) -> "list[dict] | None":
        """Retorna pré-anotações DINO/SAM do frame (JSONB), ou None se não houver."""
        row = self._execute_one(
            "SELECT pre_annotations FROM training_frames WHERE id = %s",
            (str(frame_id),),
        )
        if not row:
            return None
        return row.get("pre_annotations")  # list[dict] ou None

    def get_annotated_by_video(self, video_id: UUID, user_id: UUID) -> "list[dict]":
        """Lista frames anotados de um vídeo verificando posse via user_id.

        JOIN em training_videos garante que apenas o dono do vídeo obtém resultados
        (mesmo padrão de count_validated/get_by_id_and_user). Fix P0-01.
        """
        return self._execute(
            "SELECT tf.*, "
            "  COUNT(fa.id) AS annotation_count, "
            "  tf.validated_at IS NOT NULL AS is_validated "
            "FROM training_frames tf "
            "JOIN training_videos tv ON tv.id = tf.video_id "
            "LEFT JOIN frame_annotations fa ON fa.frame_id = tf.id "
            "WHERE tf.video_id = %s AND tv.user_id = %s AND tf.is_annotated = TRUE "
            "GROUP BY tf.id "
            "ORDER BY tf.frame_number ASC",
            (str(video_id), str(user_id)),
        )

    def get_by_id_and_user(
        self, frame_id: UUID, user_id: UUID, tenant_id: "UUID | str"
    ) -> "dict | None":
        """Busca frame por ID validando posse no CONTEXTO DE TENANT da requisição.

        AI_NOTE: US-022 security fix — evita IDOR ao validar/anotar frame.

        Achado (validação E2E Fase A): o JOIN original era INNER contra
        training_videos — frames sem vídeo pai (video_id NULL, fontes
        upload/auto/nvr desde a migration 094) NUNCA batiam, então
        save_annotations/validate_frame quebravam 100% das vezes pra
        qualquer imagem enviada via upload (WS-A2). training_frames não
        tem coluna user_id própria (só tenant_id) — pra frame sem vídeo, a
        posse correta é por tenant. Frame com vídeo mantém a regra original
        (dono do vídeo) — comportamento existente preservado.

        `tenant_id` é o tenant do CONTEXTO DA REQUISIÇÃO (claim do JWT via
        get_tenant_id()), NÃO o tenant "de casa" do user_id no banco. A
        distinção importa quando um superadmin opera sob contexto assumido
        (POST /tenants/<id>/assume, tenant_context_routes.py): a identidade
        do token continua sendo o superadmin, mas o tenant efetivo é o do
        alvo. A versão anterior derivava o tenant de `(SELECT tenant_id FROM
        users WHERE id = user_id)` — o tenant de casa do superadmin — então
        todo frame sem vídeo (nvr/upload/auto) coletado sob contexto assumido
        ficava 404 no anotador, embora aparecesse na galeria (que já escopa
        por get_tenant_id() + presigned URL). Mesmo bug do live view pré-#302:
        o endpoint ignorava o contexto assumido. Agora a posse por tenant usa
        o MESMO get_tenant_id() que a galeria (list_images_filtered) e a
        coleta (nvr_extraction) usam pra tagear/filtrar — cross-tenant → None
        → 404 (C-01), sem fallback silencioso (ADR-0017).
        """
        return self._execute_one(
            "SELECT tf.* FROM training_frames tf "
            "LEFT JOIN training_videos tv ON tv.id = tf.video_id "
            "WHERE tf.id = %s AND ("
            "  tv.user_id = %s "
            "  OR (tf.video_id IS NULL AND tf.tenant_id = %s)"
            ")",
            # tenant_id None → SQL NULL (não a string 'None', que quebra o cast
            # uuid): frame sem vídeo fica inacessível sem contexto de tenant
            # (fail-closed), frame com vídeo continua via posse do dono.
            (str(frame_id), str(user_id), str(tenant_id) if tenant_id is not None else None),
        )

    def mark_validated(
        self, frame_id: UUID, user_id: UUID, tenant_id: "UUID | str"
    ) -> "dict | None":
        """Marca frame como validado por humano (posse no contexto de tenant).

        AI_NOTE: filtra por posse pra prevenir IDOR. Mesmo achado do fix em
        get_by_id_and_user: o JOIN original (`FROM training_videos tv WHERE
        tf.video_id = tv.id`) é efetivamente um INNER JOIN — frame sem
        vídeo pai (upload/auto/nvr, video_id NULL) nunca batia, então
        nenhuma imagem enviada via upload podia ser marcada como revisada.
        Frame com vídeo mantém a regra original (dono do vídeo); frame sem
        vídeo usa posse por tenant.

        `tenant_id` é o tenant do CONTEXTO DA REQUISIÇÃO (get_tenant_id()),
        não o tenant de casa do user_id — ver docstring de get_by_id_and_user
        pro racional completo (contexto assumido de superadmin, #302).
        """
        return self._execute_mutation(
            "UPDATE training_frames tf "
            "SET validated_by = %s, validated_at = NOW() "
            "WHERE tf.id = %s AND ("
            "  EXISTS (SELECT 1 FROM training_videos tv "
            "          WHERE tv.id = tf.video_id AND tv.user_id = %s) "
            "  OR (tf.video_id IS NULL AND tf.tenant_id = %s)"
            ") "
            "RETURNING tf.*",
            # tenant_id None → SQL NULL (ver get_by_id_and_user).
            (
                str(user_id),
                str(frame_id),
                str(user_id),
                str(tenant_id) if tenant_id is not None else None,
            ),
        )

    def mark_pre_annotation_review(
        self,
        frame_id: UUID,
        status: str,
        user_id: UUID,
        tenant_id: "UUID | str | None",
    ) -> "dict | None":
        """Estampa revisão de proposta de IA — aceita ou rejeita (migration 111).

        Fecha o buraco de modelo: sem isso, proposta rejeitada nunca tinha
        onde pousar e a fila de pendentes (?pending_review=true em
        list_images_filtered) não esvaziava. `status` já validado pelo
        caller (AnnotationService.review_pre_annotation) — 'accepted' ou
        'rejected'.

        Posse no próprio UPDATE (mesmo padrão de mark_validated): escopo
        por tenant do CONTEXTO da requisição, defesa em profundidade além
        do ownership check já feito via get_by_id_and_user no service.
        Idempotente — chamar de novo só reescreve os três campos (ex.:
        usuário aperta a tecla de novo por engano).

        accept_pre_annotations (aceitar sugestões tal como vieram, via
        accept-suggestions) estampa 'accepted' na MESMA transação do
        INSERT — este método cobre os outros dois caminhos do estúdio:
        REJEITAR (nunca grava caixa) e ACEITAR COM EDIÇÃO prévia (as
        caixas já foram salvas como anotação humana normal via
        /annotations; este UPDATE só fecha o registro de revisão).
        """
        return self._execute_mutation(
            "UPDATE training_frames tf "
            "SET pre_annotation_review_status = %s, "
            "    pre_annotation_reviewed_by = %s, "
            "    pre_annotation_reviewed_at = NOW() "
            "WHERE tf.id = %s AND ("
            "  EXISTS (SELECT 1 FROM training_videos tv "
            "          WHERE tv.id = tf.video_id AND tv.user_id = %s) "
            "  OR (tf.video_id IS NULL AND tf.tenant_id = %s)"
            ") "
            "RETURNING tf.*",
            # tenant_id None → SQL NULL (ver get_by_id_and_user).
            (
                status,
                str(user_id),
                str(frame_id),
                str(user_id),
                str(tenant_id) if tenant_id is not None else None,
            ),
        )

    def get_by_user_paginated(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 24,
        is_annotated: "bool | None" = None,
        order: str = "desc",
    ) -> "dict[str, Any]":
        """Lista frames do usuário com paginação e filtros.

        Usado pela galeria de imagens de treino (Tab 1).
        Filtra por user_id via JOIN em training_videos.
        """
        offset = (page - 1) * page_size

        conditions = ["tv.user_id = %s"]
        params: list[Any] = [str(user_id)]

        if is_annotated is not None:
            conditions.append("tf.is_annotated = %s")
            params.append(is_annotated)

        where = " AND ".join(conditions)
        order_dir = "DESC" if order == "desc" else "ASC"

        count_row = self._execute_one(
            "SELECT COUNT(*) AS total FROM training_frames tf "
            f"JOIN training_videos tv ON tv.id = tf.video_id WHERE {where}",
            tuple(params),
        )
        total = int(count_row["total"]) if count_row else 0

        frames = self._execute(
            "SELECT tf.id, tf.video_id, tf.frame_number, tf.filename, "
            "tf.is_annotated, tf.created_at, "
            "tv.original_filename AS video_name "
            "FROM training_frames tf "
            f"JOIN training_videos tv ON tv.id = tf.video_id WHERE {where} "
            f"ORDER BY tf.created_at {order_dir} LIMIT %s OFFSET %s",
            tuple(params + [page_size, offset]),
        )

        return {
            "frames": list(frames),
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    def count_validated(self, video_id: UUID, user_id: UUID) -> dict:
        """Conta frames validados e anotados de um vídeo (verificando posse).

        AI_NOTE: JOIN em training_videos garante que user_id é dono do vídeo.
        """
        row = self._execute_one(
            "SELECT "
            "  COUNT(*) FILTER (WHERE tf.is_annotated = TRUE) AS annotated, "
            "  COUNT(*) FILTER (WHERE tf.validated_at IS NOT NULL) AS validated, "
            "  COUNT(*) AS total "
            "FROM training_frames tf "
            "JOIN training_videos tv ON tv.id = tf.video_id "
            "WHERE tf.video_id = %s AND tv.user_id = %s",
            (str(video_id), str(user_id)),
        )
        return (
            {
                "annotated": int(row["annotated"] or 0),
                "validated": int(row["validated"] or 0),
                "total": int(row["total"] or 0),
            }
            if row
            else {"annotated": 0, "validated": 0, "total": 0}
        )

    # ------------------------------------------------------------------
    # WS-A2 — galeria multi-fonte (método APPEND-ONLY; não alterar acima)
    # ------------------------------------------------------------------

    _STATUS_CONDITIONS: "dict[str, str]" = {
        # Plano linhas 83-85 — status é COMPUTADO, sem coluna nova.
        "unlabeled": "tf.is_annotated = FALSE",
        "labeled": "(tf.is_annotated = TRUE AND tf.validated_at IS NULL)",
        "reviewed": "tf.validated_at IS NOT NULL",
    }

    # Proposta PENDENTE = pre_annotations não vazio e ainda sem veredito de
    # revisão (migration 111). Sem condição sobre frame_annotations de
    # propósito: proposta nova em frame JÁ ANOTADO continua pendente até o
    # veredito — fonte única usada pelo filtro ?pending_review=true, pelo
    # `pending_proposals_count` de cada card e pelo `total_pending_proposals`
    # do agregado, para os três números baterem sempre.
    _PENDING_PROPOSAL_CONDITION = (
        "(tf.pre_annotations IS NOT NULL "
        "AND tf.pre_annotations != '[]'::jsonb "
        "AND tf.pre_annotation_review_status IS NULL)"
    )

    # Quantas vezes a MESMA dimensão precisa se repetir para ser considerada
    # resolução de stream (= frame inteiro) e não tamanho de caixa (= recorte).
    # Ver o bloco `only_crops` em list_images_filtered.
    _FULL_FRAME_MIN_REPEATS = 50

    def list_images_filtered(
        self,
        tenant_id: "UUID | str",
        page: int = 1,
        page_size: int = 24,
        source: "str | None" = None,
        status: "str | None" = None,
        is_annotated: "bool | None" = None,
        order: str = "desc",
        camera_id: "UUID | str | None" = None,
        curation_status: "str | None" = None,
        pending_review: "bool | None" = None,
        camera_ids: "list[UUID | str] | None" = None,
        only_crops: "bool | None" = None,
        cursor: "UUID | str | None" = None,
    ) -> "dict[str, Any]":
        """Lista imagens de treino do tenant com filtros ?source=, ?status=,
        ?camera_id=, ?curation_status= (curadoria — migration 110) e
        ?pending_review= (fila de aprovação de propostas — migration 111).

        `camera_ids` (seletor multi-câmera do filtro de treinamento):
        lista de UUIDs, filtra `camera_id = ANY(...)`. Quando não-vazia tem
        PRIORIDADE sobre `camera_id` (singular, mantido por compat — quem
        já chama só com `camera_id` continua funcionando byte a byte).

        `pending_review=True` filtra frames com proposta de IA ainda sem
        veredito (pre_annotations JSONB não vazio E pre_annotation_review_
        status IS NULL) — predicado único em _PENDING_PROPOSAL_CONDITION,
        compartilhado com `pending_proposals_count`/`total_pending_
        proposals` abaixo. INDEPENDE de o frame já ter anotação humana:
        proposta nova em frame anotado também precisa de veredito (havia
        um NOT EXISTS de frame_annotations aqui que escondia exatamente
        essas propostas da fila — a propagação anunciava N propostas e a
        galeria mostrava menos frames, sem nada ter se perdido no banco).
        Uma proposta REJEITADA passa a ter pre_annotation_review_status=
        'rejected' (AnnotationService.review_pre_annotation) e sai deste
        filtro — é exatamente o buraco de modelo que a migration 111
        fecha (antes, proposta rejeitada não tinha onde pousar e a fila
        nunca esvaziava).

        Diferenças de get_by_user_paginated (mantido intacto p/ compat):
          - escopo por tenant_id (frames de upload/auto/nvr não têm vídeo
            pai, logo não têm user_id derivável — C-01 multi-tenant);
          - LEFT JOIN em training_videos (video_id pode ser NULL desde 094);
          - status computado no SELECT:
              unlabeled = NOT is_annotated
              labeled   = is_annotated AND validated_at IS NULL
              reviewed  = validated_at IS NOT NULL

        curation_status omitido → exclui frames 'excluida' por padrão (a
        curadoria em lote nunca apaga frame do banco — só some da galeria
        até ser pedido explicitamente via ?curation_status=excluida).
        curation_status informado → filtra exatamente por esse valor
        (inclusive 'excluida', se for o pedido explícito).

        Retorno com o MESMO shape de get_by_user_paginated; cada frame ganha
        campos extras (source, r2_key, width, height, status, camera_id,
        curation_status, provenance, annotation_count). WHERE é montado só
        com fragmentos estáticos whitelisted — input do usuário vai
        exclusivamente em params (%s).

        `annotation_count` (estúdio de anotação — "nº de caixas" no card da
        galeria): COUNT correlacionado de frame_annotations por frame_id
        (mesmo índice do EXISTS de provenance, bounded por page_size).

        `pending_proposals_count` ("M propostas" no card): jsonb_array_
        length(pre_annotations) quando ainda sem veredito, senão 0. Usa o
        MESMO predicado do filtro pending_review — invariante da fila: a
        soma dos cards = `total_pending_proposals` = contagem anunciada
        pela propagação no toast. `total_pending_proposals` só é computado
        com pending_review=True (fora da fila fica None — não se paga o
        parse do JSONB em toda contagem da galeria).

        `provenance` (estúdio de anotação — selo de procedência do card,
        migration 095 frame_annotations.source + migration 011
        pre_annotations JSONB, nenhuma migration nova):
          'humana'   — existe frame_annotations com source='manual'
          'aprovada' — existe frame_annotations com source='pre_annotation'
                       (sugestão da IA aceita via accept-suggestions), sem
                       nenhuma linha 'manual'
          'proposta' — sem frame_annotations, mas pre_annotations JSONB não
                       vazio (sugestão da IA ainda não revisada)
          NULL       — sem anotação e sem sugestão pendente
        EXISTS correlacionado por frame_id (chave do índice de
        frame_annotations) — custo desprezível, bounded por page_size.
        """
        offset = (max(1, page) - 1) * page_size

        # Câmera arquivada some da galeria/fila junto com o export: material
        # de câmera que saiu do reconhecimento não deve mais consumir tempo de
        # anotação nem alimentar o modelo. Frame sem camera_id (upload/vídeo)
        # não é afetado.
        conditions = [
            "tf.tenant_id = %s",
            "(tf.camera_id IS NULL OR EXISTS ("
            "  SELECT 1 FROM public.cameras cam"
            "   WHERE cam.id = tf.camera_id AND cam.is_active = TRUE))",
        ]
        params: "list[Any]" = [str(tenant_id)]

        if source is not None:
            conditions.append("tf.source = %s")
            params.append(str(source))

        if status is not None:
            status_condition = self._STATUS_CONDITIONS.get(status)
            if status_condition is None:
                raise ValueError(
                    f"status inválido: {status!r} "
                    f"(esperado: {sorted(self._STATUS_CONDITIONS)})"
                )
            conditions.append(status_condition)

        if is_annotated is not None:
            conditions.append("tf.is_annotated = %s")
            params.append(is_annotated)

        if camera_ids:
            conditions.append("tf.camera_id = ANY(%s::uuid[])")
            params.append([str(c) for c in camera_ids])
        elif camera_id is not None:
            conditions.append("tf.camera_id = %s")
            params.append(str(camera_id))

        if curation_status is not None:
            conditions.append("tf.curation_status = %s")
            params.append(str(curation_status))
        else:
            conditions.append("tf.curation_status != 'excluida'")

        if pending_review:
            conditions.append(self._PENDING_PROPOSAL_CONDITION)

        if only_crops:
            # Fila de classificação por RECORTE: o acervo mistura recorte de
            # pessoa e frame inteiro na mesma tabela, sem coluna que os separe
            # (o coletor do edge cai pro frame cheio quando o detector não está
            # pronto — collector_loop.py). Perguntar "esta pessoa está de
            # máscara?" sobre a cena inteira não tem resposta, então o frame
            # cheio não pode entrar nesta fila.
            #
            # Discriminador: frame inteiro tem a resolução do stream, então a
            # MESMA dimensão se repete muitas vezes; recorte é do tamanho da
            # caixa da pessoa, logo tem dimensão praticamente única. Hoje o
            # tenant RVB tem exatamente uma dimensão repetida (704x480, 615
            # frames) e nenhuma anotação caiu nela.
            #
            # Auto-detecta resolução de câmera nova sem deploy — não há lista
            # de resoluções hardcoded pra manter.
            #
            # ponytail: heurística por repetição de dimensão; se algum dia o
            # coletor passar a emitir recorte de tamanho fixo (letterbox pro
            # detector), ele seria excluído por engano — aí vira coluna
            # `frame_kind` gravada na ingestão (migration + backfill).
            conditions.append(
                "tf.width IS NOT NULL AND tf.height IS NOT NULL "
                "AND (tf.width, tf.height) NOT IN ("
                "  SELECT width, height FROM training_frames"
                "   WHERE tenant_id = %s AND width IS NOT NULL"
                "   GROUP BY width, height HAVING COUNT(*) >= %s)"
            )
            params.append(str(tenant_id))
            params.append(self._FULL_FRAME_MIN_REPEATS)

        # `total` conta o conjunto INTEIRO do filtro, sem o cursor: é o que
        # ele sempre significou e o que a galeria lê. Com o cursor dentro da
        # COUNT ele viraria "quantos faltam" sem avisar ninguém — armadilha
        # para o próximo consumidor de cursor.
        count_where = " AND ".join(conditions)
        count_params = tuple(params)

        if cursor is not None:
            # Paginação por CURSOR (keyset), alternativa ao OFFSET.
            #
            # OFFSET só é correto sobre conjunto imóvel. A fila de anotação
            # não é: cada veredito tira o frame do conjunto (is_annotated ou
            # curation_status) e a coleta do NVR põe frames novos no TOPO
            # (created_at DESC). A janela `OFFSET n*page_size` escorrega sobre
            # um conjunto que mudou de tamanho, e o que ficou entre a página
            # anterior e a nova NUNCA é mostrado. Medido no acervo do RVB
            # (7.081 recortes): 3.521 (49,7%) jamais chegavam ao anotador — e a
            # tela ainda anunciava "fila concluída".
            #
            # Chave composta `(created_at, id)`: `created_at` é único no acervo
            # medido, mas um empate futuro pularia linha em silêncio — o `id`
            # desempata de graça. Mesmo par do ORDER BY, senão o cursor mente.
            #
            # O cursor é o ID e o par sai de uma subconsulta, ⛔ não de texto
            # vindo do cliente. A primeira versão recebia o `created_at`
            # ecoado da resposta e isso perdia subsegundo (o Flask serializa
            # datetime em RFC 822, sem microssegundo): o corte truncado no
            # segundo pulava em silêncio as linhas do mesmo segundo — a mesma
            # família de defeito que o cursor veio consertar. Lendo a linha,
            # a comparação é exata por construção.
            #
            # Id inexistente → subconsulta NULL → comparação NULL → zero
            # linhas, e o cliente trata como fim de fila. Frame nunca é
            # apagado (curadoria só marca), então isso não acontece na prática.
            comparador = "<" if order == "desc" else ">"
            conditions.append(
                f"(tf.created_at, tf.id) {comparador} "
                "(SELECT c.created_at, c.id FROM training_frames c "
                " WHERE c.id = %s AND c.tenant_id = %s)"
            )
            params.append(str(cursor))
            params.append(str(tenant_id))

        where = " AND ".join(conditions)
        order_dir = "DESC" if order == "desc" else "ASC"

        # Agregado só na fila de aprovação: o WHERE já restringe às propostas
        # pendentes, então SUM(jsonb_array_length) basta — e fora da fila não
        # se paga o parse do JSONB em toda contagem da galeria (fica None).
        pending_sum_sql = (
            ", COALESCE(SUM(jsonb_array_length(tf.pre_annotations)), 0) "
            "AS total_pending_proposals"
            if pending_review
            else ""
        )
        count_row = self._execute_one(
            f"SELECT COUNT(*) AS total{pending_sum_sql} "
            f"FROM training_frames tf WHERE {count_where}",
            count_params,
        )
        total = int(count_row["total"]) if count_row else 0
        total_pending_proposals = (
            int(count_row["total_pending_proposals"])
            if pending_review and count_row
            else None
        )

        # Cursor e OFFSET são exclusivos: com cursor o corte já está no WHERE.
        page_tail_sql = "" if cursor is not None else " OFFSET %s"
        page_tail_params = (
            [page_size] if cursor is not None else [page_size, offset]
        )

        frames = self._execute(
            "SELECT tf.id, tf.video_id, tf.frame_number, tf.filename, "
            "tf.r2_key, tf.source, tf.width, tf.height, tf.camera_id, "
            "tf.curation_status, "
            "tf.is_annotated, tf.created_at, "
            "CASE WHEN tf.validated_at IS NOT NULL THEN 'reviewed' "
            "     WHEN tf.is_annotated THEN 'labeled' "
            "     ELSE 'unlabeled' END AS status, "
            "tv.original_filename AS video_name, "
            "CASE "
            "  WHEN EXISTS (SELECT 1 FROM frame_annotations fa "
            "               WHERE fa.frame_id = tf.id AND fa.source = 'manual') "
            "    THEN 'humana' "
            "  WHEN EXISTS (SELECT 1 FROM frame_annotations fa "
            "               WHERE fa.frame_id = tf.id AND fa.source = 'pre_annotation') "
            "    THEN 'aprovada' "
            "  WHEN tf.pre_annotations IS NOT NULL AND tf.pre_annotations != '[]'::jsonb "
            "    THEN 'proposta' "
            "  ELSE NULL "
            "END AS provenance, "
            "(SELECT COUNT(*) FROM frame_annotations fa "
            " WHERE fa.frame_id = tf.id) AS annotation_count, "
            f"CASE WHEN {self._PENDING_PROPOSAL_CONDITION} "
            "THEN jsonb_array_length(tf.pre_annotations) ELSE 0 END "
            "AS pending_proposals_count "
            "FROM training_frames tf "
            "LEFT JOIN training_videos tv ON tv.id = tf.video_id "
            f"WHERE {where} "
            f"ORDER BY tf.created_at {order_dir}, tf.id {order_dir} "
            f"LIMIT %s{page_tail_sql}",
            tuple(params + page_tail_params),
        )

        return {
            "frames": list(frames),
            "total": total,
            "total_pending_proposals": total_pending_proposals,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    # ------------------------------------------------------------------
    # Curadoria de frames (migration 110) — facetas + update em lote
    # ------------------------------------------------------------------

    def get_facets(
        self,
        tenant_id: "UUID | str",
        source: "str | None" = None,
        camera_id: "UUID | str | None" = None,
        curation_status: "str | None" = None,
        camera_ids: "list[UUID | str] | None" = None,
    ) -> "dict[str, Any]":
        """Contagens para o painel de curadoria: por câmera e por status.

        Cada faceta respeita os FILTROS ATIVOS DAS OUTRAS dimensões (padrão
        usual de busca facetada) mas nunca o próprio — senão selecionar uma
        câmera zeraria a contagem das demais câmeras na UI. Ex.: a faceta de
        câmera aplica tenant_id + source + curation_status (se informados),
        mas NUNCA filtra por camera_id/camera_ids; a faceta de status aplica
        tenant_id + source + camera_id/camera_ids (se informados), mas nunca
        por curation_status.

        `camera_ids` (seletor multi-câmera): quando não-vazia tem PRIORIDADE
        sobre `camera_id` (singular, mantido por compat) na faceta de
        status — mesma regra de prioridade de list_images_filtered.

        Faceta de câmera: nome via LEFT JOIN public.cameras (mesmo tenant —
        defesa em profundidade, além do escopo já dado por tf.tenant_id).
        Faceta de status: partição MECE de curation_status × is_annotated —
        'duvida' e 'excluida' são o próprio curation_status; frames 'active'
        se dividem em 'nao_anotado'/'anotado' pela contagem já usada na
        galeria (is_annotated).
        """
        base_conditions = ["tf.tenant_id = %s"]
        base_params: "list[Any]" = [str(tenant_id)]
        if source is not None:
            base_conditions.append("tf.source = %s")
            base_params.append(str(source))

        # --- Faceta de câmera (não filtra pela própria camera_id) ---
        camera_conditions = list(base_conditions)
        camera_params = list(base_params)
        if curation_status is not None:
            camera_conditions.append("tf.curation_status = %s")
            camera_params.append(str(curation_status))
        else:
            camera_conditions.append("tf.curation_status != 'excluida'")
        camera_where = " AND ".join(camera_conditions)

        camera_rows = self._execute(
            "SELECT tf.camera_id, c.name AS camera_name, COUNT(*) AS count "
            "FROM training_frames tf "
            "LEFT JOIN public.cameras c "
            "  ON c.id = tf.camera_id AND c.tenant_id = tf.tenant_id "
            f"WHERE {camera_where} "
            "GROUP BY tf.camera_id, c.name "
            "ORDER BY count DESC",
            tuple(camera_params),
        )
        cameras = [
            {
                "camera_id": str(row["camera_id"]) if row["camera_id"] else None,
                "camera_name": row["camera_name"],
                "count": int(row["count"]),
            }
            for row in camera_rows
        ]

        # --- Faceta de status (não filtra pelo próprio curation_status) ---
        status_conditions = list(base_conditions)
        status_params = list(base_params)
        if camera_ids:
            status_conditions.append("tf.camera_id = ANY(%s::uuid[])")
            status_params.append([str(c) for c in camera_ids])
        elif camera_id is not None:
            status_conditions.append("tf.camera_id = %s")
            status_params.append(str(camera_id))
        status_where = " AND ".join(status_conditions)

        status_rows = self._execute(
            "SELECT tf.curation_status, tf.is_annotated, COUNT(*) AS count "
            "FROM training_frames tf "
            f"WHERE {status_where} "
            "GROUP BY tf.curation_status, tf.is_annotated",
            tuple(status_params),
        )
        status_counts = {"nao_anotado": 0, "anotado": 0, "duvida": 0, "excluida": 0}
        for row in status_rows:
            n = int(row["count"])
            if row["curation_status"] == "duvida":
                status_counts["duvida"] += n
            elif row["curation_status"] == "excluida":
                status_counts["excluida"] += n
            elif row["is_annotated"]:
                status_counts["anotado"] += n
            else:
                status_counts["nao_anotado"] += n

        return {"cameras": cameras, "status": status_counts}

    def update_curation_status(
        self,
        frame_ids: "list[UUID | str]",
        status: str,
        tenant_id: "UUID | str",
        updated_by: "UUID | str | None" = None,
    ) -> int:
        """Curadoria em lote: marca frames como active/duvida/excluida.

        Escopo SEMPRE por tenant_id (id = ANY(%s::uuid[]) AND tenant_id = %s)
        — ids de outro tenant simplesmente não casam a cláusula WHERE e não
        são atualizados, sem vazar existência (C-01). Nunca apaga a linha —
        curadoria é só um campo de estado, boxes/frame continuam no banco.
        Retorna quantidade de linhas afetadas.

        `::uuid[]` é obrigatório: psycopg2 adapta list[str] para text[], e
        `uuid_column = ANY(text[])` não tem operador implícito no Postgres
        (achado ao validar contra banco real — sem o cast, UndefinedFunction
        "operator does not exist: uuid = text").
        """
        return self._execute_mutation_no_return(
            "UPDATE training_frames "
            "SET curation_status = %s, curation_updated_at = NOW(), "
            "    curation_updated_by = %s "
            "WHERE id = ANY(%s::uuid[]) AND tenant_id = %s",
            (
                str(status),
                str(updated_by) if updated_by else None,
                [str(fid) for fid in frame_ids],
                str(tenant_id),
            ),
        )

    def list_unlabeled_by_uncertainty(
        self, tenant_id: "UUID | str", module_code: str, limit: int = 20
    ) -> "list[dict[str, Any]]":
        """Fila de active learning (WS-B2): frames não rotulados ordenados
        por incerteza — model_confidence ASC (quanto menor a confiança da
        detecção que originou o frame, maior a prioridade de rotulagem).

        Fonte do sinal de incerteza: `model_confidence`, já populado para
        frames `source='auto'` (WS-B3) pela inferência ao vivo — não
        depende de `uncertainty_score`/pré-anotação (WS-B4, backend
        plugável desligado por padrão, ver ADR-0031).

        SEM/COM score são INTERCALADOS (era `NULLS LAST` puro). A regra antiga
        dizia que frame sem `model_confidence` não é "mais urgente" que um de
        baixa confiança conhecida — verdade, mas num pool MISTO ela fazia o
        dado novo afundar pra sempre: frame de NVR/upload nunca tem score, e
        ficava eternamente atrás de qualquer frame `auto`. Isso trava
        exatamente o caso de bootstrap de cliente novo (RVB), onde a coleta do
        gravador É o dataset e não existe modelo pra pontuar nada ainda.

        Intercalação 1:1 enquanto os dois lados tiverem frame; quando um acaba,
        o outro preenche o resto. Pool só-com-score ou só-sem-score se comporta
        exatamente como antes.
        """
        cols = (
            "tf.id, tf.video_id, tf.frame_number, tf.filename, "
            "tf.r2_key, tf.source, tf.width, tf.height, tf.camera_id, "
            "tf.model_confidence, tf.created_at"
        )
        # `curation_status = 'active'`: esta fila servia frame já marcado
        # 'excluida'/'duvida' — o mesmo filtro que list_images_filtered aplica
        # desde a migration 110 nunca chegou aqui. Curadoria não apaga frame do
        # banco; sem este predicado, o que o humano descartou volta para a fila.
        base_where = (
            "WHERE tf.tenant_id = %s AND tf.module_code = %s "
            "AND tf.is_annotated = FALSE "
            "AND tf.curation_status = 'active'"
        )

        scored = list(self._execute(
            f"SELECT {cols} FROM training_frames tf {base_where} "
            "AND tf.model_confidence IS NOT NULL "
            "ORDER BY tf.model_confidence ASC, tf.created_at ASC LIMIT %s",
            (str(tenant_id), module_code, limit),
        ))
        unscored = list(self._execute(
            f"SELECT {cols} FROM training_frames tf {base_where} "
            "AND tf.model_confidence IS NULL "
            "ORDER BY tf.created_at ASC LIMIT %s",
            (str(tenant_id), module_code, limit),
        ))

        out: "list[dict[str, Any]]" = []
        for a, b in zip_longest(scored, unscored):
            if a is not None:
                out.append(a)
            if b is not None:
                out.append(b)
            if len(out) >= limit:
                break
        return out[:limit]

    # ------------------------------------------------------------------
    # Propagação semeada (migration 112) — pool materializado + guard
    # ------------------------------------------------------------------

    def get_by_ids(self, frame_ids: "list[UUID | str]") -> "list[dict[str, Any]]":
        """Busca múltiplos frames por id, sem verificação de posse —
        INTERNAL USE ONLY (Celery). Usado pra REVALIDAR o pool de
        propagação no dispatch (`tasks/propagation.py`): a lista de ids já
        materializada (`propagation_jobs.pool_frame_ids`) é refetchada por
        ID aqui, NUNCA reconsultada por critério de novo — reconsultar por
        critério poderia devolver um conjunto diferente sem ninguém notar
        (frame novo inserido depois, frame reatribuído a outra câmera).
        `::uuid[]` obrigatório (achado de `update_curation_status`):
        `uuid_column = ANY(text[])` não tem operador implícito.
        """
        if not frame_ids:
            return []
        return self._execute(
            "SELECT * FROM training_frames WHERE id = ANY(%s::uuid[])",
            ([str(fid) for fid in frame_ids],),
        )

    def list_for_propagation_pool(
        self,
        tenant_id: "UUID | str",
        camera_ids: "list[UUID | str]",
        date_from: date,
        date_to: date,
    ) -> "list[dict[str, Any]]":
        """Materializa o pool de candidatos pra propagação semeada: frames
        do tenant, dentro das câmeras e do intervalo de data pedidos, com
        `r2_key` presente (sem imagem, não há o que baixar/propagar).
        `ORDER BY id` — ordem determinística pra truncamento
        (`validation_only`) e pra `pool_hash` (ver
        `domain/services/propagation_pool.py`).
        """
        if not camera_ids:
            return []
        return self._execute(
            "SELECT id, tenant_id, camera_id, r2_key, captured_at, module_code "
            "FROM training_frames "
            "WHERE tenant_id = %s AND camera_id = ANY(%s::uuid[]) "
            "AND captured_at::date BETWEEN %s AND %s "
            "AND r2_key IS NOT NULL AND r2_key != '' "
            "ORDER BY id",
            (
                str(tenant_id),
                [str(c) for c in camera_ids],
                date_from,
                date_to,
            ),
        )

    def apply_propagation_proposals(
        self, frame_id: "UUID | str", tenant_id: "UUID | str", proposals: "list[dict[str, Any]]"
    ) -> bool:
        """Grava propostas da propagação semeada em `pre_annotations`
        (mesmo jsonb consumido por `AnnotationService.get_frame_
        annotations` e pela fila de aprovação, migration 111) e reseta o
        status de revisão pra NULL (pendente) — mesmo shape/fila que
        DINO/SAM (`pre_annotation/dino_sam_backend.py`) já alimentavam.

        Escopo por `tenant_id` no próprio UPDATE (defesa em profundidade —
        o caller já validou `frame_id ∈ pool_frame_ids` do job ANTES de
        chamar, ver `propagation_handlers.py::_apply_completed_payload`).
        Retorna True se atualizou (frame existe e pertence ao tenant).
        """
        rowcount = self._execute_mutation_no_return(
            "UPDATE training_frames SET pre_annotations = %s::jsonb, "
            "pre_annotation_review_status = NULL, "
            "pre_annotation_reviewed_by = NULL, "
            "pre_annotation_reviewed_at = NULL "
            "WHERE id = %s AND tenant_id = %s",
            (json.dumps(proposals), str(frame_id), str(tenant_id)),
        )
        return rowcount > 0

    # ------------------------------------------------------------------
    # Busca por conteúdo (migration 113) — frames selecionados + promoção
    # ------------------------------------------------------------------

    def get_by_ids_and_tenant(
        self, frame_ids: "list[UUID | str]", tenant_id: "UUID | str"
    ) -> "list[dict[str, Any]]":
        """Busca múltiplos frames por id JÁ escopado por tenant no próprio
        SQL (`AND tenant_id = %s`, não um filtro em Python depois) — um
        frame de outro tenant simplesmente não aparece no resultado, a
        MESMA forma que um id inexistente não aparece (C-01: as duas
        situações chegam indistinguíveis pro caller, nunca vaza qual delas
        é). Usado pela busca por conteúdo (`search_handlers.py`,
        `tasks/search.py`) pra resolver frames SELECIONADOS individualmente
        na galeria — ao contrário de `get_by_ids` (propagação semeada,
        INTERNAL USE ONLY, sem filtro de tenant), este método é seguro pra
        chamar direto de um handler HTTP autenticado por JWT.
        """
        if not frame_ids:
            return []
        return self._execute(
            "SELECT * FROM training_frames WHERE id = ANY(%s::uuid[]) AND tenant_id = %s",
            ([str(fid) for fid in frame_ids], str(tenant_id)),
        )

    def append_pre_annotations(
        self,
        frame_id: "UUID | str",
        tenant_id: "UUID | str",
        proposals: "list[dict[str, Any]]",
    ) -> bool:
        """Promove achado(s) de busca por conteúdo a proposta(s) pendente(s)
        — MERGE no jsonb `pre_annotations` já existente (`||` concatena
        arrays JSONB) em vez de sobrescrever como `apply_propagation_
        proposals` faz. A diferença é deliberada: a propagação semeada
        grava o pool INTEIRO de uma vez só (não há propostas anteriores de
        outro job pra preservar); a promoção de achados de busca é
        incremental — um segundo `promote` (deste job ou de outro) NUNCA
        pode apagar silenciosamente propostas pendentes já gravadas por um
        `promote` anterior. `pre_annotation_review_status` volta pra NULL
        (pendente) — mesmo shape/fila da migration 111/112. Escopo por
        `tenant_id` no próprio UPDATE (defesa em profundidade, mesmo padrão
        de `apply_propagation_proposals`). Retorna True se atualizou (frame
        existe e pertence ao tenant).
        """
        rowcount = self._execute_mutation_no_return(
            "UPDATE training_frames SET "
            "pre_annotations = COALESCE(pre_annotations, '[]'::jsonb) || %s::jsonb, "
            "pre_annotation_review_status = NULL, "
            "pre_annotation_reviewed_by = NULL, "
            "pre_annotation_reviewed_at = NULL "
            "WHERE id = %s AND tenant_id = %s",
            (json.dumps(proposals), str(frame_id), str(tenant_id)),
        )
        return rowcount > 0
