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


def _holdout(split="test", frame_ids=None, coco_r2_key="dataset-exports/tenant/1/v1"):
    """Holdout congelado (migration 131) — o que get_holdout devolve.

    Default sem `frame_ids`: dataset_version anterior à membresia persistida,
    que é o caso da maioria destes testes (foco na orquestração, não na
    membresia — essa tem suíte própria em test_holdout_membresia.py).
    """
    return {
        "dataset_version_id": DSV_ID, "coco_r2_key": coco_r2_key,
        "split": split, "frame_ids": frame_ids, "frozen": bool(frame_ids),
    }


def _fake_repos(monkeypatch, registry=None, dataset=None, eval_repo=None, storage=None):
    registry = registry or MagicMock()
    dataset = dataset or MagicMock()
    # Sem isto o holdout viria de um MagicMock e os testes passariam por
    # acidente, sobre um split que ninguém declarou.
    dataset.get_holdout.return_value = _holdout()
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
        """Versão sem holdout nenhum — nunca gerar veredito sem prova real."""
        registry, dataset, *_ = _fake_repos(monkeypatch)
        registry.get_by_id.return_value = self._base_model()
        dataset.get_by_id.return_value = self._base_dataset_version(
            test_count=0, val_count=0
        )
        dataset.get_holdout.return_value = None
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())

        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        assert result["status"] == "error"
        assert result["reason"] == "no_holdout_split"

    def test_falls_back_to_val_split_when_test_count_zero(self, monkeypatch):
        """A escolha test→val agora mora em DatasetRepository.get_holdout; a
        task só obedece ao que o holdout declarou. Ver test_holdout_membresia.py
        ::test_cai_para_val_quando_test_vazio para a escolha em si."""
        registry, dataset, eval_repo, storage = _fake_repos(monkeypatch)
        registry.get_by_id.return_value = self._base_model()
        registry.list_for_tenant.return_value = []
        dataset.get_by_id.return_value = self._base_dataset_version(test_count=0, val_count=3)
        dataset.get_holdout.return_value = _holdout(split="val")
        storage.download_bytes.return_value = _MINIMAL_COCO
        eval_repo.create.return_value = {"id": "eval-1"}
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())
        monkeypatch.setattr(
            model_evaluation,
            "_evaluate_model_on_split",
            lambda model, storage, coco_r2_key, split, coco: {
                "metrics": {
                    "map50": 0.5,
                    "per_class": {"helmet": {"ap": 0.5, "tp": 4, "fp": 1, "fn": 1}},
                },
                "confusion_matrix": {},
                "images_evaluated": 4,
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
                "metrics": {
                    "map50": 0.7,
                    "per_class": {"helmet": {"ap": 0.7, "tp": 7, "fp": 2, "fn": 1}},
                },
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
                        "per_class": {
                            "helmet": {
                                "ap": champion_map, "recall": champion_recall,
                                "tp": 9, "fp": 2, "fn": 1,
                            }
                        },
                    },
                    "confusion_matrix": {},
                    "images_evaluated": 10,
                }
            return {
                "metrics": {
                    "map50": challenger_map,
                    "per_class": {
                        "helmet": {
                            "ap": challenger_map, "recall": challenger_recall,
                            "tp": 8, "fp": 3, "fn": 2,
                        }
                    },
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
                "metrics": {
                    "map50": 0.6,
                    "per_class": {"helmet": {"ap": 0.6, "tp": 3, "fp": 1, "fn": 0}},
                },
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


class TestPisoDeMedicao:
    """Issue #417 — as 3 avaliações gravadas tinham tp=0 E fp=0 em todas as
    classes (o modelo não emitiu uma única predição) e saíram com
    verdict=promote. O gate do botão Ativar aprovava ausência de medição.

    Estes testes falham no código anterior ao piso: sem campeão, `_decide_verdict`
    devolvia PROMOTE sem olhar contagem nenhuma.
    """

    @staticmethod
    def _eval_com(per_class, map50=0.0, images=10):
        return lambda model, storage, coco_r2_key, split, coco: {
            "metrics": {"map50": map50, "per_class": per_class},
            "confusion_matrix": {},
            "images_evaluated": images,
        }

    def _rodar(self, monkeypatch, fake_eval):
        registry, dataset, eval_repo, storage = _fake_repos(monkeypatch)
        base = TestOrchestration()
        registry.get_by_id.return_value = base._base_model()
        registry.list_for_tenant.return_value = []  # ⚠️ sem campeão: era o ramo cego
        dataset.get_by_id.return_value = base._base_dataset_version()
        storage.download_bytes.return_value = _MINIMAL_COCO
        eval_repo.create.return_value = {"id": "eval-1"}
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())
        monkeypatch.setattr(model_evaluation, "_evaluate_model_on_split", fake_eval)
        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        return result, eval_repo

    def test_modelo_que_nao_emitiu_predicao_nunca_promove(self, monkeypatch):
        """tp=0 e fp=0 — exatamente o dado real do #417."""
        result, eval_repo = self._rodar(
            monkeypatch,
            self._eval_com({"helmet": {"ap": 0.0, "tp": 0, "fp": 0, "fn": 106}}),
        )
        assert result["verdict"] == "reject"
        assert eval_repo.create.call_args.args[0]["verdict"] == "reject"

    def test_modelo_so_com_falso_positivo_nunca_promove(self, monkeypatch):
        result, _ = self._rodar(
            monkeypatch,
            self._eval_com({"helmet": {"ap": 0.0, "tp": 0, "fp": 31, "fn": 106}}),
        )
        assert result["verdict"] == "reject"

    def test_per_class_vazio_nunca_promove(self, monkeypatch):
        result, _ = self._rodar(monkeypatch, self._eval_com({}, map50=0.9))
        assert result["verdict"] == "reject"

    def test_map50_zero_nunca_promove(self, monkeypatch):
        result, _ = self._rodar(
            monkeypatch,
            self._eval_com({"helmet": {"ap": 0.0, "tp": 2, "fp": 5, "fn": 100}}, map50=0.0),
        )
        assert result["verdict"] == "reject"

    def test_medicao_de_verdade_sem_campeao_promove(self, monkeypatch):
        """O piso não pode virar um 'reject sempre' — mede, então promove."""
        result, _ = self._rodar(
            monkeypatch,
            self._eval_com({"helmet": {"ap": 0.62, "tp": 13, "fp": 13, "fn": 92}}, map50=0.62),
        )
        assert result["verdict"] == "promote"

    def test_zero_imagem_avaliada_nao_vira_registro(self, monkeypatch):
        """Avaliação sobre nenhuma imagem não é avaliação — não se grava linha."""
        result, eval_repo = self._rodar(
            monkeypatch,
            self._eval_com({"helmet": {"ap": 0.0, "tp": 0, "fp": 0, "fn": 0}}, images=0),
        )
        assert result["status"] == "error"
        assert result["reason"] == "no_images_evaluated"
        eval_repo.create.assert_not_called()


class TestClassNamesFromCoco:
    """O detector traduz índice→nome. Sem as classes do dataset ele cai em
    COCO_CLASSES_91 e devolve "person"/"bicycle" contra um ground-truth de EPI —
    nada casa, e o zero parece do modelo (#417)."""

    def test_indexa_pelo_id_da_categoria(self):
        coco = {"categories": [{"id": 0, "name": "mascara"}, {"id": 1, "name": "oculos"}]}
        assert model_evaluation._class_names_from_coco(coco) == ["mascara", "oculos"]

    def test_buraco_de_id_fica_explicito(self):
        coco = {"categories": [{"id": 0, "name": "mascara"}, {"id": 2, "name": "oculos"}]}
        assert model_evaluation._class_names_from_coco(coco) == ["mascara", "?1", "oculos"]

    def test_sem_categoria_devolve_vazio(self):
        assert model_evaluation._class_names_from_coco({}) == []

    def test_id_absurdo_nao_aloca_lista_gigante(self):
        """COCO malformado com id enorme derrubaria o worker por alocação."""
        coco = {"categories": [{"id": 0, "name": "mascara"}, {"id": 10**7, "name": "oculos"}]}
        nomes = model_evaluation._class_names_from_coco(coco)
        assert nomes == ["mascara", "oculos"], "cai para a ordem, não aloca 10M"


class TestClassThresholds:
    """Limiar de produção por classe — o pico da curva F1, persistido no modelo."""

    def test_so_classes_com_pico_entram(self):
        limiares = model_evaluation._class_thresholds({
            "per_class": {
                "Luvas": {"best_threshold": 0.45},
                "Botas": {"best_threshold": None},   # F1 zero em toda a grade
                "Óculos": {"ap": None},              # sem GT no holdout
            }
        })
        assert limiares == {"Luvas": 0.45}

    def test_metrics_vazio_nao_explode(self):
        assert model_evaluation._class_thresholds({}) == {}
        assert model_evaluation._class_thresholds({"per_class": None}) == {}

    def test_persistidos_em_trained_models_metrics_com_proveniencia(self, monkeypatch):
        registry, dataset, eval_repo, storage = _fake_repos(monkeypatch)
        registry.get_by_id.return_value = {
            "id": MODEL_ID, "tenant_id": TENANT_ID, "module_code": "epi",
            "framework": "rfdetr", "r2_onnx_key": "models/c.onnx",
            "dataset_version_id": DSV_ID,
        }
        registry.list_for_tenant.return_value = []
        dataset.get_by_id.return_value = {
            "id": DSV_ID, "coco_r2_key": "dataset-exports/t/1/v1",
            "test_count": 5, "val_count": 2,
        }
        dataset.get_holdout.return_value = {
            "split": "test", "coco_r2_key": "dataset-exports/t/1/v1",
            "frame_ids": None, "frozen": False,
        }
        storage.download_bytes.return_value = _MINIMAL_COCO
        eval_repo.create.return_value = {"id": "eval-9"}
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())
        monkeypatch.setattr(
            model_evaluation, "_evaluate_model_on_split",
            lambda model, storage, coco_r2_key, split, coco: {
                "metrics": {
                    "map50": 0.7, "map50_95": 0.5,
                    "per_class": {
                        "Luvas": {"ap": 0.7, "tp": 7, "fp": 2, "fn": 1,
                                  "n_gt": 8, "best_threshold": 0.45},
                        "Botas": {"ap": 0.0, "tp": 0, "fp": 3, "fn": 4,
                                  "n_gt": 4, "best_threshold": None},
                    },
                },
                "confusion_matrix": {}, "images_evaluated": 10,
            },
        )

        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()

        assert result["class_thresholds"] == {"Luvas": 0.45}
        assert result["map50_95"] == 0.5
        registry.merge_metrics.assert_called_once()
        model_arg, payload = registry.merge_metrics.call_args.args
        assert model_arg == MODEL_ID
        assert payload["class_thresholds"] == {"Luvas": 0.45}
        origem = payload["class_thresholds_origem"]
        # o número tem de dizer de onde veio: método, prova, n e piso
        assert origem["metodo"] == "pico da curva F1 por classe"
        assert origem["evaluation_id"] == "eval-9"
        assert origem["split"] == "test"
        assert origem["confidence_floor"] == model_evaluation._EVAL_CONFIDENCE
        assert origem["images_evaluated"] == 10
        assert origem["n_gt_por_classe"] == {"Luvas": 8, "Botas": 4}
        assert origem["sem_limiar"] == ["Botas"]

    def test_falha_ao_persistir_nao_derruba_a_avaliacao(self, monkeypatch):
        registry, dataset, eval_repo, storage = _fake_repos(monkeypatch)
        registry.get_by_id.return_value = {
            "id": MODEL_ID, "tenant_id": TENANT_ID, "module_code": "epi",
            "framework": "rfdetr", "r2_onnx_key": "models/c.onnx",
            "dataset_version_id": DSV_ID,
        }
        registry.list_for_tenant.return_value = []
        registry.merge_metrics.side_effect = RuntimeError("banco fora")
        dataset.get_by_id.return_value = {
            "id": DSV_ID, "coco_r2_key": "dataset-exports/t/1/v1",
            "test_count": 5, "val_count": 0,
        }
        dataset.get_holdout.return_value = {
            "split": "test", "coco_r2_key": "dataset-exports/t/1/v1",
            "frame_ids": None, "frozen": False,
        }
        storage.download_bytes.return_value = _MINIMAL_COCO
        eval_repo.create.return_value = {"id": "eval-10"}
        monkeypatch.setitem(sys.modules, "onnxruntime", MagicMock())
        monkeypatch.setitem(sys.modules, "cv2", MagicMock())
        monkeypatch.setattr(
            model_evaluation, "_evaluate_model_on_split",
            lambda model, storage, coco_r2_key, split, coco: {
                "metrics": {
                    "map50": 0.7,
                    "per_class": {"Luvas": {"ap": 0.7, "tp": 7, "fp": 2,
                                            "fn": 1, "n_gt": 8,
                                            "best_threshold": 0.45}},
                },
                "confusion_matrix": {}, "images_evaluated": 10,
            },
        )

        result = model_evaluation.evaluate_challenger_model.apply(args=(MODEL_ID,)).get()
        assert result["status"] == "completed"  # a avaliação já está gravada
