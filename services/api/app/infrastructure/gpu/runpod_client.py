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
#: Ver _headers: sem User-Agent o Cloudflare da RunPod devolve 403/1010.
_USER_AGENT = "recognition-api/1.0"

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
            # User-Agent EXPLÍCITO porque o GraphQL da RunPod fica atrás de
            # Cloudflare, que responde 403 "error code: 1010" a requisição sem
            # UA — inclusive SEM autenticação nenhuma, então o erro não tem
            # nada a ver com a chave e manda quem depura na direção errada
            # (medido em 2026-08-25: mesma chave, mesmo endpoint, 403 sem UA e
            # 200 com qualquer UA). Hoje `requests` manda o dele por padrão e
            # isso não morde; mordeu na primeira ferramenta que usou urllib.
            "User-Agent": _USER_AGENT,
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

    def get_pod_logs(self, pod_id: str, *, tail: int = 400) -> str:
        """Log do pod. Best-effort: devolve "" em erro, NUNCA levanta.

        Existe porque `terminate_pod` roda em `finally` e destruía a evidência
        de toda falha — o log morria junto com o pod e o diagnóstico virava
        adivinhação. Chamar ANTES de terminar é o que torna a falha legível.
        """
        for rota in (f"/pods/{pod_id}/logs", f"/pods/{pod_id}/logs?tail={tail}"):
            try:
                data = self._request("GET", rota)
            except Exception as exc:  # noqa: BLE001 — nunca bloquear a morte
                logger.warning("runpod_logs_falhou: pod=%s rota=%s err=%s",
                               pod_id, rota, exc)
                continue
            if isinstance(data, str) and data.strip():
                return data
            if isinstance(data, dict):
                for chave in ("logs", "log", "data", "output"):
                    v = data.get(chave)
                    if isinstance(v, str) and v.strip():
                        return v
                    if isinstance(v, list) and v:
                        return "\n".join(str(x) for x in v)
            if isinstance(data, list) and data:
                return "\n".join(str(x) for x in data)
        return ""

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

    def get_gpu_price(self, gpu_type: str, secure_cloud: bool = False) -> float:
        """Preço on-demand $/h via GraphQL (gpuTypes.lowestPrice.uninterruptablePrice).

        `secure_cloud` NÃO é detalhe. Sem ele a API devolve o menor preço do
        catálogo, que é sempre o da COMMUNITY. Medido na RTX 4090 em 02/09:
        secureCloud=false → $0,34/h · true → $0,74/h, 2,2× de diferença.
        Rodando em SECURE com o preço da COMMUNITY, `check_cost_cap` validava
        contra menos da metade da conta real e deixava passar mais que o dobro
        do orçamento autorizado. Quem chama passa o MESMO tier do create_pod.

        Levanta RunPodError se o gpu_type for desconhecido ou sem preço —
        nunca retorna 0.0/None silenciosamente (isso zeraria o teto de custo).
        """
        query = """
        query GpuTypes($id: String, $secure: Boolean) {
          gpuTypes(input: {id: $id}) {
            id
            lowestPrice(input: {gpuCount: 1, secureCloud: $secure}) {
              uninterruptablePrice
            }
          }
        }
        """
        data = self._graphql(query, {"id": gpu_type, "secure": bool(secure_cloud)})
        types = data.get("gpuTypes") or []
        if not types:
            raise RunPodError(f"gpu_type desconhecido na RunPod: {gpu_type!r}")
        price = (types[0].get("lowestPrice") or {}).get("uninterruptablePrice")
        if price is None:
            raise RunPodError(f"RunPod não retornou preço para gpu_type={gpu_type!r}")
        return float(price)

    def get_saldo(self) -> float:
        """Saldo em dólares da conta que esta chave abre (`myself.clientBalance`).

        Existe porque teto de custo e saldo respondem perguntas diferentes:
        `check_cost_cap` pergunta "este job cabe no orçamento autorizado?" e o
        saldo pergunta "a conta tem dinheiro para terminar o que vai começar?".
        Um job dentro do teto que esgota o saldo na metade morre com tudo que
        já foi pago — e com N pods concorrentes o saldo acaba N vezes mais
        rápido, matando todos de uma vez.

        Levanta RunPodError em vez de devolver 0.0: saldo desconhecido tratado
        como zero bloquearia todo disparo, e tratado como infinito não guardaria
        nada. Quem chama decide o que fazer com a incerteza.
        """
        data = self._graphql("query { myself { clientBalance } }", {})
        saldo = (data.get("myself") or {}).get("clientBalance")
        if saldo is None:
            raise RunPodError("RunPod não retornou clientBalance para esta chave")
        return float(saldo)

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
