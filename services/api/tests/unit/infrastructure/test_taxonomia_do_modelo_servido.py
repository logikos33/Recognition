"""O modelo servido não pode falar a taxonomia de outro domínio.

O ONNX devolve um ÍNDICE. Quem traduz índice→nome é o detector, a partir de
`class_names`. O caminho de AVALIAÇÃO passava essa lista
(`model_evaluation._class_names_from_coco`, cujo docstring descreve o perigo
com todas as letras); o caminho SERVIDO (`_get_detector_for_camera`) não
passava, e caía em `COCO_CLASSES_91`.

Medido no modelo real (v15, 61 detecções em frames do holdout): 61 de 61
rótulos trocados, com substituição sistemática —

    bus           -> Protetor auditivo        train -> mascara
    traffic light -> Botas                    truck -> Sem protetor de ouvido
    car           -> Sem Luvas                airplane -> Sem Óculos

E o defeito não aparecia como rótulo errado na tela, porque o filtro de escopo
(#519, `_no_escopo_da_camera`) compara o nome contra as classes da câmera:
com dicionário COCO nada casa, e as detecções somem — 100% descartado, um
`logger.debug`, zero alerta. Zero alerta lê igual a "não houve violação".

Por que ninguém viu: os 334 alertas do shadow têm nomes CERTOS porque não
saíram desta tarefa. Eles provam que o modelo funciona; não provam que o
caminho servido funciona.
"""
from __future__ import annotations

import logging
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

_CELERY_APP_KEY = "app.infrastructure.queue.celery_app"
_INFERENCE_KEY = "app.infrastructure.queue.tasks.inference"
_loaded = sys.modules.get(_CELERY_APP_KEY)
if _loaded is not None and getattr(_loaded, "__file__", None) is None:
    for _key in (_INFERENCE_KEY, _CELERY_APP_KEY):
        sys.modules.pop(_key, None)

from app.infrastructure.queue.tasks import inference as inference_mod  # noqa: E402

_CAMERA_ID = str(uuid4())
_MODEL_ID = str(uuid4())
_FACTORY = "app.domain.detectors.factory.get_detector"

# Ordem real do export RVB (v15): índice 0 é a dummy do RF-DETR.
_RVB = [
    "recognition", "Capacete", "Luvas", "Sem Luvas", "Óculos", "Sem Óculos",
    "Protetor auditivo", "mascara", "Sem protetor de ouvido", "Sem mascara",
    "Botas", "Uso incorreto de mascara",
]


def _limpa_cache():
    inference_mod._camera_detectors.clear()


class TestTaxonomiaChegaAoDetector:
    """O elo que estava faltando: resolvida ≠ entregue."""

    def setup_method(self):
        _limpa_cache()

    teardown_method = setup_method

    def test_class_names_do_modelo_e_repassado_a_factory(self):
        resolvido = {
            "model_id": _MODEL_ID,
            "framework": "rfdetr",
            "r2_onnx_key": "models/x.onnx",
            "class_names": _RVB,
            "classes": None,
        }
        with patch.object(
            inference_mod, "_resolve_camera_model", return_value=resolvido
        ), patch.object(
            inference_mod, "_ensure_local_model", return_value="/tmp/x.onnx"
        ), patch(_FACTORY, return_value=MagicMock()) as factory:
            inference_mod._get_detector_for_camera(_CAMERA_ID)

        entregue = factory.call_args.kwargs.get("class_names")
        assert entregue == _RVB, (
            "sem class_names o detector usa COCO_CLASSES_91 e todo rótulo sai "
            f"de outro domínio; recebeu {entregue!r}"
        )

    def test_o_escopo_da_camera_nao_e_confundido_com_a_taxonomia(self):
        """São coisas diferentes e vinham do mesmo dicionário.

        `classes` = recorte do admin (subconjunto, sem ordem, filtra a saída).
        `class_names` = ordem índice→nome gravada nos pesos (traduz a saída).
        Trocar um pelo outro rotularia pelo índice do recorte.
        """
        resolvido = {
            "model_id": _MODEL_ID,
            "framework": "rfdetr",
            "r2_onnx_key": "models/x.onnx",
            "class_names": _RVB,
            "classes": frozenset({"Botas", "Sem Luvas"}),
        }
        with patch.object(
            inference_mod, "_resolve_camera_model", return_value=resolvido
        ), patch.object(
            inference_mod, "_ensure_local_model", return_value="/tmp/x.onnx"
        ), patch(_FACTORY, return_value=MagicMock()) as factory:
            inference_mod._get_detector_for_camera(_CAMERA_ID)

        assert factory.call_args.kwargs["class_names"] == _RVB
        assert inference_mod._camera_detectors[_CAMERA_ID]["classes"] == frozenset(
            {"Botas", "Sem Luvas"}
        )


