"""
Tests: tasks/model_evaluation.py — avaliação campeão×desafiante (WS-C1).

Estratégia: repositórios/storage mockados via monkeypatch dos factories
(_get_registry_repo/_get_dataset_repo/_get_eval_repo/_get_storage — mesmo
padrão de test_models_registry_routes.py::TestValidateOnnxTask).
_evaluate_model_on_split é monkeypatchada diretamente nos testes de
orquestração (veredito/gate/holdout) — ela é testada via a instância real
somente na chamada síncrona apply(), com dependências ML (cv2/onnxruntime)
faltando de propósito pra provar o skip gracioso.
"""
from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock

from app.infrastructure.queue.tasks import model_evaluation

MODEL_ID = "55555555-5555-5555-5555-555555555555"
CHAMPION_ID = "66666666-6666-6666-6666-666666666666"
DSV_ID = "77777777-7777-7777-7777-777777777777"
TENANT_ID = "11111111-1111-1111-1111-111111111111"

_MINIMAL_COCO = json.dumps(
    {"categories": [{"id": 1, "name": "helmet"}], "images": [], "annotations": []}
).encode("utf-8")


def _fake_repos(monkeypatch, registry=None, dataset=None, eval_repo=None, storage=None):
    registry = registry or MagicMock()
    dataset = dataset or MagicMock()
    eval_repo = eval_repo or MagicMock()
    storage = storage or MagicMock()
    monkeypatch.setattr(model_evaluation, "_get_registry_repo", lambda: registry)
    monkeypatch.setattr(model_evaluation, "_get_dataset_repo", lambda: dataset)
    monkeypatch.setattr(model_evaluation, "_get_eval_repo", lambda: eval_repo)
    monkeypatch.setattr(model_evaluation, "_get_storage", lambda tenant_id=None: storage)
    return registry, dataset, eval_repo, storage


class TestMlDepsSkip:
    def test_skipped_when_onnxruntime_unavailable(self, monkeypatch):
        # cv2 real (instalado no venv) tem um bug de typing stub conhecido
        # (cv2.gapi.wip.draw sem atributo Text) que só se manifesta quando
        # importado pela primeira vez em processos com muitos módulos já
        # carregados (flakiness de suíte completa) — fake também o cv2 aqui
        # pra este teste focar só no gate onnxruntime, sem depender do
        # import real do cv2 nunca acontecer neste probe.
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())
        monkeypatch.setitem(sys.modules, "onnxruntime", None)
        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        assert result["status"] == "skipped"
        assert result["reason"] == "ml_deps_unavailable"

    def test_skipped_when_cv2_unavailable(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "cv2", None)
        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        assert result["status"] == "skipped"
        assert result["reason"] == "ml_deps_unavailable"


