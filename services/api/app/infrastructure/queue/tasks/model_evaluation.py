"""
Recognition — Champion×Challenger Evaluation Task (WS-C1, ADR-0037).

Roda o modelo desafiante (e o campeão atual, se houver) contra o split de
holdout (test, fallback val) da dataset_version de origem, casa detecções
contra ground-truth COCO (IoU greedy, per-image — ver eval_metrics.py) e
grava o resultado em model_evaluations. Consumido pelo gate de
POST /api/v1/models/<id>/activate (verdict=reject → 409 a menos que
force=true e role admin+ — já implementado em registry_handlers.py).

Import de onnxruntime/numpy/cv2 é LAZY e gracioso (mesmo padrão de
tasks/model_validation.py::validate_onnx): worker sem as libs (imagem da
API não instala ML) não quebra — task retorna status 'skipped'.
"""
import logging
from typing import Any

from app.infrastructure.queue.celery_app import celery

logger = logging.getLogger(__name__)

_DEFAULT_IOU_THRESHOLD = 0.5
_MAP_REGRESSION_TOLERANCE = 0.01  # desafiante pode ficar até 1pp abaixo do campeão
_RECALL_DROP_TOLERANCE = 0.05  # nenhuma classe pode cair mais de 5pp de recall
_MAX_CATEGORIA_ID = 10_000  # teto de sanidade para indexar classes por id COCO


def _get_registry_repo():  # type: ignore[no-untyped-def]
    from app.infrastructure.database.connection import DatabasePool
    from app.infrastructure.database.repositories.model_registry_repository import (
        ModelRegistryRepository,
    )
    return ModelRegistryRepository(DatabasePool.get_instance())


def _get_dataset_repo():  # type: ignore[no-untyped-def]
    from app.infrastructure.database.connection import DatabasePool
    from app.infrastructure.database.repositories.dataset_repository import (
        DatasetRepository,
    )
    return DatasetRepository(DatabasePool.get_instance())


def _get_eval_repo():  # type: ignore[no-untyped-def]
    from app.infrastructure.database.connection import DatabasePool
    from app.infrastructure.database.repositories.model_evaluation_repository import (
        ModelEvaluationRepository,
    )
    return ModelEvaluationRepository(DatabasePool.get_instance())


def _get_storage(tenant_id: str | None = None):  # type: ignore[no-untyped-def]
    from app.infrastructure.storage.local_storage import get_storage
    return get_storage(tenant_id)


def _resolve_holdout_split(dataset_version: dict[str, Any]) -> str | None:
    """Prefere 'test'; cai pra 'val' se test_count==0; None se os dois forem 0."""
    if int(dataset_version.get("test_count") or 0) > 0:
        return "test"
    if int(dataset_version.get("val_count") or 0) > 0:
        return "val"
    return None


def _run_split_inference(
    detector: Any, storage: Any, coco_r2_key: str, split: str, coco: dict
) -> tuple[list[dict], list[dict]]:
    """Roda o detector em cada imagem do split e retorna
    (per_image_preds, per_image_gts) — listas paralelas, uma entrada por
    imagem, cada uma já no formato esperado por eval_metrics.greedy_match/
    confusion_matrix.
    """
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    cat_name_by_id = {c["id"]: c["name"] for c in coco.get("categories", [])}
    gts_by_image: dict[int, list[dict]] = {}
    for ann in coco.get("annotations", []):
        gts_by_image.setdefault(ann["image_id"], []).append({
            "class": cat_name_by_id.get(ann["category_id"], str(ann["category_id"])),
            "bbox": ann["bbox"],
        })

    per_image_preds: list[list[dict]] = []
    per_image_gts: list[list[dict]] = []
    falhas = 0
    for image in coco.get("images", []):
        key = f"{coco_r2_key}/{split}/{image['file_name']}"
        try:
            data = storage.download_bytes(key)
            frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                raise ValueError("cv2.imdecode retornou None")
            preds = detector.predict(frame)
        except Exception as exc:  # noqa: BLE001
            falhas += 1
            logger.warning("eval_image_skipped: key=%s err=%s", key, exc)
            continue
        per_image_preds.append(preds)
        per_image_gts.append(gts_by_image.get(image["id"], []))

    if falhas:
        logger.warning(
            "eval_split_com_falhas: split=%s ok=%d falhas=%d — imagem que não baixa "
            "vira ausência de detecção e puxa a métrica para baixo sem dizer por quê",
            split, len(per_image_preds), falhas,
        )
    return per_image_preds, per_image_gts


