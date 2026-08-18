"""Estado persistido do coletor — contadores de frames por câmera (D-86).

Fecha o buraco documentado no docstring do collector_loop: o contador
`frames_uploaded` vivia só em memória e re-armava a cota a cada restart do
processo — um restart no meio de uma campanha dobra a coleta sem ninguém
perceber. Com 2 câmeras era simplificação aceitável; com a campanha das
câmeras novas (29 canais) vira multiplicador de custo.

Mesmo padrão do edge_config_cache.py (vizinho de diretório e de disciplina):
JSON pequeno, escrita atômica (tempfile + os.replace), best-effort — falha de
IO degrada para o comportamento antigo (contador só em memória), NUNCA derruba
o loop de coleta.

Formato do arquivo:
    {"frames_uploaded": {"<camera_id>": <int>, ...}}

O arquivo NUNCA carrega segredo (só UUID de câmera e contagem).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Irmão de config_cache.json e buffer.db — mesma convenção de diretório para
# estado runtime edge-local (ver edge_config_cache.DEFAULT_CACHE_PATH).
# XDG, não /var: o agente roda como systemd --user SEM sudo (Jetson,
# REGRAS_PLATAFORMA_JETSON.md §3.4) e não pode criar /var/edge-sync. Medido em
# 2026-08-18: `collector_state_write_failed ... [Errno 13] Permission denied` a
# cada ciclo — os contadores de campanha e o ponto de retomada eram perdidos
# TODA vez, e a única pista era um WARNING no meio de milhares de linhas.
DEFAULT_STATE_PATH = os.path.join(
    os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"),
    "recognition", "collector_state.json",
)


def load_counts(path: str) -> dict[str, int]:
    """Lê os contadores persistidos. Arquivo ausente/corrompido -> {} com
    warning (primeiro boot legítimo não tem arquivo; corrupção não pode
    impedir a coleta — o custo de recontar do zero é coletar DEMAIS, que é
    recuperável, enquanto travar o boot custa a janela de coleta inteira)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        logger.info("collector_state_ausente path=%s — contadores começam em 0", path)
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "collector_state_ilegivel path=%s err=%s — contadores começam em 0",
            path, exc,
        )
        return {}

    raw = data.get("frames_uploaded")
    if not isinstance(raw, dict):
        logger.warning(
            "collector_state_corrompido path=%s (frames_uploaded não é dict) — "
            "contadores começam em 0", path,
        )
        return {}
    counts: dict[str, int] = {}
    for camera_id, value in raw.items():
        try:
            counts[str(camera_id)] = max(0, int(value))
        except (TypeError, ValueError):
            logger.warning(
                "collector_state_valor_invalido camera=%s valor=%r — ignorado",
                camera_id, value,
            )
    return counts


def save_counts(path: str, counts: dict[str, int]) -> None:
    """Persiste os contadores atomicamente (best-effort — NUNCA levanta).

    Falha de escrita (disco cheio, permissão) não pode derrubar o loop de
    coleta — só significa que um restart futuro volta pro último snapshot
    bom, coletando um pouco a mais (recuperável, ver load_counts).
    """
    try:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"frames_uploaded": counts})
        fd, tmp_path = tempfile.mkstemp(dir=str(target.parent), prefix=".collector_state-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            os.replace(tmp_path, target)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    except OSError as exc:
        logger.warning("collector_state_write_failed path=%s err=%s", path, exc)


def collection_enabled(env: dict[str, str] | None = None) -> bool:
    """Interruptor-mestre persistido da coleta (COLLECTOR_ENABLED no .env).

    "Desligado" precisa sobreviver a restart (D-86): depois da campanha, TODAS
    as capturas param para o treino começar — e se o desligado fosse só "a
    cota bateu" (memória) ou "systemctl stop" (não sobrevive a reboot da
    unit habilitada), um restart às três da manhã religaria 29 câmeras.
    O .env é arquivo: editar + reiniciar a unit é o desligamento durável.
    """
    source = env if env is not None else os.environ
    return source.get("COLLECTOR_ENABLED", "1").strip().lower() not in ("0", "false", "no")
