"""
Recognition — Classificação Funcional/Parcial/Não avaliado (gate de ativação).

Um modelo só pode ser ATIVADO ou ATRIBUÍDO A UMA CÂMERA quando classificado
"funcional". Deriva 100% da ÚLTIMA linha de `model_evaluations` do modelo
(migration 101, já escrita por `tasks/model_evaluation.py`) — NENHUMA coluna
nova: a classificação é lida, nunca persistida (ponytail rung 1 — o dado
para decidir já existe).

Por quê `per_class[cls]["ap"]` e não `map50`/`is_active`/`verdict`:
  `eval_metrics.precision_recall_map` (domain/services/eval_metrics.py:157)
  grava `ap=None` exatamente quando `n_gt=0` — a classe apareceu (predita ou
  no ground-truth) mas o holdout não tinha exemplo nenhum dela para o
  modelo acertar ou errar. `ap=0.0` é uma MEDIDA real (o modelo errou tudo);
  `ap=None` é AUSÊNCIA de medida. Essa distinção (já resolvida no cálculo,
  nunca exposta antes) é o "n" que classifica o modelo:
    - nenhuma avaliação, ou avaliação sem nenhuma classe medida → não avaliado
    - avaliação com pelo menos uma classe SEM medida (ap=None) → parcial
    - todas as classes vistas na avaliação medidas (ap≠None) → funcional

LIMITAÇÃO CONHECIDA (documentada, não corrigida aqui — fora do escopo deste
gate): uma classe que NUNCA aparece em `per_class` (nem prevista, nem no
ground-truth de nenhuma imagem do holdout avaliado) é invisível a este
cálculo — ele só vê classes que o eval efetivamente tocou. Cobertura contra
o catálogo COMPLETO de classes do módulo (`GET /api/modules/{code}/classes`)
exigiria join com `module_classes`/taxonomia do tenant — puxaria para dentro
deste gate um problema de taxonomia já rastreado separadamente (censo em
paralelo). Quando o censo aumentar a cobertura real do holdout, este cálculo
reflete a melhora sozinho, sem mudança de código.
"""
from __future__ import annotations

from typing import Any, Optional

FUNCIONAL = "funcional"
PARCIAL = "parcial"
NAO_AVALIADO = "nao_avaliado"


def _mean(values: list[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def classify_model_evaluation(evaluation: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Classifica um modelo a partir da última avaliação campeão×desafiante.

    Retorna sempre as mesmas chaves:
      status              — FUNCIONAL | PARCIAL | NAO_AVALIADO
      motivo              — texto pt-BR para o usuário final, ou None se funcional
      map50/precision/recall — médias reais das classes MEDIDAS (None se
                            nenhuma classe foi medida — nunca 0.0 fingido)
      images_evaluated    — "n" da avaliação (mesmo n para as 3 métricas acima)
      classes_sem_medida  — nomes de classe com ap=None nesta avaliação
    """
    vazio = {
        "map50": None, "precision": None, "recall": None,
        "images_evaluated": None, "classes_sem_medida": [],
    }

    if evaluation is None:
        return {
            **vazio,
            "status": NAO_AVALIADO,
            "motivo": (
                "Este modelo nunca foi avaliado contra imagens de validação — "
                "não pode ser ativado nem atribuído a uma câmera até passar "
                "por uma avaliação."
            ),
        }

    metrics = evaluation.get("metrics") or {}
    per_class = metrics.get("per_class") or {}
    medidas = sorted(c for c, d in per_class.items() if d and d.get("ap") is not None)
    sem_medida = sorted(c for c, d in per_class.items() if not d or d.get("ap") is None)

    if not per_class or not medidas:
        return {
            **vazio,
            "status": NAO_AVALIADO,
            "images_evaluated": metrics.get("images_evaluated"),
            "classes_sem_medida": sem_medida,
            "motivo": (
                "A avaliação deste modelo não mediu nenhuma classe (sem "
                "imagens de validação com anotação real para julgar) — não "
                "pode ser ativado nem atribuído a uma câmera."
            ),
        }

    resultado = {
        "map50": metrics.get("map50"),
        "precision": _mean([per_class[c]["precision"] for c in medidas if per_class[c].get("precision") is not None]),
        "recall": _mean([per_class[c]["recall"] for c in medidas if per_class[c].get("recall") is not None]),
        "images_evaluated": metrics.get("images_evaluated"),
        "classes_sem_medida": sem_medida,
    }

    if sem_medida:
        return {
            **resultado,
            "status": PARCIAL,
            "motivo": (
                "Modelo avaliado, mas sem imagens de validação suficientes "
                f"para medir: {', '.join(sem_medida)}. Classificado como "
                "Parcial — não pode ser ativado nem atribuído a uma câmera "
                "até essas classes serem avaliadas."
            ),
        }

    return {**resultado, "status": FUNCIONAL, "motivo": None}
