"""
Tests: tasks/inference.py — resolução de modelo efetivo por câmera (WS-A6).

Cobre:
- Cascata de resolução: model_deployments ativo > cameras.model_{module}_id
  > fallback env (sem pool / sem modelo / sem r2_onnx_key → None)
- _fetch_trained_model: query tenant-scoped (params model_id + tenant_id)
- Cache de detector por câmera keyed por model_id: hit (não re-baixa),
  miss (modelo mudou → rebuild), falha de download/init → fallback env
- _ensure_local_model: skip se arquivo já existe; download + escrita quando não
- Invalidação via canal Redis camera:model_change (drain + invalidate)
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

# Garante import REAL de celery_app/inference mesmo que outro arquivo de teste
# tenha deixado um stub de celery_app em sys.modules (padrão pré-existente de
# tests/unit/domain/test_versioning_helpers.py). Stubs via types.ModuleType
# não têm __file__ — é o marcador para evictar e reimportar o real.
_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_INFERENCE_KEY = "app.infrastructure.queue.tasks.inference"
_loaded = sys.modules.get(_CELERY_APP_KEY)
if _loaded is not None and getattr(_loaded, "__file__", None) is None:
    for _key in (_INFERENCE_KEY, _CELERY_APP_KEY):
        sys.modules.pop(_key, None)

from app.infrastructure.queue.tasks import inference as inference_mod  # noqa: E402

_CAMERA_ID = str(uuid4())
_TENANT_ID = "99999999-8888-7777-6666-555555555555"
_DEPLOY_MODEL_ID = str(uuid4())
_CAMERA_MODEL_ID = str(uuid4())
_DATASET_VERSION_ID = str(uuid4())

_DBPOOL = "app.infrastructure.database.connection.DatabasePool"
_CAM_REPO = (
    "app.infrastructure.database.repositories.camera_repository.CameraRepository"
)
_DEPLOY_REPO = (
    "app.infrastructure.database.repositories."
    "model_deployment_repository.ModelDeploymentRepository"
)
_TRAINING_REPO = (
    "app.infrastructure.database.repositories.training_repository.TrainingRepository"
)
_FACTORY = "app.domain.detectors.factory.get_detector"
_GET_STORAGE = "app.infrastructure.storage.local_storage.get_storage"

_MODEL_COLUMNS = {
    "epi": "model_epi_id",
    "quality": "model_quality_id",
    "counting": "model_counting_id",
}


@pytest.fixture(autouse=True)
def _clean_camera_cache():
    """Isola o cache por-processo entre testes."""
    inference_mod._camera_detectors.clear()
    yield
    inference_mod._camera_detectors.clear()


def _camera_row(model_epi_id: str | None = None) -> dict:
    return {
        "id": _CAMERA_ID,
        "tenant_id": _TENANT_ID,
        "active_module": "epi",
        "model_epi_id": model_epi_id,
        "model_quality_id": None,
        "model_counting_id": None,
    }


_TAXONOMIA = ["recognition", "Luvas", "Sem Luvas", "Botas"]


def _registry_row(framework: str | None = "rfdetr", r2_key: str | None = "k") -> dict:
    return {
        "id": _DEPLOY_MODEL_ID,
        "framework": framework,
        "r2_onnx_key": r2_key,
        "model_path": "models/legacy/best.pt",
        "dataset_version_id": _DATASET_VERSION_ID,
    }


def _resolve(camera=None, deployment=None, model=None, pool=MagicMock(),
             taxonomia=_TAXONOMIA):
    """Executa _resolve_camera_model com a cascata inteira mockada.

    `taxonomia` é a ordem índice→classe do modelo. É pré-condição de servir:
    sem ela o detector rotularia em COCO e o escopo descartaria tudo, então
    `_resolve_camera_model` recusa. Passar None exercita essa recusa.
    """
    with patch(_DBPOOL) as mock_pool_cls, \
         patch(_CAM_REPO) as mock_cam_cls, \
         patch(_DEPLOY_REPO) as mock_dep_cls, \
         patch.object(
             inference_mod, "_taxonomia_do_modelo", return_value=taxonomia
         ), \
         patch.object(
             inference_mod, "_fetch_trained_model", return_value=model
         ) as mock_fetch:
        mock_pool_cls.get_instance.return_value = pool
        mock_cam_cls.MODEL_COLUMNS = _MODEL_COLUMNS
        mock_cam_cls.return_value.get_by_id.return_value = camera
        mock_dep_cls.return_value.get_active_for_camera.return_value = deployment
        result = inference_mod._resolve_camera_model(_CAMERA_ID)
    return result, mock_fetch, mock_dep_cls.return_value


# ── Cascata de resolução ──────────────────────────────────────────────────────

class TestResolveCameraModel:
    def test_deployment_ativo_tem_precedencia_sobre_coluna_da_camera(self):
        result, mock_fetch, dep_repo = _resolve(
            camera=_camera_row(model_epi_id=_CAMERA_MODEL_ID),
            deployment={"model_id": _DEPLOY_MODEL_ID},
            model=_registry_row(),
        )
        assert result is not None
        assert result["model_id"] == _DEPLOY_MODEL_ID
        assert result["framework"] == "rfdetr"
        assert result["r2_onnx_key"] == "k"
        # registry consultado com o model do deployment + tenant da câmera
        mock_fetch.assert_called_once()
        _, fetched_model_id, fetched_tenant = mock_fetch.call_args[0]
        assert fetched_model_id == _DEPLOY_MODEL_ID
        assert fetched_tenant == _TENANT_ID
        # deployment lookup é tenant+module scoped
        dep_args = dep_repo.get_active_for_camera.call_args[0]
        assert dep_args[0] == _TENANT_ID
        assert dep_args[2] == "epi"

    def test_sem_deployment_usa_model_epi_id_da_camera(self):
        result, mock_fetch, _ = _resolve(
            camera=_camera_row(model_epi_id=_CAMERA_MODEL_ID),
            deployment=None,
            model={**_registry_row(), "id": _CAMERA_MODEL_ID},
        )
        assert result is not None
        assert result["model_id"] == _CAMERA_MODEL_ID
        assert mock_fetch.call_args[0][1] == _CAMERA_MODEL_ID

    def test_sem_deployment_e_sem_coluna_retorna_none(self):
        result, mock_fetch, _ = _resolve(
            camera=_camera_row(model_epi_id=None), deployment=None
        )
        assert result is None
        mock_fetch.assert_not_called()

    def test_sem_pool_retorna_none(self):
        result, _, _ = _resolve(camera=_camera_row(), pool=None)
        assert result is None

    def test_camera_inexistente_retorna_none(self):
        result, _, _ = _resolve(camera=None)
        assert result is None

    def test_modelo_sem_r2_onnx_key_retorna_none(self):
        result, _, _ = _resolve(
            camera=_camera_row(),
            deployment={"model_id": _DEPLOY_MODEL_ID},
            model=_registry_row(r2_key=None),
        )
        assert result is None

    def test_modelo_fora_do_tenant_retorna_none(self):
        # _fetch_trained_model tenant-scoped não acha o modelo → fallback
        result, _, _ = _resolve(
            camera=_camera_row(),
            deployment={"model_id": _DEPLOY_MODEL_ID},
            model=None,
        )
        assert result is None


class TestFetchTrainedModel:
    def test_query_e_tenant_scoped(self):
        pool = MagicMock()
        with patch(_TRAINING_REPO) as mock_repo_cls:
            mock_repo_cls.return_value._execute_one.return_value = _registry_row()
            row = inference_mod._fetch_trained_model(
                pool, _DEPLOY_MODEL_ID, _TENANT_ID
            )
        assert row == _registry_row()
        query, params = mock_repo_cls.return_value._execute_one.call_args[0]
        assert "u.tenant_id = %s" in query
        assert "r2_onnx_key" in query
        assert params == (_DEPLOY_MODEL_ID, _TENANT_ID)


# ── Cache do detector por câmera ──────────────────────────────────────────────

class TestGetDetectorForCamera:
    def test_fallback_env_quando_nao_ha_modelo(self):
        env_detector = MagicMock(name="env_detector")
        with patch.object(
            inference_mod, "_resolve_camera_model", return_value=None
        ), patch.object(
            inference_mod, "_get_detector", return_value=env_detector
        ) as mock_env:
            result = inference_mod._get_detector_for_camera(_CAMERA_ID)
        assert result is env_detector
        mock_env.assert_called_once()
        assert inference_mod._camera_detectors == {}

    def test_fallback_env_quando_resolucao_lanca_excecao(self):
        env_detector = MagicMock(name="env_detector")
        with patch.object(
            inference_mod, "_resolve_camera_model", side_effect=RuntimeError("db")
        ), patch.object(
            inference_mod, "_get_detector", return_value=env_detector
        ):
            result = inference_mod._get_detector_for_camera(_CAMERA_ID)
        assert result is env_detector

    def test_cache_hit_nao_rebaixa_modelo(self):
        cached_detector = MagicMock(name="cached_detector")
        inference_mod._camera_detectors[_CAMERA_ID] = {
            "model_id": _DEPLOY_MODEL_ID,
            "detector": cached_detector,
        }
        resolved = {
            "model_id": _DEPLOY_MODEL_ID,
            "framework": "rfdetr",
            "r2_onnx_key": "k",
        }
        with patch.object(
            inference_mod, "_resolve_camera_model", return_value=resolved
        ), patch.object(
            inference_mod, "_ensure_local_model"
        ) as mock_ensure, patch(_FACTORY) as mock_factory:
            result = inference_mod._get_detector_for_camera(_CAMERA_ID)
        assert result is cached_detector
        mock_ensure.assert_not_called()
        mock_factory.assert_not_called()

    def test_cache_miss_modelo_mudou_reconstroi_detector(self):
        old_detector = MagicMock(name="old_detector")
        new_model_id = str(uuid4())
        inference_mod._camera_detectors[_CAMERA_ID] = {
            "model_id": _DEPLOY_MODEL_ID,
            "detector": old_detector,
        }
        resolved = {
            "model_id": new_model_id,
            "framework": "rfdetr",
            "r2_onnx_key": "models/new.onnx",
            "class_names": _TAXONOMIA,
        }
        new_detector = MagicMock(name="new_detector")
        local_path = f"/tmp/models/{new_model_id}.onnx"
        with patch.object(
            inference_mod, "_resolve_camera_model", return_value=resolved
        ), patch.object(
            inference_mod, "_ensure_local_model", return_value=local_path
        ) as mock_ensure, patch(_FACTORY, return_value=new_detector) as mock_factory:
            result = inference_mod._get_detector_for_camera(_CAMERA_ID)

        assert result is new_detector
        mock_ensure.assert_called_once_with(new_model_id, "models/new.onnx")
        mock_factory.assert_called_once_with(
            backend="rfdetr",
            model_path=local_path,
            # A taxonomia do modelo TEM de chegar ao detector: sem ela ele usa
            # COCO_CLASSES_91 e "Sem protetor de ouvido" vira "truck".
            class_names=_TAXONOMIA,
            confidence=inference_mod._DETECTION_CONFIDENCE,
        )
        assert inference_mod._camera_detectors[_CAMERA_ID] == {
            "model_id": new_model_id,
            "detector": new_detector,
            # Escopo de classes da câmera (#519) viaja junto do detector, para
            # a troca de modelo e a troca de escopo invalidarem no mesmo ponto.
            "classes": None,
        }

    def test_framework_ausente_usa_backend_env(self):
        resolved = {
            "model_id": _DEPLOY_MODEL_ID,
            "framework": None,
            "r2_onnx_key": "k",
        }
        with patch.object(
            inference_mod, "_resolve_camera_model", return_value=resolved
        ), patch.object(
            inference_mod, "_ensure_local_model", return_value="/tmp/models/x.onnx"
        ), patch(_FACTORY, return_value=MagicMock()) as mock_factory:
            inference_mod._get_detector_for_camera(_CAMERA_ID)
        assert (
            mock_factory.call_args.kwargs["backend"] == inference_mod._DETECTOR_BACKEND
        )

    def test_troca_de_arquitetura_por_camera_aplica_sem_restart(self):
        """task-083 (aceite): trocar a arquitetura (YOLOX → RF-DETR) atribuída
        a uma câmera precisa refletir no próximo frame processado pelo MESMO
        processo worker — sem restart. A troca de arquitetura sempre viaja
        junto com uma troca de model_id (framework é propriedade do registro
        em trained_models, não um campo solto), então o cache keyed por
        model_id já cobre o caso — este teste fixa esse comportamento
        end-to-end: cache quente com YOLOX, reassign para um modelo RF-DETR,
        detector reconstruído com backend="rfdetr" sem qualquer reimport ou
        reinicialização do módulo.
        """
        yolox_model_id = _DEPLOY_MODEL_ID
        rfdetr_model_id = str(uuid4())

        yolox_detector = MagicMock(name="yolox_detector")
        inference_mod._camera_detectors[_CAMERA_ID] = {
            "model_id": yolox_model_id,
            "detector": yolox_detector,
        }

        # 1) Antes da troca: cache hit, continua servindo YOLOX.
        with patch.object(
            inference_mod, "_resolve_camera_model",
            return_value={
                "model_id": yolox_model_id,
                "framework": "yolox",
                "r2_onnx_key": "models/yolox.onnx",
            },
        ), patch(_FACTORY) as mock_factory_before:
            before = inference_mod._get_detector_for_camera(_CAMERA_ID)
        assert before is yolox_detector
        mock_factory_before.assert_not_called()

        # 2) Admin reatribui a câmera a um modelo RF-DETR (via PUT
        #    /cameras/<id>/models) — o handler publica camera:model_change,
        #    que o worker drena e invalida o cache local (mesmo mecanismo
        #    de _invalidate_camera_detector/_drain_model_change).
        inference_mod._invalidate_camera_detector(_CAMERA_ID)

        # 3) Próxima chamada, MESMO PROCESSO, sem restart: resolve o novo
        #    modelo e reconstroi o detector com o backend correto.
        rfdetr_detector = MagicMock(name="rfdetr_detector")
        local_path = f"/tmp/models/{rfdetr_model_id}.onnx"
        with patch.object(
            inference_mod, "_resolve_camera_model",
            return_value={
                "model_id": rfdetr_model_id,
                "framework": "rfdetr",
                "r2_onnx_key": "models/rfdetr.onnx",
                "class_names": _TAXONOMIA,
            },
        ), patch.object(
            inference_mod, "_ensure_local_model", return_value=local_path,
        ) as mock_ensure, patch(
            _FACTORY, return_value=rfdetr_detector,
        ) as mock_factory_after:
            after = inference_mod._get_detector_for_camera(_CAMERA_ID)

        assert after is rfdetr_detector
        assert after is not before
        mock_ensure.assert_called_once_with(rfdetr_model_id, "models/rfdetr.onnx")
        mock_factory_after.assert_called_once_with(
            backend="rfdetr",
            model_path=local_path,
            class_names=_TAXONOMIA,
            confidence=inference_mod._DETECTION_CONFIDENCE,
        )
        assert inference_mod._camera_detectors[_CAMERA_ID]["model_id"] == rfdetr_model_id

    def test_falha_de_download_faz_fallback_env_sem_poluir_cache(self):
        env_detector = MagicMock(name="env_detector")
        resolved = {
            "model_id": _DEPLOY_MODEL_ID,
            "framework": "rfdetr",
            "r2_onnx_key": "k",
        }
        with patch.object(
            inference_mod, "_resolve_camera_model", return_value=resolved
        ), patch.object(
            inference_mod, "_ensure_local_model", side_effect=OSError("r2 down")
        ), patch.object(
            inference_mod, "_get_detector", return_value=env_detector
        ):
            result = inference_mod._get_detector_for_camera(_CAMERA_ID)
        assert result is env_detector
        assert inference_mod._camera_detectors == {}


# ── Cache local do ONNX ───────────────────────────────────────────────────────

class TestEnsureLocalModel:
    def test_skip_download_se_arquivo_existe(self, tmp_path, monkeypatch):
        monkeypatch.setattr(inference_mod, "_MODEL_CACHE_DIR", str(tmp_path))
        model_id = str(uuid4())
        existing = tmp_path / f"{model_id}.onnx"
        existing.write_bytes(b"cached-onnx")
        with patch(_GET_STORAGE) as mock_get_storage:
            path = inference_mod._ensure_local_model(model_id, "models/x.onnx")
        assert path == str(existing)
        mock_get_storage.assert_not_called()

    def test_download_quando_nao_existe(self, tmp_path, monkeypatch):
        monkeypatch.setattr(inference_mod, "_MODEL_CACHE_DIR", str(tmp_path))
        model_id = str(uuid4())
        storage = MagicMock()
        storage.download_bytes.return_value = b"onnx-bytes"
        with patch(_GET_STORAGE, return_value=storage):
            path = inference_mod._ensure_local_model(model_id, "models/x.onnx")
        storage.download_bytes.assert_called_once_with("models/x.onnx")
        assert path == str(tmp_path / f"{model_id}.onnx")
        assert (tmp_path / f"{model_id}.onnx").read_bytes() == b"onnx-bytes"
        # escrita atômica: nenhum .tmp sobrando
        assert list(tmp_path.glob("*.tmp")) == []


# ── Invalidação via camera:model_change ───────────────────────────────────────

class _FakePubSub:
    def __init__(self, messages):
        self._messages = list(messages)

    def get_message(self, ignore_subscribe_messages=True, timeout=0):
        if self._messages:
            return self._messages.pop(0)
        return None


class TestModelChangeInvalidation:
    def test_invalidate_remove_entrada_do_cache(self):
        inference_mod._camera_detectors[_CAMERA_ID] = {
            "model_id": _DEPLOY_MODEL_ID,
            "detector": MagicMock(),
        }
        inference_mod._invalidate_camera_detector(_CAMERA_ID)
        assert _CAMERA_ID not in inference_mod._camera_detectors

    def test_invalidate_e_noop_sem_entrada(self):
        inference_mod._invalidate_camera_detector(_CAMERA_ID)  # não lança
        assert inference_mod._camera_detectors == {}

    def test_drain_retorna_true_com_mensagem_e_drena_fila(self):
        pubsub = _FakePubSub([
            {"type": "message", "data": "{}"},
            {"type": "message", "data": "{}"},
        ])
        assert inference_mod._drain_model_change(pubsub) is True
        assert pubsub._messages == []

    def test_drain_retorna_false_sem_mensagens(self):
        assert inference_mod._drain_model_change(_FakePubSub([])) is False

    def test_drain_retorna_false_para_pubsub_none(self):
        assert inference_mod._drain_model_change(None) is False

    def test_subscribe_best_effort_retorna_none_em_falha(self):
        redis_client = MagicMock()
        redis_client.pubsub.side_effect = ConnectionError("redis down")
        assert (
            inference_mod._subscribe_model_change(redis_client, _CAMERA_ID) is None
        )

    def test_subscribe_assina_canal_da_camera(self):
        redis_client = MagicMock()
        pubsub = inference_mod._subscribe_model_change(redis_client, _CAMERA_ID)
        assert pubsub is redis_client.pubsub.return_value
        pubsub.subscribe.assert_called_once_with(
            f"camera:model_change:{_CAMERA_ID}"
        )
