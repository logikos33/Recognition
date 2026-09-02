"""
Tests: model_status.classify_model_evaluation — gate Funcional/Parcial/Não
avaliado (task "modelo PARCIAL não ativa").

Fixture real: per_class no shape gravado por
eval_metrics.precision_recall_map (ap=None quando n_gt=0 — AUSÊNCIA de
medida, distinta de ap=0.0, que é medida real).
"""
from app.domain.services.model_status import (
    FUNCIONAL,
    NAO_AVALIADO,
    PARCIAL,
    classify_model_evaluation,
)


def _eval(per_class: dict, images_evaluated: int = 100, map50: float = 0.5) -> dict:
    return {
        "verdict": "promote",
        "metrics": {"map50": map50, "images_evaluated": images_evaluated, "per_class": per_class},
    }


class TestNaoAvaliado:
    def test_no_evaluation_at_all(self):
        info = classify_model_evaluation(None)
        assert info["status"] == NAO_AVALIADO
        assert info["map50"] is None
        assert "nunca foi avaliado" in info["motivo"]

    def test_evaluation_with_empty_per_class(self):
        info = classify_model_evaluation(_eval(per_class={}))
        assert info["status"] == NAO_AVALIADO
        assert info["map50"] is None

    def test_evaluation_where_every_class_has_no_support(self):
        """Todas as classes vistas têm n_gt=0 (ap=None) — nada foi medido,
        mesmo a avaliação existindo (piso de medição, issue #417)."""
        info = classify_model_evaluation(_eval(per_class={
            "capacete": {"ap": None, "n_gt": 0, "tp": 0, "fp": 3, "fn": 0},
        }))
        assert info["status"] == NAO_AVALIADO
        assert info["map50"] is None


class TestParcial:
    def test_one_class_without_support_blocks_as_parcial(self):
        info = classify_model_evaluation(_eval(per_class={
            "capacete": {"ap": 0.9, "precision": 0.9, "recall": 0.9, "n_gt": 24},
            "oculos": {"ap": None, "n_gt": 0, "tp": 0, "fp": 0, "fn": 0},
        }, images_evaluated=360, map50=0.9))
        assert info["status"] == PARCIAL
        assert info["classes_sem_medida"] == ["oculos"]
        assert "oculos" in info["motivo"]
        # map50 real das classes medidas continua visível (não vira "—") —
        # é o "parcial" que impede ativar, não a ausência do número.
        assert info["map50"] == 0.9
        assert info["images_evaluated"] == 360

    def test_measured_zero_ap_is_not_confused_with_missing(self):
        """ap=0.0 (o modelo errou tudo nessa classe) é medida REAL — não deve
        contar como classe sem medida (LEI DA CASA: zero real ≠ ausência)."""
        info = classify_model_evaluation(_eval(per_class={
            "luvas": {"ap": 0.0, "precision": 0.0, "recall": 0.0, "n_gt": 6},
        }))
        assert info["status"] == FUNCIONAL
        assert info["classes_sem_medida"] == []


class TestFuncional:
    def test_all_classes_measured(self):
        info = classify_model_evaluation(_eval(per_class={
            "capacete": {"ap": 0.9, "precision": 0.8, "recall": 0.85, "n_gt": 24},
            "luvas": {"ap": 0.2, "precision": 0.3, "recall": 0.4, "n_gt": 25},
        }, images_evaluated=360, map50=0.55))
        assert info["status"] == FUNCIONAL
        assert info["motivo"] is None
        assert info["map50"] == 0.55
        assert info["precision"] == (0.8 + 0.3) / 2
        assert info["recall"] == (0.85 + 0.4) / 2
        assert info["images_evaluated"] == 360
        assert info["classes_sem_medida"] == []
