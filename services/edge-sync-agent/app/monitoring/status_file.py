"""Artefatos de estado entre processos — escrita atômica, best-effort.

O coletor de monitoramento (`python -m app.monitoring`) roda em processo
próprio; live_view e heartbeat rodam nos deles. A ponte é a mesma disciplina
do edge_config_cache/collector_state (vizinhos de diretório): JSON pequeno,
`tempfile + os.replace` atômico, falha de IO degrada sem NUNCA derrubar o
processo que produz o dado. Cada artefato carrega `ts` — a página trata dado
velho como velho (timestamp sempre visível, nunca cara de dado novo).

⚠️ Nenhum artefato aqui pode carregar segredo: URLs RTSP com credencial ficam
fora por construção (só IDs de câmera, contadores e durações).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_STATE_DIR = str(Path.home() / ".local" / "state" / "recognition" / "monitoring")
LIVE_VIEW_STATUS_FILENAME = "live_view.json"
NET_STATUS_FILENAME = "net.json"
INFERENCE_STATUS_FILENAME = "inference.json"


def write_json_atomic(path: str | Path, data: dict[str, Any]) -> bool:
    """Escrita atômica best-effort. False em falha de IO (logada, nunca levanta)."""
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=f".{p.name}.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, p)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        return True
    except OSError as exc:
        logger.warning("status_file_escrita_falhou path=%s err=%s", p, exc)
        return False


def write_net_status(path: str | Path, *, rtt_ms: float | None, ok: bool) -> None:
    """RTT até a API de CARONA no heartbeat que já ia subir — medir com probe
    próprio seria egress novo, e o requisito é zero egress sem acesso."""
    write_json_atomic(
        path,
        {"ts": round(time.time(), 1), "api_rtt_ms": rtt_ms, "ok": ok},
    )


class LiveViewStatus:
    """Métricas por câmera do pipeline de vídeo, alimentadas pelo LiveViewLoop.

    Thread-safe (os hooks de push rodam nos worker threads do executor). O
    LiveViewLoop chama `maybe_write()` a cada tick; a escrita real acontece no
    máximo a cada `write_interval_s`.

    Métricas por câmera:
      - ffmpeg vivo/morto (e "idle" quando sem espectador — estado legítimo,
        não falha: o live view é sob demanda por design, LV-3);
      - segmentos/min (janela deslizante de timestamps de push);
      - latência de push p50/p95 (janela das últimas `_MAX_LAT` durações);
      - falhas de POST (contador acumulado);
      - última imagem empurrada há X s;
      - reinícios do ffmpeg (contador acumulado — reconexão RTSP em loop).
    """

    _MAX_LAT = 200
    _RATE_WINDOW_S = 60.0

    def __init__(self, path: str | Path, *, write_interval_s: float = 10.0) -> None:
        self._path = Path(path)
        self._write_interval_s = write_interval_s
        self._lock = threading.Lock()
        self._last_write = 0.0
        self._cameras: dict[str, dict[str, Any]] = {}
        self._latencies: dict[str, deque[float]] = {}
        self._push_times: dict[str, deque[float]] = {}

    def _cam(self, camera_id: str) -> dict[str, Any]:
        return self._cameras.setdefault(
            camera_id,
            {"push_fail_total": 0, "restarts_total": 0, "state": "idle"},
        )

    def record_push_ok(self, camera_id: str, duration_ms: float) -> None:
        now = time.time()
        with self._lock:
            cam = self._cam(camera_id)
            cam["last_push_ts"] = round(now, 1)
            lat = self._latencies.setdefault(camera_id, deque(maxlen=self._MAX_LAT))
            lat.append(duration_ms)
            times = self._push_times.setdefault(camera_id, deque(maxlen=600))
            times.append(now)

    def record_push_fail(self, camera_id: str) -> None:
        with self._lock:
            self._cam(camera_id)["push_fail_total"] += 1

    def record_ffmpeg_state(self, camera_id: str, *, running: bool, wanted: bool) -> None:
        with self._lock:
            cam = self._cam(camera_id)
            cam["ffmpeg_alive"] = running
            cam["state"] = "streaming" if running else ("starting" if wanted else "idle")

    def record_restart(self, camera_id: str) -> None:
        """FFmpeg morreu com espectador ativo e vai ser religado — cada
        incremento aqui é uma reconexão RTSP; em loop = câmera/rede doente."""
        with self._lock:
            self._cam(camera_id)["restarts_total"] += 1

    def maybe_write(self) -> None:
        now = time.time()
        with self._lock:
            if now - self._last_write < self._write_interval_s:
                return
            self._last_write = now
            snapshot = self._snapshot_locked(now)
        write_json_atomic(self._path, snapshot)

    def _snapshot_locked(self, now: float) -> dict[str, Any]:
        cameras: dict[str, Any] = {}
        for camera_id, cam in self._cameras.items():
            entry = dict(cam)
            lat = sorted(self._latencies.get(camera_id, ()))
            if lat:
                entry["push_p50_ms"] = round(lat[len(lat) // 2], 1)
                entry["push_p95_ms"] = round(lat[min(len(lat) - 1, int(len(lat) * 0.95))], 1)
            times = self._push_times.get(camera_id, ())
            recent = [t for t in times if now - t <= self._RATE_WINDOW_S]
            entry["segments_per_min"] = round(len(recent) * 60.0 / self._RATE_WINDOW_S, 1)
            if "last_push_ts" in entry:
                entry["last_push_age_s"] = max(0, round(now - entry["last_push_ts"]))
            cameras[camera_id] = entry
        return {"ts": round(now, 1), "cameras": cameras}


def build_live_view_status_from_env(env: dict[str, str] | None = None) -> LiveViewStatus:
    source = env if env is not None else os.environ
    state_dir = source.get("EDGE_MONITORING_STATE_DIR") or DEFAULT_STATE_DIR
    return LiveViewStatus(Path(state_dir) / LIVE_VIEW_STATUS_FILENAME)