class TestSemTaxonomiaNaoServe:
    """Recusar é melhor do que rotular com dicionário inventado."""

    def test_resolucao_devolve_none_quando_a_taxonomia_nao_resolve(self, caplog):
        cam = {
            "id": _CAMERA_ID,
            "tenant_id": "11111111-2222-3333-4444-555555555555",
            "active_module": "epi",
            "model_epi_id": None,
        }
        registro = {
            "id": _MODEL_ID,
            "framework": "rfdetr",
            "r2_onnx_key": "k",
            "dataset_version_id": None,  # sem dataset não há ordem de classes
        }
        with patch(
            "app.infrastructure.database.connection.DatabasePool"
        ) as pool_cls, patch(
            "app.infrastructure.database.repositories."
            "camera_repository.CameraRepository"
        ) as cam_cls, patch(
            "app.infrastructure.database.repositories."
            "model_deployment_repository.ModelDeploymentRepository"
        ) as dep_cls, patch.object(
            inference_mod, "_fetch_trained_model", return_value=registro
        ):
            pool_cls.get_instance.return_value = MagicMock()
            cam_cls.MODEL_COLUMNS = {"epi": "model_epi_id"}
            cam_cls.return_value.get_by_id.return_value = cam
            dep_cls.return_value.get_active_for_camera.return_value = {
                "model_id": _MODEL_ID
            }
            with caplog.at_level(logging.ERROR):
                assert inference_mod._resolve_camera_model(_CAMERA_ID) is None

        assert "camera_model_sem_taxonomia" in caplog.text, (
            "recusar em silêncio repete o defeito noutra forma"
        )

    def test_taxonomia_sem_dataset_version_e_none(self):
        assert inference_mod._taxonomia_do_modelo(MagicMock(), None, "t") is None


class TestFiltroDeEscopoDenunciaDescarteTotal:
    """100% fora não é turno limpo — é dicionário errado."""

    def setup_method(self):
        _limpa_cache()

    teardown_method = setup_method

    def _com_escopo(self, escopo):
        inference_mod._camera_detectors[_CAMERA_ID] = {
            "model_id": _MODEL_ID,
            "detector": MagicMock(),
            "classes": escopo,
        }

    def test_descarte_total_vira_warning(self, caplog):
        self._com_escopo(frozenset({"Botas", "Sem Luvas"}))
        # exatamente o que o detector emitia sem class_names
        deteccoes = [{"class": "bus"}, {"class": "truck"}, {"class": "train"}]

        with caplog.at_level(logging.WARNING):
            assert inference_mod._no_escopo_da_camera(_CAMERA_ID, deteccoes) == []

        assert "camera_escopo_descartou_tudo" in caplog.text, (
            "era logger.debug — foi assim que a câmera muda passou despercebida"
        )

    def test_descarte_parcial_continua_silencioso(self, caplog):
        self._com_escopo(frozenset({"Botas"}))
        deteccoes = [{"class": "Botas"}, {"class": "Sem Luvas"}]

        with caplog.at_level(logging.WARNING):
            dentro = inference_mod._no_escopo_da_camera(_CAMERA_ID, deteccoes)

        assert dentro == [{"class": "Botas"}]
        assert "camera_escopo_descartou_tudo" not in caplog.text

    def test_sem_deteccao_nenhuma_nao_avisa(self, caplog):
        """Câmera sem detecção é o caso normal — avisar aqui seria ruído."""
        self._com_escopo(frozenset({"Botas"}))
        with caplog.at_level(logging.WARNING):
            assert inference_mod._no_escopo_da_camera(_CAMERA_ID, []) == []
        assert "camera_escopo_descartou_tudo" not in caplog.text
