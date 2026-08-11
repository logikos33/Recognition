"""
Recognition — Abstração TrainingCompute (WS-D1, ADR-0039).

Decompõe a escolha de "onde treinar" de `tasks/training.py::dispatch_training`
numa interface única, pra permitir plugar um provedor novo (edge) sem tocar a
lógica de dispatch já provada em produção (Vast.ai REST real, WS-A4).

`compute_target` REUSA `training_jobs.gpu_provider` (migration 097) — mesma
decisão do PR-4 de não criar coluna nova quando uma já serve (achado de
grounding: aqui `gpu_provider` já é gravado hoje com `'vast_ai'`/`'local'`/
`'colab'`, só faltava o valor `'edge'` no enum, app/constants.py::GpuProvider).

Contrato de retorno de `dispatch()` (dict, mesmo shape que `_dispatch_vast_ai`
já usa):
  {"model_path": str, "metrics": dict, "source": str, "status"?: "completed"|"running"}
`status` ausente == "completed" (retrocompat com o dispatcher síncrono já
existente). "running" sinaliza dispatch assíncrono (hoje só EdgeProvider
— o job fica "running" e NÃO cria `trained_models`; a finalização real
depende de um callback que ainda não existe, ver PENDÊNCIA abaixo).

VastAiProvider é um wrapper fino sobre a função já existente e testada em
`tasks/training.py` (`_dispatch_vast_ai`) — import tardio (dentro de
dispatch()) para evitar ciclo de import (training.py importa este módulo no
nível de módulo).

EdgeProvider é BLOQUEADO-HARDWARE: enfileira um edge_command
`start_training` (mesma fila já usada por `update_camera_config`,
`app/api/v1/cameras/config_handler.py`) pro edge-sync-agent processar —
mas o edge-sync-agent NÃO tem hoje um handler pra esse tipo de comando nem
um script de treino real (equivalente ao `remote_train.py` do Vast.ai) pra
rodar num Jetson. Nunca validado contra hardware real — ver issue de
validação de hardware (mesmo padrão da issue #131, NVR/DVR).

ADR-0017 (fail loud, não fallback silencioso) — task "treino honesto"
(ADR-0060) + task "treino não pode mentir" (ADR desta task, supersede
parcial da ADR-0060): `get_training_compute` ANTES caía em `LocalProvider`
(simulação — sleep + métricas fabricadas por fórmula, nenhum artefato real)
por default sempre que não havia chave Vast.ai nem edge_site disponível —
NENHUMA flag, NENHUM sinal pro usuário, artefato fake indistinguível de um
treino real. Terceira aparição dessa doença no projeto. A ADR-0060 primeiro
colocou simulação atrás de opt-in explícito (env TRAINING_SIMULATION_ENABLED);
esta task vai além e DELETA `LocalProvider`/`_simulate_training` de vez —
simulação nunca foi um treino real, só um opt-in mais bonito pro mesmo
engano. `GpuProvider.LOCAL` continua existindo no enum (linhagem de dados
legados e configuração explícita) mas não tem mais NENHUM provider por trás:
um tenant com `training_compute_target='local'` recebe erro claro ("treino
local não suportado"), nunca uma simulação. Sem provedor real disponível:
RuntimeError com mensagem clara — dispatch_training marca o job 'failed'.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

_FEATURE_FLAG_COMPUTE_TARGET = "training_compute_target"


class TrainingCompute(ABC):
    """Interface de despacho de treino — um provedor por `compute_target`."""

    @abstractmethod
    def dispatch(
        self,
        job_id: str,
        dataset_version_id: str,
        model_size: str,
        epochs: int,
        imgsz: int,
        batch: int,
        update_fn: Any,
        tenant_id: str | None = None,
    ) -> dict:
        """Dispara o treino. Ver contrato de retorno no docstring do módulo."""


class VastAiProvider(TrainingCompute):
    """Wrapper fino sobre `tasks/training.py::_dispatch_vast_ai` (WS-A4,
    já validado em produção — nenhuma lógica nova aqui)."""

    def dispatch(
        self, job_id, dataset_version_id, model_size, epochs, imgsz, batch,
        update_fn, tenant_id=None,
    ) -> dict:
        from app.infrastructure.queue.tasks.training import (  # noqa: PLC0415
            _dispatch_vast_ai,
        )
        return _dispatch_vast_ai(
            job_id, model_size, epochs, imgsz, batch, update_fn,
            tenant_id=tenant_id,
        )


class EdgeProvider(TrainingCompute):
    """BLOQUEADO-HARDWARE — desenhado e testado com mock, nunca validado
    contra um Jetson real. Ver docstring do módulo.

    Enfileira `edge_commands` (command_type='start_training') pro site mais
    recente do tenant (MVP: sem UI pra escolher o site — trabalho futuro,
    ver issue de validação de hardware). Fail-loud: se o enqueue falhar,
    propaga a exceção (nunca finge que um treino começou quando não
    começou — diferente do padrão best-effort de `_notify_model_change`,
    que é só invalidação de cache, não a ÚNICA forma de o job progredir).
    """

    def dispatch(
        self, job_id, dataset_version_id, model_size, epochs, imgsz, batch,
        update_fn, tenant_id=None,
    ) -> dict:
        if not tenant_id:
            raise ValueError("EdgeProvider requer tenant_id para resolver o site")

        from app.infrastructure.database.connection import (  # noqa: PLC0415
            DatabasePool,
        )
        from app.infrastructure.database.repositories.edge_command_repository import (  # noqa: PLC0415,E501
            EdgeCommandRepository,
        )
        from app.infrastructure.database.repositories.edge_site_repository import (  # noqa: PLC0415,E501
            EdgeSiteRepository,
        )

        pool = DatabasePool.get_instance()
        sites = EdgeSiteRepository(pool).list_sites(tenant_id)
        if not sites:
            raise RuntimeError(
                f"EdgeProvider: tenant {tenant_id} sem edge_sites cadastrado"
            )
        site_id = str(sites[0]["id"])

        command_id = f"train:{job_id}"
        EdgeCommandRepository(pool).create(
            tenant_id=tenant_id,
            site_id=site_id,
            command_type="start_training",
            payload={
                "job_id": job_id,
                "dataset_version_id": dataset_version_id,
                "model_size": model_size,
                "epochs": epochs,
                "imgsz": imgsz,
                "batch": batch,
            },
            command_id=command_id,
            created_by=None,
        )
        update_fn("running", progress=0)
        logger.info(
            "edge_training_dispatched: job=%s tenant=%s site=%s "
            "(BLOQUEADO-HARDWARE — sem confirmação de execução real)",
            job_id, tenant_id, site_id,
        )
        return {"model_path": "", "metrics": {}, "source": "edge", "status": "running"}


def _tenant_edge_site_available(tenant_id: str) -> bool:
    try:
        from app.infrastructure.database.connection import (  # noqa: PLC0415
            DatabasePool,
        )
        from app.infrastructure.database.repositories.edge_site_repository import (  # noqa: PLC0415,E501
            EdgeSiteRepository,
        )
        pool = DatabasePool.get_instance()
        if pool is None:
            return False
        return bool(EdgeSiteRepository(pool).list_sites(tenant_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("edge_site_check_failed: tenant=%s err=%s", tenant_id, exc)
        return False


def get_training_compute(tenant_id: str | None) -> TrainingCompute:
    """Factory: resolve o provedor pela mesma precedência de sempre (Vast.ai
    real > edge > simulação), com edge E simulação como opt-in explícito.

    Precedência:
      1. Vast.ai — `resolve_vast_api_key(tenant_id)` (integration store do
         tenant > env `VAST_API_KEY`) resolve uma chave. (O dispatch em si
         ainda é gateado por `training_third_party_cloud_enabled` dentro de
         `tasks/training.py::_dispatch_vast_ai` — GPU de terceiro nunca
         dispara sem esse opt-in, mesmo com chave configurada.)
      2. Edge — feature flag `training_compute_target='edge'` no tenant E
         o tenant tem ≥1 edge_site cadastrado.
      3. Nenhum provedor real (inclusive `training_compute_target='local'`
         explícito): erro alto, sempre — não existe mais simulação.

    ADR-0017: sem nenhum provedor real disponível, o job NUNCA cai
    silenciosamente em nada — levanta RuntimeError com mensagem clara, e
    `dispatch_training` marca o job 'failed' (nunca 'completed' com um
    artefato fake). `training_compute_target='local'` tem uma mensagem
    própria e legível ("treino local não suportado") em vez de cair no erro
    genérico — sinaliza claramente pro operador que essa configuração nunca
    teve um provider real por trás.
    """
    from app.infrastructure.gpu.vast_client import resolve_vast_api_key  # noqa: PLC0415

    if resolve_vast_api_key(tenant_id):
        return VastAiProvider()

    compute_target: str | None = None
    if tenant_id:
        try:
            from uuid import UUID  # noqa: PLC0415

            from app.infrastructure.database.connection import (  # noqa: PLC0415
                DatabasePool,
            )
            from app.infrastructure.database.repositories.tenant_settings_repository import (  # noqa: PLC0415,E501
                TenantSettingsRepository,
            )
            pool = DatabasePool.get_instance()
            if pool is not None:
                flags = TenantSettingsRepository(pool).get_feature_flags(UUID(str(tenant_id)))
                compute_target = flags.get(_FEATURE_FLAG_COMPUTE_TARGET)
                if compute_target == "edge":
                    if _tenant_edge_site_available(tenant_id):
                        return EdgeProvider()
                    logger.warning(
                        "training_compute_edge_flag_without_site: tenant=%s — "
                        "sem edge_site cadastrado", tenant_id,
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "training_compute_flag_read_failed: tenant=%s err=%s", tenant_id, exc
            )

    if compute_target == "local":
        raise RuntimeError(
            f"Treino local não suportado (tenant={tenant_id} configurado com "
            "training_compute_target='local') — nenhum provedor de treino "
            "roda localmente; configure Vast.ai (chave no integration store "
            "do tenant) ou edge (training_compute_target='edge' + edge_site "
            "cadastrado)."
        )

    reason = (
        "tenant configurado para edge (training_compute_target='edge') mas "
        "sem edge_site cadastrado" if compute_target == "edge" else
        "nenhuma chave Vast.ai resolvível (integration store do tenant nem "
        "env VAST_API_KEY) e nenhum compute_target alternativo configurado"
    )
    raise RuntimeError(
        f"Nenhum provedor de treino real disponível para tenant={tenant_id} "
        f"({reason})."
    )