def _class_names_from_coco(coco: dict) -> list[str]:
    """Nomes de classe indexados pelo id da categoria COCO.

    O detector traduz índice→nome. Sem esta lista ele cai em COCO_CLASSES_91
    ("person", "bicycle", …), que nunca casa com o ground-truth do tenant — e
    o resultado é um avaliador que não acerta nada e não diz por quê.

    Índice = id da categoria, que é a convenção do harness calibrado
    (training/eval/per_class_eval.py). Buraco de id vira "?N": explícito, para
    aparecer na métrica em vez de silenciar.
    """
    by_id = {int(c["id"]): c["name"] for c in coco.get("categories", [])}
    if not by_id:
        return []
    maior = max(by_id)
    if maior >= _MAX_CATEGORIA_ID:
        # Um id absurdo alocaria uma lista de milhões de entradas por causa de
        # um COCO malformado. Cai para a ordem das categorias — pior que o
        # índice por id, mas melhor que derrubar o worker por alocação.
        logger.warning(
            "eval_categoria_id_absurdo: maior id=%d (limite %d) — usando a ORDEM "
            "das categorias em vez do id; se o modelo indexa por id, a métrica "
            "sai trocada e é isso que este aviso existe para denunciar",
            maior, _MAX_CATEGORIA_ID,
        )
        return [by_id[i] for i in sorted(by_id)]
    return [by_id.get(i, f"?{i}") for i in range(maior + 1)]


def _evaluate_model_on_split(
    model: dict[str, Any], storage: Any, coco_r2_key: str, split: str, coco: dict
) -> dict[str, Any]:
    """Baixa o ONNX do modelo, instancia o detector e avalia contra o split.

    Reusa _ensure_local_model (cache local keyed por model_id) de
    tasks/inference.py — mesmo helper usado pela inferência ao vivo,
    evita duplicar a lógica de download+cache atômico.
    """
    from app.domain.detectors.factory import FRAMEWORK_TO_BACKEND, get_detector
    from app.infrastructure.queue.tasks.inference import _ensure_local_model

    local_path = _ensure_local_model(str(model["id"]), model["r2_onnx_key"])
    backend = FRAMEWORK_TO_BACKEND.get(
        (model.get("framework") or "").lower(), model.get("framework") or "yolox_onnx"
    )
    detector = get_detector(
        backend=backend,
        model_path=local_path,
        class_names=_class_names_from_coco(coco),
        confidence=0.25,
    )

    per_image_preds, per_image_gts = _run_split_inference(
        detector, storage, coco_r2_key, split, coco
    )

    from app.domain.services.eval_metrics import (
        confusion_matrix as compute_confusion_matrix,
    )
    from app.domain.services.eval_metrics import (
        greedy_match,
        merge_confusion_matrices,
        merge_match_results,
        precision_recall_map,
    )

    match_results = [
        greedy_match(preds, gts, iou_threshold=_DEFAULT_IOU_THRESHOLD)
        for preds, gts in zip(per_image_preds, per_image_gts)
    ]
    confusion_results = [
        compute_confusion_matrix(preds, gts, iou_threshold=_DEFAULT_IOU_THRESHOLD)
        for preds, gts in zip(per_image_preds, per_image_gts)
    ]

    merged_matches = merge_match_results(match_results)
    pr_map = precision_recall_map(merged_matches)
    matrix = merge_confusion_matrices(confusion_results)

    return {"metrics": pr_map, "confusion_matrix": matrix, "images_evaluated": len(per_image_preds)}


