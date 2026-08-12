"""
Recognition — Resolução do provider de GPU da propagação semeada (edge vs
nuvem de terceiro) e guard por DESTINO (nunca por flag).

Fonte única usada tanto pelo CREATE (`api/v1/training/propagation_handlers.py`)
quanto pelo DISPATCH (`infrastructure/queue/tasks/propagation.py`) — os dois
precisam concordar em exatamente a mesma resolução/classificação, senão um
job poderia ser criado como "onsite" e despachado como "offsite" (ou
vice-versa) por causa de uma diferença sutil entre duas implementações.

Precedência de `resolve_propagation_provider`: `provider` explícito no
corpo do request > env `PROPAGATION_GPU_PROVIDER` > default `runpod`
(retrocompat — nenhum tenant que já usa a nuvem de terceiro muda de
comportamento por causa desta mudança; DEV passa a ter
`PROPAGATION_GPU_PROVIDER=edge` como configuração de ambiente, não como
mudança de default de código).

`is_offsite`/`is_onsite` são wrappers finos sobre
`app.constants.OFFSITE_PROVIDERS`/`ONSITE_PROVIDERS` — nunca reimplementam
a classificação (fonte única em constants.py, com o guard fail-closed de
"provider sem classificação" já verificado na importação daquele módulo).
"""
from __future__ import annotations

import os

from app.constants import OFFSITE_PROVIDERS, ONSITE_PROVIDERS, GpuProvider

_ENV_VAR = "PROPAGATION_GPU_PROVIDER"
_DEFAULT_PROVIDER = GpuProvider.RUNPOD


class InvalidGpuProviderError(ValueError):
    """`provider` explícito no request, ou env PROPAGATION_GPU_PROVIDER,
    não é um valor conhecido de `app.constants.GpuProvider`."""


def resolve_propagation_provider(requested: "str | None") -> GpuProvider:
    """Resolve o `GpuProvider` de um job de propagação.

    `requested` vindo de `data.get("provider")`/`request.args.get("provider")`
    tem prioridade sobre a env — permite um operador pedir explicitamente
    `provider=runpod` mesmo com `PROPAGATION_GPU_PROVIDER=edge` no ambiente
    (ex.: comparar os dois pipelines lado a lado). `None`/string vazia caem
    pra env, que por sua vez cai pro default `runpod`.

    Levanta `InvalidGpuProviderError` pra qualquer valor que não seja um
    membro de `GpuProvider` — o caller HTTP converte em 400 com a mensagem
    já pronta (nunca cai silenciosamente num provider errado).
    """
    raw = requested if requested else os.environ.get(_ENV_VAR)
    if not raw:
        return _DEFAULT_PROVIDER
    try:
        return GpuProvider(str(raw).strip().lower())
    except ValueError as exc:
        valid = sorted(p.value for p in GpuProvider)
        raise InvalidGpuProviderError(
            f"provider inválido: {raw!r} (valores aceitos: {valid})"
        ) from exc


def is_offsite(provider: "GpuProvider | str") -> bool:
    return GpuProvider(provider) in OFFSITE_PROVIDERS


def is_onsite(provider: "GpuProvider | str") -> bool:
    return GpuProvider(provider) in ONSITE_PROVIDERS
