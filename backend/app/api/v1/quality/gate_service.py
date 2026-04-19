"""
Gate Service — orquestra o fluxo do quality gate.

Responsabilidades:
  - Gerenciar ciclo de vida das peças (create → identify → inspect → approve/rework)
  - Aplicar state machine a cada transição
  - Publicar eventos no Redis para WebSocket bridge (frontend/tablet)
  - Disparar tasks Celery de inspeção
  - Acionar torre luminosa por resultado
  - Exportar peça aprovada para o Wiser

Padrão:
  - Imports de state_machine, tower_controller e wiser_integration são lazy
    (dentro dos métodos) para evitar circular imports e carregamento desnecessário
  - Redis publish: canal quality:* para socket_bridge
  - DatabasePool: injetado via construtor
"""
import json
import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class GateService:
    """Orquestra o quality gate — state machine, inspeção, retrabalho e exportação.

    Args:
        pool: Instância do DatabasePool já inicializado.
        redis_client: Cliente Redis já conectado (redis.Redis ou redis.StrictRedis).
    """

    def __init__(self, pool, redis_client):
        """Inicializa o serviço com pool de DB e cliente Redis.

        Args:
            pool: DatabasePool.get_instance() — nunca None em runtime.
            redis_client: Cliente Redis para publicação de eventos.
        """
        self._pool = pool
        self._redis = redis_client

    # ------------------------------------------------------------------ #
    # Helpers internos                                                     #
    # ------------------------------------------------------------------ #

    def _get_repo(self):
        """Retorna instância do GateRepository com o pool atual."""
        from app.api.v1.quality.gate_repository import GateRepository
        return GateRepository(self._pool)

    def _get_sm(self):
        """Retorna instância da PieceStateMachine."""
        from app.api.v1.quality.state_machine import PieceStateMachine
        return PieceStateMachine()

    def _publish_redis(self, channel: str, data: dict) -> None:
        """Publica mensagem JSON no Redis para WebSocket bridge.

        Args:
            channel: Canal Redis (ex: "quality:piece_identified").
            data: Dict a serializar e publicar.
        """
        try:
            self._redis.publish(channel, json.dumps(data, default=str))
        except Exception as exc:
            logger.warning("redis_publish_error: channel=%s err=%s", channel, exc)

    def _signal_tower(self, schema: str, station_code: str, color: str) -> None:
        """Aciona torre luminosa da bancada.

        Args:
            schema: Schema do tenant (não usado diretamente, mas disponível para log).
            station_code: Código da bancada.
            color: "green", "red" ou "idle".
        """
        try:
            from app.api.v1.quality.tower_controller import get_tower_controller
            tower = get_tower_controller()
            if color == "green":
                tower.set_green(station_code)
            elif color == "red":
                tower.set_red(station_code)
            else:
                tower.set_idle(station_code)
        except Exception as exc:
            logger.warning(
                "tower_signal_error: station=%s color=%s err=%s", station_code, color, exc
            )

    # ------------------------------------------------------------------ #
    # Criação e identificação de peças                                     #
    # ------------------------------------------------------------------ #

    def create_piece(
        self,
        schema: str,
        piece_number: str,
        work_order: str | None = None,
        product_type: str | None = None,
        operator_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict:
        """Cria peça no estado 'idle' e publica evento no Redis.

        Args:
            schema: Schema do tenant.
            piece_number: Número identificador da peça.
            work_order: Ordem de produção (opcional).
            product_type: Tipo de produto (opcional).
            operator_id: UUID do operador que criou (opcional).
            tenant_id: UUID do tenant (opcional).

        Returns:
            Dict com os campos da peça criada.
        """
        repo = self._get_repo()
        piece = repo.create_piece(
            schema,
            {
                "piece_number": piece_number,
                "work_order": work_order,
                "product_type": product_type,
                "status": "idle",
                "operator_id": operator_id,
            },
        )
        self._publish_redis(
            f"quality:station_state:{schema}",
            {"event": "piece_created", "piece": piece},
        )
        return piece

    def identify_piece(
        self,
        schema: str,
        piece_id: str,
        piece_number: str,
        work_order: str | None = None,
    ) -> dict:
        """Transição idle→identified. Atualiza número da peça e ordem de produção.

        Args:
            schema: Schema do tenant.
            piece_id: UUID da peça.
            piece_number: Número da peça lido (OCR ou manual).
            work_order: Ordem de produção (opcional).

        Returns:
            Dict com os campos atualizados da peça.

        Raises:
            ValueError: Se a transição idle→identified não for permitida.
        """
        repo = self._get_repo()
        sm = self._get_sm()

        piece = repo.get_piece(schema, piece_id)
        if not piece:
            raise ValueError(f"Peça não encontrada: {piece_id}")

        sm.transition(piece["status"], "identified")  # valida ou levanta ValueError

        extra = {"piece_number": piece_number}
        if work_order:
            extra["work_order"] = work_order

        updated = repo.update_piece_status(schema, piece_id, "identified", extra)
        self._publish_redis(
            f"quality:piece_identified:{schema}",
            {"event": "piece_identified", "piece": updated},
        )
        return updated

    # ------------------------------------------------------------------ #
    # Inspeção                                                             #
    # ------------------------------------------------------------------ #

    def start_inspection(self, schema: str, piece_id: str, camera_id: str | None = None) -> dict:
        """Inicia inspeção: transição identified→validating_v1 (ou rework→validating).

        Dispara task Celery run_quality_gate_inspection.

        Args:
            schema: Schema do tenant.
            piece_id: UUID da peça.
            camera_id: UUID da câmera de inspeção (opcional — buscado da bancada se None).

        Returns:
            Dict com os campos atualizados da peça.

        Raises:
            ValueError: Se a transição não for permitida no estado atual.
        """
        repo = self._get_repo()
        sm = self._get_sm()

        piece = repo.get_piece(schema, piece_id)
        if not piece:
            raise ValueError(f"Peça não encontrada: {piece_id}")

        current = piece["status"]

        # Determina o próximo estado de validação
        if current == "identified":
            next_state = "validating_v1"
        elif sm.is_rework(current):
            # rework_v1 → validating_v1, rework_v2 → validating_v2, etc.
            rework_num = current.split("_")[-1]  # "v1", "v2" ou "v3"
            next_state = f"validating_{rework_num}"
        else:
            raise ValueError(f"Não é possível iniciar inspeção a partir do estado: {current!r}")

        sm.transition(current, next_state)  # valida ou levanta ValueError

        updated = repo.update_piece_status(schema, piece_id, next_state)

        validation_type = sm.get_validation_type(next_state)

        self._publish_redis(
            f"quality:inspection_started:{schema}",
            {"event": "inspection_started", "piece": updated, "validation_type": validation_type},
        )

        # Dispara task Celery de inspeção se camera_id fornecido
        if camera_id and validation_type:
            try:
                from app.infrastructure.queue.tasks.quality_inference import (  # noqa: E501
                    run_quality_gate_inspection,
                )
                run_quality_gate_inspection.delay(
                    piece_id=piece_id,
                    validation_type=validation_type,
                    camera_id=camera_id,
                    tenant_schema=schema,
                )
            except Exception as exc:
                logger.error("gate_inspection_task_dispatch_error: piece=%s err=%s", piece_id, exc)

        return updated

    def process_inspection_result(
        self,
        schema: str,
        piece_id: str,
        result: str,
        confidence: float,
        photo_path: str | None = None,
        defect_description: str | None = None,
        station_code: str | None = None,
        tenant_id: str | None = None,
    ) -> dict:
        """Processa resultado da inspeção YOLO e avança a state machine.

        Se OK:  avança validating_v1→v2, v2→waiting_bench_b ou v3→approved.
        Se NOK: cria registro de retrabalho e transiciona para rework_vN.
        Se approved: dispara exportação Wiser e foto de qualidade.

        Args:
            schema: Schema do tenant.
            piece_id: UUID da peça.
            result: "ok" ou "nok".
            confidence: Confiança do resultado (0.0 a 1.0).
            photo_path: Caminho da foto de análise (opcional, relevante para NOK).
            defect_description: Descrição do defeito encontrado (opcional).
            station_code: Código da bancada (para sinalizar torre).
            tenant_id: UUID do tenant (para criar rework).

        Returns:
            Dict com os campos atualizados da peça.

        Raises:
            ValueError: Se a peça não for encontrada ou estado inválido.
        """
        repo = self._get_repo()
        sm = self._get_sm()

        piece = repo.get_piece(schema, piece_id)
        if not piece:
            raise ValueError(f"Peça não encontrada: {piece_id}")

        current = piece["status"]
        validation_type = sm.get_validation_type(current)

        if not validation_type:
            raise ValueError(f"Peça não está em estado de validação: {current!r}")

        if result == "ok":
            next_state = sm.get_next_validation(validation_type)
            if not next_state:
                raise ValueError(f"Sem próximo estado para validação {validation_type!r}")

            extra = {"last_inspection_confidence": confidence}
            if next_state == "approved":
                extra["approved_at"] = datetime.now(UTC).isoformat()

            updated = repo.update_piece_status(schema, piece_id, next_state, extra)

            # Sinaliza torre verde
            if station_code:
                self._signal_tower(schema, station_code, "green")

            # Se aprovada: dispara exportação Wiser
            if next_state == "approved" and photo_path:
                try:
                    from app.api.v1.quality.wiser_integration import get_wiser_integration
                    wiser = get_wiser_integration()
                    export_result = wiser.export_piece(updated, photo_path)
                    if export_result["success"]:
                        repo.update_piece(schema, piece_id, {
                            "wiser_exported": True,
                            "wiser_exported_at": datetime.now(UTC).isoformat(),
                        })
                        repo.create_export_log(schema, {
                            "piece_id": piece_id,
                            "export_method": export_result.get("method", "file_share"),
                            "file_path": export_result.get("path"),
                            "success": True,
                            "error_message": "",
                        })
                    else:
                        logger.warning(
                            "wiser_export_failed: piece=%s err=%s",
                            piece_id,
                            export_result.get("error"),
                        )
                except Exception as exc:
                    logger.error("wiser_export_error: piece=%s err=%s", piece_id, exc)

        else:  # result == "nok"
            rework_state = sm.get_rework_state(validation_type)
            updated = repo.update_piece_status(
                schema,
                piece_id,
                rework_state,
                {"total_rework_count": (piece.get("total_rework_count") or 0) + 1},
            )

            # Cria registro de retrabalho
            try:
                repo.create_rework(schema, {
                    "piece_id": piece_id,
                    "validation_type": validation_type,
                    "defect_type": None,
                    "defect_description": defect_description,
                    "photo_before_path": photo_path,
                    "photo_before_r2_key": None,
                    "operator_id": None,
                })
            except Exception as exc:
                logger.error("create_rework_error: piece=%s err=%s", piece_id, exc)

            # Sinaliza torre vermelha
            if station_code:
                self._signal_tower(schema, station_code, "red")

        self._publish_redis(
            f"quality:inspection_result:{schema}",
            {
                "event": "inspection_result",
                "piece_id": piece_id,
                "result": result,
                "confidence": confidence,
                "new_status": updated.get("status"),
                "validation_type": validation_type,
            },
        )

        return updated

    def mark_false_positive(
        self,
        schema: str,
        piece_id: str,
        inspection_id: str | None = None,
    ) -> dict:
        """Reverte resultado de inspeção como falso positivo — volta para 'identified'.

        Usado quando o operador rejeita o resultado NOK da câmera.

        Args:
            schema: Schema do tenant.
            piece_id: UUID da peça.
            inspection_id: UUID da inspeção a marcar como false_negative (opcional).

        Returns:
            Dict com os campos atualizados da peça.

        Raises:
            ValueError: Se a peça não for encontrada ou não estiver em estado de validação.
        """
        repo = self._get_repo()
        sm = self._get_sm()

        piece = repo.get_piece(schema, piece_id)
        if not piece:
            raise ValueError(f"Peça não encontrada: {piece_id}")

        if not sm.is_validating(piece["status"]):
            raise ValueError(
                f"Falso positivo só permitido durante validação. Estado atual: {piece['status']!r}"
            )

        sm.transition(piece["status"], "identified")  # valida ou levanta ValueError

        updated = repo.update_piece_status(schema, piece_id, "identified")

        # Atualiza feedback_status da inspeção se ID fornecido
        if inspection_id:
            try:
                with self._pool.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SET search_path TO %s, public", (schema,))
                    cur.execute(
                        "UPDATE quality_inspections "
                    "SET feedback_status='false_negative' WHERE id=%s",
                        (inspection_id,),
                    )
            except Exception as exc:
                logger.warning(
                    "false_positive_feedback_update_error: inspection=%s err=%s",
                    inspection_id,
                    exc,
                )

        self._publish_redis(
            f"quality:inspection_result:{schema}",
            {"event": "false_positive", "piece_id": piece_id, "new_status": "identified"},
        )
        return updated

    # ------------------------------------------------------------------ #
    # Bancada B e retrabalho                                               #
    # ------------------------------------------------------------------ #

    def release_to_bench_b(
        self, schema: str, piece_id: str, station_code: str | None = None
    ) -> dict:
        """Operador libera peça para Bancada B: waiting_bench_b→validating_v3.

        Args:
            schema: Schema do tenant.
            piece_id: UUID da peça.
            station_code: Código da bancada B (para sinalizar torre).

        Returns:
            Dict com os campos atualizados da peça.

        Raises:
            ValueError: Se a peça não estiver em estado waiting_bench_b.
        """
        repo = self._get_repo()
        sm = self._get_sm()

        piece = repo.get_piece(schema, piece_id)
        if not piece:
            raise ValueError(f"Peça não encontrada: {piece_id}")

        sm.transition(piece["status"], "validating_v3")  # valida ou levanta ValueError

        updated = repo.update_piece_status(schema, piece_id, "validating_v3")

        if station_code:
            self._signal_tower(schema, station_code, "idle")

        self._publish_redis(
            f"quality:station_state:{schema}",
            {"event": "released_to_bench_b", "piece": updated},
        )
        return updated

    def start_rework(
        self,
        schema: str,
        piece_id: str,
        validation_type: str,
        defect_type: str,
        defect_description: str | None = None,
        photo_before_path: str | None = None,
        operator_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict:
        """Registra início formal de retrabalho pelo operador.

        Args:
            schema: Schema do tenant.
            piece_id: UUID da peça.
            validation_type: Tipo de validação que gerou o NOK ("v1", "v2" ou "v3").
            defect_type: Categoria do defeito (ex: "surface_scratch").
            defect_description: Descrição textual do defeito (opcional).
            photo_before_path: Foto da peça antes do retrabalho (opcional).
            operator_id: UUID do operador (opcional).
            tenant_id: UUID do tenant (opcional).

        Returns:
            Dict com os campos do retrabalho criado.
        """
        repo = self._get_repo()
        rework = repo.create_rework(schema, {
            "piece_id": piece_id,
            "validation_type": validation_type,
            "defect_type": defect_type,
            "defect_description": defect_description,
            "photo_before_path": photo_before_path,
            "photo_before_r2_key": None,
            "operator_id": operator_id,
        })
        self._publish_redis(
            f"quality:station_state:{schema}",
            {"event": "rework_started", "rework": rework, "piece_id": piece_id},
        )
        return rework

    def complete_rework(self, schema: str, rework_id: str) -> dict:
        """Registra conclusão do retrabalho e calcula duração.

        Args:
            schema: Schema do tenant.
            rework_id: UUID do registro de retrabalho.

        Returns:
            Dict com os campos atualizados do retrabalho.

        Raises:
            ValueError: Se o retrabalho não for encontrado.
        """
        repo = self._get_repo()

        # Busca retrabalho para calcular duração
        with self._pool.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SET search_path TO %s, public", (schema,))
            cur.execute("SELECT * FROM quality_reworks WHERE id = %s", (rework_id,))
            row = cur.fetchone()

        if not row:
            raise ValueError(f"Retrabalho não encontrado: {rework_id}")

        rework = dict(row)
        started_at = rework.get("started_at")
        completed_at = datetime.now(UTC)

        duration_seconds = 0
        if started_at:
            try:
                # started_at pode ser datetime ou string ISO
                if hasattr(started_at, "timestamp"):
                    delta = completed_at - started_at.replace(tzinfo=UTC)
                    duration_seconds = int(delta.total_seconds())
                else:
                    sa = datetime.fromisoformat(str(started_at)).replace(tzinfo=UTC)
                    duration_seconds = int((completed_at - sa).total_seconds())
            except Exception as exc:
                logger.warning("rework_duration_calc_error: %s", exc)

        updated = repo.complete_rework(
            schema,
            rework_id,
            completed_at,
            max(0, duration_seconds),
        )

        # Atualiza total_rework_time_seconds na peça
        piece_id = rework.get("piece_id")
        if piece_id:
            try:
                with self._pool.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("SET search_path TO %s, public", (schema,))
                    cur.execute(
                        "UPDATE quality_pieces SET "
                        "total_rework_time_seconds = total_rework_time_seconds + %s, "
                        "updated_at = NOW() WHERE id = %s",
                        (duration_seconds, str(piece_id)),
                    )
            except Exception as exc:
                logger.warning("rework_time_update_error: piece=%s err=%s", piece_id, exc)

        self._publish_redis(
            f"quality:station_state:{schema}",
            {"event": "rework_completed", "rework": updated},
        )
        return updated

    # ------------------------------------------------------------------ #
    # Status da bancada                                                    #
    # ------------------------------------------------------------------ #

    def get_station_status(self, schema: str, station_code: str) -> dict:
        """Retorna status atual da bancada: peça atual, estado e câmeras.

        Args:
            schema: Schema do tenant.
            station_code: Código único da bancada.

        Returns:
            Dict com campos da bancada e peça atual (ou None se vazia).
        """
        repo = self._get_repo()
        station = repo.get_station(schema, station_code)
        if not station:
            return {"station_code": station_code, "current_piece": None, "cameras": []}

        current_piece = None
        piece_id = station.get("current_piece_id")
        if piece_id:
            current_piece = repo.get_piece(schema, str(piece_id))

        return {
            "station_code": station_code,
            "station": station,
            "current_piece": current_piece,
            "cameras": station.get("camera_ids") or [],
        }
