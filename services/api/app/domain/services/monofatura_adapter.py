"""
Adaptador outbound da integração monofatura (task-108, ADR-0053).

O contrato REAL do cliente (formato/endpoint do ERP que recebe o resultado
da etapa) ainda é um INPUT PENDENTE. Por isso o outbound é PLUGÁVEL:
uma interface estável + implementação simulada. Quando o contrato chegar,
cria-se um novo adapter (ex.: HttpMonofaturaAdapter) sem tocar no service.

Payload por etapa (o que a plataforma devolve associado ao ID da peça):
  {
    "piece_id":        ID bipado da peça,
    "stage":           etapa da inspeção,
    "result":          {"ok": bool, "attributes": [{"name", "ok", "confidence"?}, ...]},
    "evidence_r2_key": chave R2 da imagem de evidência (pode ser None),
    "elapsed_s":       tempo da etapa em segundos (cronômetro NvDCF — task-109),
    "finished_at":     ISO-8601,
  }

Seleção por env: MONOFATURA_ADAPTER=simulated (default).
"""
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class MonofaturaAdapter(ABC):
    """Interface do outbound monofatura — um send por etapa concluída."""

    @abstractmethod
    def send_stage_result(self, payload: dict[str, Any]) -> bool:
        """Entrega o resultado da etapa ao sistema do cliente.

        Returns:
            True se aceito pelo destino; False em falha (o service registra,
            não relança — a conclusão da etapa não pode ser perdida por
            indisponibilidade do ERP).
        """


class SimulatedMonofaturaAdapter(MonofaturaAdapter):
    """Simulação do destino (stress task-111 / contrato real pendente).

    Só loga o payload de forma estruturada; o registro persistente fica no
    result JSONB da própria inspection_session.
    """

    def send_stage_result(self, payload: dict[str, Any]) -> bool:
        logger.info(
            "monofatura_outbound_simulated: piece=%s stage=%s ok=%s "
            "attrs=%d evidence=%s elapsed_s=%s",
            payload.get("piece_id"),
            payload.get("stage"),
            (payload.get("result") or {}).get("ok"),
            len((payload.get("result") or {}).get("attributes", [])),
            payload.get("evidence_r2_key"),
            payload.get("elapsed_s"),
        )
        return True


def get_monofatura_adapter() -> MonofaturaAdapter:
    """Factory por env MONOFATURA_ADAPTER (default: simulated)."""
    kind = os.environ.get("MONOFATURA_ADAPTER", "simulated").lower()
    if kind == "simulated":
        return SimulatedMonofaturaAdapter()
    raise ValueError(
        f"MONOFATURA_ADAPTER desconhecido: {kind!r} — contrato real do cliente "
        "ainda pendente; implementar novo adapter quando definido."
    )