class TestOrchestration:
    def _base_model(self, **overrides):
        row = {
            "id": MODEL_ID,
            "tenant_id": TENANT_ID,
            "module_code": "epi",
            "framework": "rfdetr",
            "r2_onnx_key": "models/challenger.onnx",
            "dataset_version_id": DSV_ID,
        }
        row.update(overrides)
        return row

    def _base_dataset_version(self, **overrides):
        row = {
            "id": DSV_ID,
            "coco_r2_key": "dataset-exports/tenant/1/v1",
            "test_count": 5,
            "val_count": 2,
        }
        row.update(overrides)
        return row

    def test_model_not_found_returns_error(self, monkeypatch):
        registry, *_ = _fake_repos(monkeypatch)
        registry.get_by_id.return_value = None
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())

        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        assert result["status"] == "error"
        assert result["reason"] == "model_not_found"

    def test_missing_onnx_key_returns_error(self, monkeypatch):
        registry, *_ = _fake_repos(monkeypatch)
        registry.get_by_id.return_value = self._base_model(r2_onnx_key=None)
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())

        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        assert result["status"] == "error"
        assert result["reason"] == "missing_onnx_key"

    def test_no_dataset_version_returns_error(self, monkeypatch):
        registry, *_ = _fake_repos(monkeypatch)
        registry.get_by_id.return_value = self._base_model(dataset_version_id=None)
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())

        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        assert result["status"] == "error"
        assert result["reason"] == "no_dataset_version"

    def test_dataset_version_not_found_returns_error(self, monkeypatch):
        registry, dataset, *_ = _fake_repos(monkeypatch)
        registry.get_by_id.return_value = self._base_model()
        dataset.get_by_id.return_value = None
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())

        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        assert result["status"] == "error"
        assert result["reason"] == "dataset_version_not_found"

    def test_missing_holdout_split_returns_error(self, monkeypatch):
        """test_count==0 E val_count==0 — nunca gerar veredito sem holdout real."""
        registry, dataset, *_ = _fake_repos(monkeypatch)
        registry.get_by_id.return_value = self._base_model()
        dataset.get_by_id.return_value = self._base_dataset_version(
            test_count=0, val_count=0
        )
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())

        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        assert result["status"] == "error"
        assert result["reason"] == "no_holdout_split"

    def test_falls_back_to_val_split_when_test_count_zero(self, monkeypatch):
        registry, dataset, eval_repo, storage = _fake_repos(monkeypatch)
        registry.get_by_id.return_value = self._base_model()
        registry.list_for_tenant.return_value = []
        dataset.get_by_id.return_value = self._base_dataset_version(test_count=0, val_count=3)
        storage.download_bytes.return_value = _MINIMAL_COCO
        eval_repo.create.return_value = {"id": "eval-1"}
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())
        monkeypatch.setattr(
            model_evaluation,
            "_evaluate_model_on_split",
            lambda model, storage, coco_r2_key, split, coco: {
                "metrics": {"map50": 0.5, "per_class": {}},
                "confusion_matrix": {},
                "images_evaluated": 0,
            },
        )

        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        assert result["status"] == "completed"
        create_kwargs = eval_repo.create.call_args.args[0]
        assert create_kwargs["metrics"]["split_used"] == "val"

    def test_coco_download_failure_returns_error(self, monkeypatch):
        registry, dataset, _, storage = _fake_repos(monkeypatch)
        registry.get_by_id.return_value = self._base_model()
        dataset.get_by_id.return_value = self._base_dataset_version()
        storage.download_bytes.side_effect = RuntimeError("r2 down")
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())

        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        assert result["status"] == "error"
        assert result["reason"] == "coco_download_failed"

    def test_inference_failure_returns_error(self, monkeypatch):
        registry, dataset, _, storage = _fake_repos(monkeypatch)
        registry.get_by_id.return_value = self._base_model()
        dataset.get_by_id.return_value = self._base_dataset_version()
        storage.download_bytes.return_value = _MINIMAL_COCO
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())
        monkeypatch.setattr(
            model_evaluation,
            "_evaluate_model_on_split",
            MagicMock(side_effect=RuntimeError("detector init failed")),
        )

        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        assert result["status"] == "error"
        assert result["reason"] == "inference_failed"

    def test_no_champion_defaults_promote(self, monkeypatch):
        registry, dataset, eval_repo, storage = _fake_repos(monkeypatch)
        registry.get_by_id.return_value = self._base_model()
        registry.list_for_tenant.return_value = []  # sem campeão ativo
        dataset.get_by_id.return_value = self._base_dataset_version()
        storage.download_bytes.return_value = _MINIMAL_COCO
        eval_repo.create.return_value = {"id": "eval-1"}
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())
        monkeypatch.setattr(
            model_evaluation,
            "_evaluate_model_on_split",
            lambda model, storage, coco_r2_key, split, coco: {
                "metrics": {"map50": 0.7, "per_class": {}},
                "confusion_matrix": {},
                "images_evaluated": 10,
            },
        )

        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        assert result["status"] == "completed"
        assert result["verdict"] == "promote"
        eval_repo.create.assert_called_once()
        payload = eval_repo.create.call_args.args[0]
        assert payload["champion_model_id"] is None
        assert payload["verdict"] == "promote"

    def _run_with_champion(
        self, monkeypatch, challenger_map, champion_map,
        champion_recall=0.90, challenger_recall=0.90,
    ):
        registry, dataset, eval_repo, storage = _fake_repos(monkeypatch)
        registry.get_by_id.return_value = self._base_model()
        registry.list_for_tenant.return_value = [
            {"id": CHAMPION_ID, "r2_onnx_key": "models/champion.onnx", "framework": "rfdetr"}
        ]
        dataset.get_by_id.return_value = self._base_dataset_version()
        storage.download_bytes.return_value = _MINIMAL_COCO
        eval_repo.create.return_value = {"id": "eval-1"}
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())

        def _fake_eval(model, storage, coco_r2_key, split, coco):
            if str(model["id"]) == CHAMPION_ID:
                return {
                    "metrics": {
                        "map50": champion_map,
                        "per_class": {"helmet": {"ap": champion_map, "recall": champion_recall}},
                    },
                    "confusion_matrix": {},
                    "images_evaluated": 10,
                }
            return {
                "metrics": {
                    "map50": challenger_map,
                    "per_class": {"helmet": {"ap": challenger_map, "recall": challenger_recall}},
                },
                "confusion_matrix": {},
                "images_evaluated": 10,
            }

        monkeypatch.setattr(model_evaluation, "_evaluate_model_on_split", _fake_eval)
        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        return result, eval_repo

    def test_challenger_better_or_equal_promotes(self, monkeypatch):
        result, eval_repo = self._run_with_champion(
            monkeypatch, challenger_map=0.8, champion_map=0.75
        )
        assert result["verdict"] == "promote"
        payload = eval_repo.create.call_args.args[0]
        assert payload["champion_model_id"] == CHAMPION_ID

    def test_challenger_worse_than_champion_rejects(self, monkeypatch):
        result, _ = self._run_with_champion(
            monkeypatch, challenger_map=0.5, champion_map=0.8
        )
        assert result["verdict"] == "reject"

    def test_recall_drop_beyond_tolerance_rejects_even_with_similar_map(self, monkeypatch):
        # map50 quase igual (dentro da tolerância), mas recall da classe cai muito
        result, _ = self._run_with_champion(
            monkeypatch, challenger_map=0.79, champion_map=0.80,
            champion_recall=0.90, challenger_recall=0.70,
        )
        assert result["verdict"] == "reject"

    def test_creates_evaluation_row_with_confusion_matrix(self, monkeypatch):
        registry, dataset, eval_repo, storage = _fake_repos(monkeypatch)
        registry.get_by_id.return_value = self._base_model()
        registry.list_for_tenant.return_value = []
        dataset.get_by_id.return_value = self._base_dataset_version()
        storage.download_bytes.return_value = _MINIMAL_COCO
        eval_repo.create.return_value = {"id": "eval-1"}
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())
        monkeypatch.setattr(
            model_evaluation,
            "_evaluate_model_on_split",
            lambda model, storage, coco_r2_key, split, coco: {
                "metrics": {"map50": 0.6, "per_class": {}},
                "confusion_matrix": {"helmet": {"helmet": 3}},
                "images_evaluated": 3,
            },
        )

        model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        payload = eval_repo.create.call_args.args[0]
        assert payload["confusion_matrix"] == {"helmet": {"helmet": 3}}
        assert payload["tenant_id"] == TENANT_ID
        assert payload["model_id"] == MODEL_ID
        assert payload["dataset_version_id"] == DSV_ID
