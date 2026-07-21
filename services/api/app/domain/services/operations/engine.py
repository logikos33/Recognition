"""
Recognition — OperationsEngine.

Motor que avalia operações configuradas contra o stream de detecção em produção
(fora do /test) e persiste resultado. É a peça que faltava do Bloco 3 do go-live RVB:
antes, `evaluate()` só rodava na rota /test e `operation_results` não era populada
por worker nenhum.

Design (testável): esta classe é PURA — não conhece Redis nem o driver do banco.
Recebe um `repo` (duck-typed: precisa de `list_all_active`, `get_active_by_id`,
`insert_result`, `update_live_value`), um `publish` opcional `(channel, payload)->None`
e um relógio `now()->float`. O runner de I/O (Redis pub/sub) vive em
`app/core/operations_worker.py` e apenas dirige este motor.

Fluxo:
  load_all()                    → monta o mapa camera_id → [operações ativas]
  process_frame(cam, dets, fm)  → avalia cada operação da câmera, carrega estado
                                  entre frames, persiste com throttle e publica status
  reload_operation(op_id)       → hot-reload de UMA operação (D2: reload estrutural)

Throttle (crítico): a 5 FPS × dezenas de câmeras, persistir todo frame explodiria
`operation_results`. Persiste-se quando a CONDIÇÃO muda OU passou `result_interval_s`;
o `last_value_json` (badge ao vivo) atualiza na mudança OU a cada `live_interval_s`.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol

from app.domain.services.operations.base import BaseOperation
from app.domain.services.operations.registry import OperationTypeRegistry

logger = logging.getLogger(__name__)

# Estado interno reservado por convenção (não vai para o histórico).
_RESULT_KEYS = ("result", "metric_value", "condition_satisfied")


class _RepoLike(Protocol):
    def list_all_active(self) -> list[dict[str, Any]]: ...
    def get_active_by_id(self, operation_id: int) -> Optional[dict[str, Any]]: ...
    def insert_result(self, operation_id: int, result_json: dict) -> None: ...
    def update_live_value(
        self, operation_id: int, last_value_json: dict, status: str = ...
    ) -> None: ...


@dataclass
class _LoadedOp:
    """Uma operação carregada em memória, com estado vivo entre frames."""

    op_id: int
    tenant_id: str
    camera_id: str
    type_id: str
    version: int
    instance: BaseOperation
    state: dict = field(default_factory=dict)
    last_result_ts: float = 0.0
    last_live_ts: float = 0.0
    last_condition: Any = None


class OperationsEngine:
    """Avalia operações contra detecções e persiste resultado (throttled)."""

    def __init__(
        self,
        repo: _RepoLike,
        publish: Optional[Callable[[str, dict], None]] = None,
        now: Callable[[], float] = time.monotonic,
        result_interval_s: float = 5.0,
        live_interval_s: float = 2.0,
    ) -> None:
        self._repo = repo
        self._publish = publish
        self._now = now
        self._result_interval_s = result_interval_s
        self._live_interval_s = live_interval_s
        self._by_camera: dict[str, list[_LoadedOp]] = {}
        self._by_id: dict[int, _LoadedOp] = {}

    # ------------------------------------------------------------------ load
    def load_all(self) -> int:
        """(Re)carrega todas as operações ativas. Preserva estado de ops cuja
        versão não mudou (reload periódico não zera cronômetros à toa)."""
        prev = self._by_id
        by_camera: dict[str, list[_LoadedOp]] = {}
        by_id: dict[int, _LoadedOp] = {}
        for row in self._repo.list_all_active():
            loaded = self._build(row)
            if loaded is None:
                continue
            old = prev.get(loaded.op_id)
            if old is not None and old.version == loaded.version:
                # mesma versão → preserva estado vivo e timestamps de throttle
                loaded.state = old.state
                loaded.last_result_ts = old.last_result_ts
                loaded.last_live_ts = old.last_live_ts
                loaded.last_condition = old.last_condition
            by_id[loaded.op_id] = loaded
            by_camera.setdefault(loaded.camera_id, []).append(loaded)
        self._by_camera = by_camera
        self._by_id = by_id
        logger.info(
            "operations_engine_loaded: ops=%d cameras=%d", len(by_id), len(by_camera)
        )
        return len(by_id)

    def _build(self, row: dict[str, Any]) -> Optional[_LoadedOp]:
        type_id = row["type_id"]
        op_class = OperationTypeRegistry.get(type_id)
        if op_class is None:
            logger.warning(
                "operations_engine_unknown_type: op=%s type=%s (pulada)",
                row["id"], type_id,
            )
            return None
        try:
            instance = op_class(row.get("config") or {})
        except Exception:
            logger.exception("operations_engine_build_failed: op=%s", row["id"])
            return None
        return _LoadedOp(
            op_id=int(row["id"]),
            tenant_id=str(row["tenant_id"]),
            camera_id=str(row["camera_id"]),
            type_id=type_id,
            version=int(row.get("version", 1)),
            instance=instance,
        )

    # ---------------------------------------------------------------- reload
    def reload_operation(self, operation_id: int) -> bool:
        """Hot-reload de UMA operação (D2). Config nova → instância nova; o estado
        vivo é RESETADO (mudança de config é tratada como estrutural para a operação;
        cronômetros/contadores recomeçam limpos). Remove se sumiu/ficou inativa."""
        row = self._repo.get_active_by_id(operation_id)
        # inativa/ausente → remover do mapa
        if row is None or row.get("status") == "inactive":
            self._remove(operation_id)
            logger.info("operations_engine_reload_removed: op=%s", operation_id)
            self._emit(f"operations:reload:{operation_id}", {"removed": True})
            return False
        loaded = self._build(row)
        if loaded is None:
            self._remove(operation_id)
            return False
        self._remove(operation_id)  # tira a instância antiga do mapa por câmera
        self._by_id[operation_id] = loaded
        self._by_camera.setdefault(loaded.camera_id, []).append(loaded)
        logger.info(
            "operations_engine_reloaded: op=%s v=%s camera=%s",
            operation_id, loaded.version, loaded.camera_id,
        )
        self._emit(f"operations:reload:{operation_id}", {"version": loaded.version})
        return True

    def _remove(self, operation_id: int) -> None:
        old = self._by_id.pop(operation_id, None)
        if old is None:
            return
        siblings = self._by_camera.get(old.camera_id)
        if siblings:
            remaining = [o for o in siblings if o.op_id != operation_id]
            if remaining:
                self._by_camera[old.camera_id] = remaining
            else:
                self._by_camera.pop(old.camera_id, None)

    # --------------------------------------------------------------- process
    def process_frame(
        self,
        camera_id: str,
        detections: list[dict],
        frame_meta: dict,
    ) -> int:
        """Avalia todas as operações da câmera contra as detecções do frame.

        Retorna quantas operações foram avaliadas. Uma operação que estoura NÃO
        derruba as outras (isolamento) — vira status 'error'.
        """
        ops = self._by_camera.get(str(camera_id))
        if not ops:
            return 0
        evaluated = 0
        for op in ops:
            try:
                self._evaluate_one(op, detections, frame_meta)
                evaluated += 1
            except Exception as exc:  # isolamento — uma op ruim não mata o frame
                logger.warning(
                    "operations_engine_eval_error: op=%s type=%s err=%s",
                    op.op_id, op.type_id, exc,
                )
                self._safe_error(op, exc)
        return evaluated

    def _evaluate_one(
        self, op: _LoadedOp, detections: list[dict], frame_meta: dict
    ) -> None:
        result = op.instance.evaluate(detections, frame_meta, op.state)
        if not isinstance(result, dict):
            raise TypeError(f"evaluate() retornou {type(result).__name__}, esperado dict")
        # estado entre frames
        op.state = result.get("state_next", op.state) or op.state
        payload = {k: result.get(k) for k in _RESULT_KEYS}
        condition = result.get("condition_satisfied")
        changed = condition != op.last_condition
        now = self._now()

        # histórico (throttle): na mudança de condição OU a cada result_interval_s
        if changed or (now - op.last_result_ts) >= self._result_interval_s:
            self._repo.insert_result(op.op_id, payload)
            op.last_result_ts = now

        # badge ao vivo (throttle): na mudança OU a cada live_interval_s
        if changed or (now - op.last_live_ts) >= self._live_interval_s:
            self._repo.update_live_value(op.op_id, payload, status="active")
            op.last_live_ts = now
            self._emit(
                f"operations:status:{op.op_id}",
                {"operation_id": op.op_id, "camera_id": op.camera_id, **payload},
            )
        op.last_condition = condition

    def _safe_error(self, op: _LoadedOp, exc: Exception) -> None:
        try:
            self._repo.update_live_value(
                op.op_id, {"error": str(exc)[:200]}, status="error"
            )
            self._emit(
                f"operations:status:{op.op_id}",
                {"operation_id": op.op_id, "camera_id": op.camera_id, "status": "error"},
            )
        except Exception:
            logger.exception("operations_engine_error_persist_failed: op=%s", op.op_id)

    # ------------------------------------------------------------------ util
    def _emit(self, channel: str, payload: dict) -> None:
        if self._publish is None:
            return
        try:
            self._publish(channel, payload)
        except Exception:
            logger.warning("operations_engine_publish_failed: channel=%s", channel)

    # ------------------------------------------------------------ introspection
    def stats(self) -> dict:
        """Snapshot leve para health/observabilidade."""
        return {
            "operations": len(self._by_id),
            "cameras": len(self._by_camera),
        }
