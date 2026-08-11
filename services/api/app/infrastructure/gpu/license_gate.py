"""
Recognition — Trava de licença para variantes RF-DETR (ADR-0044, decisão do dono).

O pacote `rfdetr` (github.com/roboflow/rf-detr) publica variantes Apache 2.0
— Nano/Small/Base/Medium, instaláveis via `pip install rfdetr` — e variantes
XLarge/2XLarge licenciadas sob PML 1.0 (Platform Model License, exigem
`pip install rfdetr[plus]`), NÃO Apache. ADR-0043 (AGPL-zero) e ADR-0044
(RF-DETR/YOLOX plugável) exigem que só licenças permissivas cheguem ao
caminho de treino/serving — nenhuma variante XL/2XL pode ser selecionada.

Estado hoje (2026-08): `training/vast/remote_train.py::train_rfdetr` sempre
usa `RFDETRBase()` fixo — nenhuma seleção de variante ainda chega até lá
(create_job_handler não expõe `base_model`/`hyperparams` na API pública
ainda). Esta trava existe como DEFESA EM PROFUNDIDADE, ANTES da UI/API
exporem seleção de variante — pra nunca depender de lembrar de adicioná-la
depois que o caminho já estiver aberto (mesmo espírito ADR-0017: falhar alto
e cedo, nunca descobrir o problema em produção).

Fonte: README do github.com/roboflow/rf-detr (split explícito Apache vs PML
por variante) — consultado 2026-08-10.
"""
from __future__ import annotations

from typing import Any

# Variantes Apache 2.0 do pacote `rfdetr` base (sem o extra `[plus]`).
# "large" existe upstream e também é Apache 2.0, mas fica FORA do allowlist
# por decisão de produto (ADR-0044: alvo é Jetson Orin NX — nano é o
# default de edge; large nunca foi validado no hardware alvo). Ampliar o
# allowlist é uma decisão de produto nova, não um bug desta trava.
ALLOWED_RFDETR_VARIANTS: frozenset[str] = frozenset({"nano", "small", "base", "medium"})

_LICENSE_MARKERS: tuple[str, ...] = ("xlarge", "2xlarge", "xl", "2xl")
_RFDETR_PREFIXES: tuple[str, ...] = (
    "rfdetr-", "rfdetr_", "rfdetr", "rf-detr-", "rf-detr_", "rf-detr",
)


class RfdetrLicenseError(ValueError):
    """Variante RF-DETR fora do allowlist Apache 2.0 (PML ou desconhecida)."""


def _normalize(raw: str) -> str:
    token = raw.strip().lower()
    for prefix in _RFDETR_PREFIXES:
        if token.startswith(prefix):
            token = token[len(prefix):]
            break
    return token.strip("-_ ")


def assert_rfdetr_variant_allowed(
    framework: str | None,
    base_model: str | None = None,
    hyperparams: dict[str, Any] | None = None,
) -> None:
    """Levanta `RfdetrLicenseError` se `framework == 'rfdetr'` e a variante
    pedida (via `base_model` ou `hyperparams`) não estiver no allowlist
    Apache 2.0 (nano/small/base/medium).

    No-op para qualquer outro framework (ex.: `yolox` — sempre Apache 2.0,
    sem variantes PML) e para variante ausente (None/"" — remote_train.py
    usa `RFDETRBase()` como default, já dentro do allowlist).

    Deliberadamente NÃO recebe `model_size` — esse campo é legado/genérico
    (ex.: default "yolo26n" herdado da era Ultralytics, presente em toda
    chamada de dispatch independente do framework real) e checá-lo aqui
    geraria falso-positivo em todo job rfdetr existente.
    """
    if (framework or "").strip().lower() not in ("rfdetr", "rf-detr"):
        return

    hp = hyperparams or {}
    candidates = [
        v for v in (
            base_model,
            hp.get("base_model"),
            hp.get("model_size"),
            hp.get("variant"),
        )
        if v
    ]
    for raw in candidates:
        normalized = _normalize(str(raw))
        if not normalized or normalized in ALLOWED_RFDETR_VARIANTS:
            continue
        license_hit = any(marker in normalized for marker in _LICENSE_MARKERS)
        reason = (
            "licenciada sob PML 1.0 (Platform Model License), não Apache 2.0 "
            "— exige `rfdetr[plus]`, fora do caminho servido (ADR-0043)"
            if license_hit else
            "não reconhecida no allowlist Apache 2.0 do RF-DETR"
        )
        raise RfdetrLicenseError(
            f"Variante RF-DETR {raw!r} rejeitada — {reason}. "
            f"Permitidas: {sorted(ALLOWED_RFDETR_VARIANTS)} (ADR-0044)."
        )