def _piso_de_medicao(metrics: dict[str, Any]) -> str | None:
    """Motivo pelo qual esta avaliação NÃO mede nada — ou None se mede.

    Nasceu do issue #417: as 3 avaliações gravadas em model_evaluations tinham
    `tp=0` **e** `fp=0` em todas as classes — o modelo não emitiu uma única
    predição — e mesmo assim saíram com `verdict=promote` e `map50=0.0`.
    Ausência de medição estava sendo lida como aprovação.

    Um veredito só é veredito se houve o que julgar. Sem predição nenhuma, o que
    o número diz não é "o modelo é bom": é "o instrumento não mediu".
    """
    per_class = metrics.get("per_class") or {}
    tp = sum(int(d.get("tp") or 0) for d in per_class.values())
    fp = sum(int(d.get("fp") or 0) for d in per_class.values())
    if not per_class:
        return "sem classe avaliada — o split não produziu nenhuma métrica"
    if tp + fp == 0:
        return "modelo não emitiu nenhuma predição (tp=0 e fp=0 em todas as classes)"
    if tp == 0:
        return f"nenhum acerto — {fp} falso(s) positivo(s) e nenhum verdadeiro"
    if not (float(metrics.get("map50") or 0.0) > 0.0):
        return "map50 = 0"
    return None


def _decide_verdict(
    challenger_metrics: dict[str, Any], champion_metrics: dict[str, Any] | None
) -> str:
    """reject se a avaliação não mediu nada; senão promote quando não há campeão
    ou quando o desafiante não regride mais que a tolerância de mAP nem derruba
    recall de nenhuma classe além do limite."""
    from app.constants import EvalVerdict

    # ⚠️ Piso ANTES de qualquer comparação: sem campeão nunca mais é promoção
    # automática. Era exatamente esse ramo que aprovava modelo cego (#417).
    motivo = _piso_de_medicao(challenger_metrics)
    if motivo is not None:
        logger.error("evaluate_challenger_piso_reprovado: %s", motivo)
        return EvalVerdict.REJECT

    if champion_metrics is None:
        return EvalVerdict.PROMOTE

    if challenger_metrics["map50"] < champion_metrics["map50"] - _MAP_REGRESSION_TOLERANCE:
        return EvalVerdict.REJECT

    champion_per_class = champion_metrics.get("per_class", {})
    for cls, data in challenger_metrics.get("per_class", {}).items():
        champion_cls = champion_per_class.get(cls)
        if not champion_cls or champion_cls.get("recall") is None or data.get("recall") is None:
            continue
        if data["recall"] < champion_cls["recall"] - _RECALL_DROP_TOLERANCE:
            return EvalVerdict.REJECT

    return EvalVerdict.PROMOTE


