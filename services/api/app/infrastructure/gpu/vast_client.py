"""
Recognition — Vast.ai REST client (WS-A4).

Cliente fino sobre a API REST https://console.vast.ai/api/v0 usado pelo
dispatch real de treinamento (tasks/training.py::_dispatch_vast_ai).

Operações:
  - search_offers: busca ofertas GPU (RTX 4090/3090) com price-cap $/h
    (env VAST_PRICE_CAP, default 0.60), ordenadas por dph_total asc.
  - create_instance: aluga a oferta com imagem pytorch + onstart script
    (o onstart embute o runner remote_train.py via heredoc — a instância
    não tem acesso ao repositório).
  - get_instance_status: usado como watchdog pelo poll do worker.
  - destroy_instance: best-effort (nunca vazar GPU paga) — retorna bool,
    não levanta, para ser seguro em blocos finally.

Credencial (resolve_vast_api_key): integration store do tenant
(integration_type='vast_ai', via IntegrationService.get_integration_secret)
→ fallback env VAST_API_KEY.

Endpoints (mesmos usados pelo vastai CLI):
  GET    /bundles/            q=<json>   → {"offers": [...]}
  PUT    /asks/<offer_id>/               → {"success": true, "new_contract": <id>}
  GET    /instances/<id>/                → {"instances": {...}}
  DELETE /instances/<id>/                → {"success": true}
"""
import json
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

VAST_API_BASE_URL = "https://console.vast.ai/api/v0"

_DEFAULT_TIMEOUT_SECONDS = 30
_DEFAULT_PRICE_CAP_USD_H = 0.60
_DEFAULT_GPU_NAMES: tuple[str, ...] = ("RTX 4090", "RTX 3090")
_DEFAULT_IMAGE = "pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime"
_DEFAULT_DISK_GB = 60


class VastAIError(Exception):
    """Erro de comunicação ou de estado com a API Vast.ai."""


def get_price_cap() -> float:
    """Price-cap em USD/h (env VAST_PRICE_CAP, default 0.60)."""
    raw = os.environ.get("VAST_PRICE_CAP", "")
    try:
        return float(raw) if raw else _DEFAULT_PRICE_CAP_USD_H
    except ValueError:
        logger.warning("vast_price_cap_invalido: %r — usando default %.2f",
                       raw, _DEFAULT_PRICE_CAP_USD_H)
        return _DEFAULT_PRICE_CAP_USD_H


def resolve_vast_api_key(tenant_id: str | None) -> str:
    """Resolve a API key Vast.ai: integration store do tenant → env VAST_API_KEY.

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
                key = svc.get_integration_secret(UUID(str(tenant_id)), "vast_ai")
                if key:
                    return key
        except Exception as exc:
            logger.warning(
                "vast_key_tenant_lookup_failed: tenant=%s err=%s", tenant_id, exc
            )
    return os.environ.get("VAST_API_KEY", "")


class VastAIClient:
    """Cliente REST Vast.ai. Todas as chamadas têm timeout e chave via header."""

    def __init__(
        self,
        api_key: str,
        base_url: str = VAST_API_BASE_URL,
        timeout: int = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if not api_key:
            raise VastAIError("API key Vast.ai ausente")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    # ------------------------------------------------------------------ http

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
            raise VastAIError(f"Vast.ai {method} {path} falhou: {exc}") from exc

        if resp.status_code >= 400:
            raise VastAIError(
                f"Vast.ai {method} {path} → HTTP {resp.status_code}: "
                f"{resp.text[:300]}"
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise VastAIError(
                f"Vast.ai {method} {path} → resposta não-JSON"
            ) from exc
        if not isinstance(data, dict):
            return {"data": data}
        return data

    # ---------------------------------------------------------------- offers

    def search_offers(
        self,
        gpu_names: tuple[str, ...] = _DEFAULT_GPU_NAMES,
        max_price: float | None = None,
        num_gpus: int = 1,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Busca ofertas on-demand alugáveis, filtradas pelo price-cap.

        Retorna ordenado por dph_total asc (mais barata primeiro). O filtro
        de preço é re-aplicado client-side — nunca confiar só na query.
        """
        cap = max_price if max_price is not None else get_price_cap()
        query = {
            "gpu_name": {"in": list(gpu_names)},
            "num_gpus": {"eq": num_gpus},
            "rentable": {"eq": True},
            "dph_total": {"lte": cap},
            "type": "on-demand",
            "order": [["dph_total", "asc"]],
        }
        data = self._request("GET", "/bundles/", params={"q": json.dumps(query)})
        offers = data.get("offers") or []
        priced = [
            o for o in offers
            if isinstance(o, dict)
            and float(o.get("dph_total", float("inf"))) <= cap
        ]
        priced.sort(key=lambda o: float(o.get("dph_total", float("inf"))))
        logger.info(
            "vast_search_offers: gpus=%s cap=%.2f encontradas=%d",
            ",".join(gpu_names), cap, len(priced),
        )
        return priced[:limit]

    # -------------------------------------------------------------- instance

    def create_instance(
        self,
        offer_id: int | str,
        onstart: str,
        image: str = _DEFAULT_IMAGE,
        disk_gb: int = _DEFAULT_DISK_GB,
        label: str | None = None,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Aluga a oferta e retorna a resposta com 'new_contract' (instance id)."""
        body: dict[str, Any] = {
            "client_id": "me",
            "image": image,
            "onstart": onstart,
            "disk": disk_gb,
            "runtype": "ssh",
        }
        if label:
            body["label"] = label
        if env:
            body["env"] = env

        data = self._request("PUT", f"/asks/{offer_id}/", json_body=body)
        if not data.get("new_contract"):
            raise VastAIError(
                f"create_instance sem new_contract: offer={offer_id} resp={data}"
            )
        logger.info(
            "vast_instance_created: offer=%s instance=%s",
            offer_id, data["new_contract"],
        )
        return data

    def get_instance_status(self, instance_id: int | str) -> dict[str, Any]:
        """Status da instância (watchdog). Retorna o dict da instância.

        Campos relevantes: actual_status ('running'|'exited'|...), ssh_host.
        """
        data = self._request("GET", f"/instances/{instance_id}/")
        instance = data.get("instances")
        if isinstance(instance, dict):
            return instance
        if isinstance(instance, list):
            return instance[0] if instance else {}
        return data

    def destroy_instance(self, instance_id: int | str) -> bool:
        """Destrói a instância. Best-effort: loga e retorna False em erro.

        Nunca levanta — é chamado em blocos finally para não vazar GPU paga.
        """
        try:
            self._request("DELETE", f"/instances/{instance_id}/")
            logger.info("vast_instance_destroyed: instance=%s", instance_id)
            return True
        except VastAIError as exc:
            logger.error(
                "vast_destroy_failed: instance=%s err=%s — destrua manualmente "
                "no console Vast.ai", instance_id, exc,
            )
            return False
