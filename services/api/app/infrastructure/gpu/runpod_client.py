"""
Recognition — RunPod REST/GraphQL client (substitui Vast.ai).

Cliente HTTP puro (`requests`) para a API REST v1 do RunPod
(https://rest.runpod.io/v1) + preço de GPU via GraphQL
(https://api.runpod.io/graphql) — ZERO dependência do SDK `runpod` (pip).

Decisão do dono: `infrastructure/gpu/vast_client.py` foi DELETADO — a API
console.vast.ai deu 404 em produção e nunca entregou um treino real (ver
`docs/decisions/adr/` desta task). RunPod é o substituto; este cliente é
usado pelo runner genérico (`runpod_runner.py`) tanto para carga 'train'
quanto (PR futuro) 'propagate'.

Operações:
  - create_pod: provisiona um pod com imagem + env + dockerStartCmd (o
    dockerStartCmd embute o executor genérico via heredoc — camada 1 de 3
    de garantia de morte, ver `runpod_runner.py::build_onstart`).
  - get_pod / list_pods: status (usado pelo watchdog Celery e pelo
    reconciler celery-beat — camadas 2 e 3).
  - terminate_pod: best-effort (nunca vazar GPU paga) — retorna bool, nunca
    levanta, seguro em blocos finally/reconciler.
  - get_gpu_price: preço on-demand $/h via GraphQL — usado pra estimar
    custo ANTES de criar o pod (teto por tipo de carga).
  - get_billing: histórico de cobrança por pod (custo real pós-término).

Credencial (resolve_runpod_api_key): integration store do tenant
(integration_type='runpod', via IntegrationService.get_integration_secret)
→ fallback env RUNPOD_API_KEY — mesmo padrão de precedência que
`resolve_vast_api_key` (deletado) e `resolve_r2_credentials` já usavam.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

RUNPOD_REST_BASE_URL = "https://rest.runpod.io/v1"
RUNPOD_GRAPHQL_URL = "https://api.runpod.io/graphql"

_DEFAULT_TIMEOUT_SECONDS = 30


class RunPodError(Exception):
    """Erro de comunicação ou de estado com a API RunPod."""


def resolve_runpod_api_key(tenant_id: str | None) -> str:
    """Resolve a API key RunPod: integration store do tenant → env RUNPOD_API_KEY.

    Fail-soft: qualquer erro na consulta do integration store (pool ausente,
    Fernet, tenant inválido) cai no fallback env. Retorna "" se nada existe.
    """
    if tenant_id:
        try:
            from uuid import UUID  # noqa: PLC0415

            from app.domain.services.integration_service import (  # noqa: PLC0415
                IntegrationService,
            )
            from app.infrastructure.database.connection import (  # noqa: PLC0415
                DatabasePool,
            )
            from app.infrastructure.database.repositories.integration_repository import (  # noqa: E501,PLC0415
                IntegrationRepository,
            )

            pool = DatabasePool.get_instance()
            if pool is not None:
                svc = IntegrationService(IntegrationRepository(pool))
                key = svc.get_integration_secret(UUID(str(tenant_id)), "runpod")
                if key:
                    return key
        except Exception as exc:
            logger.warning(
                "runpod_key_tenant_lookup_failed: tenant=%s err=%s", tenant_id, exc
            )
    return os.environ.get("RUNPOD_API_KEY", "")


class RunPodClient:
    """Cliente REST/GraphQL RunPod. Toda chamada tem timeout e chave via header."""

    def __init__(
        self,
        api_key: str,
        base_url: str = RUNPOD_REST_BASE_URL,
        graphql_url: str = RUNPOD_GRAPHQL_URL,
        timeout: int = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not api_key:
            raise RunPodError("API key RunPod ausente")
        self.api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._graphql_url = graphql_url
        self._timeout = timeout

    # ------------------------------------------------------------------ http

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        try:
            resp = requests.request(
                method,
                url,
                headers=self._headers(),
                params=params,
                json=json_body,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise RunPodError(f"RunPod {method} {path} falhou: {exc}") from exc

        if resp.status_code >= 400:
            raise RunPodError(
                f"RunPod {method} {path} → HTTP {resp.status_code}: {resp.text[:300]}"
            )
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError as exc:
            raise RunPodError(f"RunPod {method} {path} → resposta não-JSON") from exc

    def _graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            resp = requests.post(
                self._graphql_url,
                headers=self._headers(),
                json={"query": query, "variables": variables or {}},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise RunPodError(f"RunPod GraphQL falhou: {exc}") from exc

        if resp.status_code >= 400:
            raise RunPodError(
                f"RunPod GraphQL → HTTP {resp.status_code}: {resp.text[:300]}"
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise RunPodError("RunPod GraphQL → resposta não-JSON") from exc
        if data.get("errors"):
            raise RunPodError(f"RunPod GraphQL → erros: {data['errors']}")
        return data.get("data") or {}

    # ------------------------------------------------------------------ pods

    def create_pod(
        self,
        *,
        name: str,
        image: str,
        gpu_type_id: str,
        env: dict[str, str],
        docker_start_cmd: list[str],
        gpu_count: int = 1,
        container_disk_gb: int = 40,
        cloud_type: str = "COMMUNITY",
    ) -> dict[str, Any]:
        """Provisiona um pod. Levanta RunPodError sem `id` na resposta —
        nunca retorna um pod "fantasma" que o caller acharia criado."""
        body: dict[str, Any] = {
            "name": name,
            "imageName": image,
            "gpuTypeIds": [gpu_type_id],
            "gpuCount": gpu_count,
            "containerDiskInGb": container_disk_gb,
            "cloudType": cloud_type,
            "computeType": "GPU",
            "env": env,
            "dockerStartCmd": docker_start_cmd,
        }
        data = self._request("POST", "/pods", json_body=body)
        if not isinstance(data, dict) or not data.get("id"):
            raise RunPodError(f"create_pod sem id: name={name} resp={data}")
        logger.info(
            "runpod_pod_created: id=%s name=%s gpu=%s", data["id"], name, gpu_type_id
        )
        return data

    def get_pod(self, pod_id: str) -> dict[str, Any]:
        data = self._request("GET", f"/pods/{pod_id}")
        return data if isinstance(data, dict) else {}

    def list_pods(self) -> list[dict[str, Any]]:
        """Lista pods da conta (usado pelo reconciler celery-beat, camada 3)."""
        data = self._request("GET", "/pods")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("pods") or data.get("data") or []
        return []

    def terminate_pod(self, pod_id: str) -> bool:
        """Termina o pod. Best-effort: loga e retorna False em erro — NUNCA
        levanta (chamado em blocos finally/watchdog/reconciler — camadas
        1 [trap local]/2 [watchdog]/3 [reconciler] de garantia de morte
        dependem de nunca deixar uma exceção aqui vazar o pod)."""
        try:
            self._request("DELETE", f"/pods/{pod_id}")
            logger.info("runpod_pod_terminated: pod=%s", pod_id)
            return True
        except RunPodError as exc:
            logger.error(
                "runpod_terminate_failed: pod=%s err=%s — termine manualmente "
                "no console RunPod", pod_id, exc,
            )
            return False

    # --------------------------------------------------------------- pricing

    def get_gpu_price(self, gpu_type: str) -> float:
        """Preço on-demand $/h via GraphQL (gpuTypes.lowestPrice.uninterruptablePrice).

        Levanta RunPodError se o gpu_type for desconhecido ou sem preço —
        nunca retorna 0.0/None silenciosamente (isso zeraria o teto de custo).
        """
        query = """
        query GpuTypes($id: String) {
          gpuTypes(input: {id: $id}) {
            id
            lowestPrice(input: {gpuCount: 1}) {
              uninterruptablePrice
            }
          }
        }
        """
        data = self._graphql(query, {"id": gpu_type})
        types = data.get("gpuTypes") or []
        if not types:
            raise RunPodError(f"gpu_type desconhecido na RunPod: {gpu_type!r}")
        price = (types[0].get("lowestPrice") or {}).get("uninterruptablePrice")
        if price is None:
            raise RunPodError(f"RunPod não retornou preço para gpu_type={gpu_type!r}")
        return float(price)

    # --------------------------------------------------------------- billing

    def get_billing(
        self, pod_id: str | None = None, bucket_size: str = "day"
    ) -> list[dict[str, Any]]:
        """Histórico de cobrança de pods (GET /billing/pods). Filtra por
        `pod_id` client-side — a API não documenta um filtro server-side
        por pod individual."""
        data = self._request("GET", "/billing/pods", params={"bucketSize": bucket_size})
        records = data if isinstance(data, list) else (data.get("data") or [])
        if pod_id is None:
            return records
        return [r for r in records if r.get("podId") == pod_id]
