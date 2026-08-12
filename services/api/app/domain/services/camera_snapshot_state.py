"""camera_snapshot_state — Redis cache do último snapshot de cada câmera
(Bloco A: miniatura de triagem, CameraTriagePage).

Só metadados vivem aqui — os bytes do JPEG vivem no R2 (constants.R2Prefix.
SNAPSHOTS). Chave: epi:camera_snapshot:{tenant_id}:{camera_id}.

Sem migration nova (decisão da task): o estado "qual foi o último resultado
de captura desta câmera" é efêmero por natureza (uma nova captura sempre
pode substituir a anterior) — Redis com TTL longo é suficiente, e evita
crescer uma tabela para algo que não precisa de histórico nem de query
relacional.

Escritores:
  - `write_pending` — chamado por
    app.api.v1.cameras.snapshot_handlers.refresh_camera_snapshot logo após
    enfileirar um `capture_snapshot` de verdade (nunca no caminho "cache
    fresco" ou "já pendente") — sem isto, GET nunca reportava "pending": o
    Redis só tinha o resultado da captura ANTERIOR (ready/failed/ausente),
    então um refresh disparado sobre um cache velho fazia o polling do
    frontend ler esse resultado velho e parar na hora, achando que já
    tinha terminado.
  - `write_ready` — chamado por app.api.v1.edge.routes.upload_camera_snapshot
    (device auth) após o upload do JPEG pro R2 ter sucesso.
  - `write_failed` — chamado por app.api.v1.edge_commands.routes ao receber
    o ack de um comando `capture_snapshot` com status=failed (bridge
    best-effort, mesmo padrão de `_bridge_heartbeat_to_telemetry` em
    app.api.v1.edge.routes).

Leitor: app.api.v1.cameras.snapshot_handlers (GET/POST /snapshot, JWT do
tenant).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

_KEY_PREFIX = "epi:camera_snapshot"
# Entrada sem refresh cai sozinha depois de um tempo generoso — nunca cresce
# sem limite, e uma câmera arquivada/removida não deixa lixo permanente.
_DEFAULT_TTL_S = 7 * 24 * 3600  # 7 dias


def _key(tenant_id: str, camera_id: str) -> str:
    return f"{_KEY_PREFIX}:{tenant_id}:{camera_id}"


def read_state(redis_client: Any, tenant_id: str, camera_id: str) -> Optional[dict]:
    """Lê o último estado conhecido. `None` = nunca capturado (status "none"
    do lado do handler) ou erro de leitura do Redis (fail-open — nunca
    derruba o GET por causa do cache)."""
    try:
        raw = redis_client.get(_key(tenant_id, camera_id))
    except Exception:
        logger.warning(
            "camera_snapshot_state_read_error tenant=%s camera=%s",
            tenant_id, camera_id, exc_info=True,
        )
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        logger.warning(
            "camera_snapshot_state_corrupt tenant=%s camera=%s", tenant_id, camera_id
        )
        return None


def write_pending(
    redis_client: Any,
    tenant_id: str,
    camera_id: str,
    ttl: int = _DEFAULT_TTL_S,
) -> None:
    """Marca uma captura como em andamento — chamado logo após enfileirar o
    edge_command capture_snapshot de verdade (POST /refresh, caminho
    "despachou"). Preserva o último r2_key/captured_at "bons" conhecidos
    (se houver) para a UI poder continuar mostrando a miniatura antiga
    enquanto espera a nova."""
    previous = read_state(redis_client, tenant_id, camera_id) or {}
    state = {
        "status": "pending",
        "r2_key": previous.get("r2_key"),
        "captured_at": previous.get("captured_at"),
        "error_reason": None,
    }
    redis_client.setex(_key(tenant_id, camera_id), ttl, json.dumps(state))


def write_ready(
    redis_client: Any,
    tenant_id: str,
    camera_id: str,
    r2_key: str,
    ttl: int = _DEFAULT_TTL_S,
) -> None:
    """Registra uma captura bem-sucedida (chamado pelo endpoint de upload do
    device, DEPOIS do R2 já ter aceito os bytes)."""
    state = {
        "status": "ready",
        "r2_key": r2_key,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "error_reason": None,
    }
    redis_client.setex(_key(tenant_id, camera_id), ttl, json.dumps(state))


def write_failed(
    redis_client: Any,
    tenant_id: str,
    camera_id: str,
    reason: str,
    ttl: int = _DEFAULT_TTL_S,
) -> None:
    """Registra uma falha de captura — preserva o último r2_key/captured_at
    "bons" conhecidos (se houver) para a UI poder mostrar "última imagem boa
    há X min" junto com o motivo da falha mais recente, em vez de perder a
    miniatura anterior por causa de uma falha nova."""
    previous = read_state(redis_client, tenant_id, camera_id) or {}
    state = {
        "status": "failed",
        "r2_key": previous.get("r2_key"),
        "captured_at": previous.get("captured_at"),
        "error_reason": reason,
    }
    redis_client.setex(_key(tenant_id, camera_id), ttl, json.dumps(state))


def is_fresh(state: Optional[dict], fresh_minutes: int) -> bool:
    """True quando `state` é um snapshot "ready" capturado há menos de
    `fresh_minutes`. Usado pelo POST /refresh para decidir se despachar uma
    nova captura é necessário — nunca bate no gravador com um cache fresco."""
    if not state or state.get("status") != "ready" or not state.get("captured_at"):
        return False
    try:
        captured_at = datetime.fromisoformat(state["captured_at"])
    except ValueError:
        return False
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    age_s = (datetime.now(timezone.utc) - captured_at).total_seconds()
    return age_s < fresh_minutes * 60