@celery.task(
    bind=True,
    max_retries=2,
    queue="training",
    name="tasks.model_evaluation.evaluate_challenger_model",
)
def evaluate_challenger_model(self, model_id: str, dataset_version_id: str | None = None) -> dict:
    """Avalia um modelo desafiante contra o campeão ativo (se houver).

    Retornos:
      {"status": "skipped"}          — onnxruntime/numpy/cv2 indisponíveis
      {"status": "error", "reason"}  — modelo/dataset/split inexistente
      {"status": "completed", ...}   — avaliação gravada em model_evaluations
    """
    try:
        import cv2  # noqa: F401, PLC0415
        import numpy as np  # noqa: F401, PLC0415
        import onnxruntime  # noqa: F401, PLC0415
    except ImportError as exc:
        logger.warning(
            "evaluate_challenger_skipped: deps indisponíveis (%s) model=%s",
            exc, model_id,
        )
        return {"status": "skipped", "model_id": model_id, "reason": "ml_deps_unavailable"}

    registry_repo = _get_registry_repo()
    model = registry_repo.get_by_id(model_id)
    if model is None:
        logger.error("evaluate_challenger_model_not_found: model=%s", model_id)
        return {"status": "error", "model_id": model_id, "reason": "model_not_found"}

    if not model.get("r2_onnx_key"):
        logger.info(
            "evaluate_challenger_no_onnx: model=%s — avaliação pulada (sem artefato)",
            model_id,
        )
        return {"status": "error", "model_id": model_id, "reason": "missing_onnx_key"}

    tenant_id = model.get("tenant_id")
    module_code = model.get("module_code") or "epi"
    dsv_id = dataset_version_id or model.get("dataset_version_id")
    if not dsv_id:
        return {"status": "error", "model_id": model_id, "reason": "no_dataset_version"}

    dataset_repo = _get_dataset_repo()
    dataset_version = dataset_repo.get_by_id(dsv_id)
    if dataset_version is None:
        return {"status": "error", "model_id": model_id, "reason": "dataset_version_not_found"}

    coco_r2_key = dataset_version.get("coco_r2_key")
    split = _resolve_holdout_split(dataset_version)
    if not coco_r2_key or split is None:
        logger.warning(
            "evaluate_challenger_no_holdout: model=%s dataset_version=%s "
            "test_count=%s val_count=%s",
            model_id, dsv_id,
            dataset_version.get("test_count"), dataset_version.get("val_count"),
        )
        return {"status": "error", "model_id": model_id, "reason": "no_holdout_split"}

    storage = _get_storage(tenant_id)
    try:
        import json as _json
        coco_bytes = storage.download_bytes(f"{coco_r2_key}/{split}/_annotations.coco.json")
        coco = _json.loads(coco_bytes)
    except Exception as exc:
        logger.error(
            "evaluate_challenger_coco_download_failed: model=%s err=%s",
            model_id, exc, exc_info=True,
        )
        return {"status": "error", "model_id": model_id, "reason": "coco_download_failed"}

    try:
        challenger_result = _evaluate_model_on_split(model, storage, coco_r2_key, split, coco)
    except Exception as exc:
        logger.error(
            "evaluate_challenger_inference_failed: model=%s err=%s",
            model_id, exc, exc_info=True,
        )
        return {"status": "error", "model_id": model_id, "reason": "inference_failed"}

    if challenger_result["images_evaluated"] == 0:
        logger.error(
            "evaluate_challenger_sem_imagem: model=%s split=%s — nenhuma imagem do "
            "holdout foi avaliada; gravar isso como avaliação seria registrar "
            "ausência de medida como medida",
            model_id, split,
        )
        return {"status": "error", "model_id": model_id, "reason": "no_images_evaluated"}

    # Campeão atual do tenant+módulo (is_active=True) — se existir e for
    # diferente do próprio desafiante, roda o MESMO split nele pra
    # comparação justa (mesmas imagens, mesmo threshold de IoU).
    champion_id: str | None = None
    champion_metrics: dict[str, Any] | None = None
    if tenant_id:
        active_models = registry_repo.list_for_tenant(
            tenant_id, module_code=module_code, is_active=True
        )
        champion = next((m for m in active_models if str(m["id"]) != str(model_id)), None)
        if champion and champion.get("r2_onnx_key"):
            champion_id = str(champion["id"])
            try:
                champion_result = _evaluate_model_on_split(
                    champion, storage, coco_r2_key, split, coco
                )
                champion_metrics = champion_result["metrics"]
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "evaluate_challenger_champion_eval_failed: champion=%s err=%s",
                    champion_id, exc,
                )
                champion_id, champion_metrics = None, None

    verdict = _decide_verdict(challenger_result["metrics"], champion_metrics)

    metrics_payload = {
        **challenger_result["metrics"],
        "split_used": split,
        "iou_threshold": _DEFAULT_IOU_THRESHOLD,
        "images_evaluated": challenger_result["images_evaluated"],
        "champion_model_id": champion_id,
        "champion_map50": champion_metrics["map50"] if champion_metrics else None,
    }

    evaluation = _get_eval_repo().create({
        "tenant_id": tenant_id,
        "model_id": model_id,
        "champion_model_id": champion_id,
        "dataset_version_id": dsv_id,
        "metrics": metrics_payload,
        "confusion_matrix": challenger_result["confusion_matrix"],
        "verdict": verdict,
    })

    logger.info(
        "evaluate_challenger_completed: model=%s champion=%s verdict=%s map50=%.4f "
        "images=%d piso=%s",
        model_id, champion_id, verdict, challenger_result["metrics"]["map50"],
        challenger_result["images_evaluated"],
        _piso_de_medicao(challenger_result["metrics"]) or "ok",
    )
    return {
        "status": "completed",
        "model_id": model_id,
        "evaluation_id": str(evaluation["id"]) if evaluation else None,
        "verdict": verdict,
        "map50": challenger_result["metrics"]["map50"],
    }
