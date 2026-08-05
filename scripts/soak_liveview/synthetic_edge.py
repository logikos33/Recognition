#!/usr/bin/env python3
"""Câmera edge SINTÉTICA para o soak do live view (caça ao congelamento 04/08).

Reproduz o contrato do edge-sync-agent sem NVR, sem enrollment e sem device
JWT: `serve_hls` lê `epi:edge_hls:{camera_id}:{filename}` direto do Redis
binário (caminho LV-1, stream_handlers.py) e não consulta o banco — basta:

  1. UM FFmpeg local gerando HLS ao vivo de um testsrc (lavfi), janela
     deslizante igual à do edge (hls_time 1s, list_size 3, delete_segments);
  2. este loop espelhando o diretório para o Redis com a MESMA disciplina do
     edge corrigido (PR do gate da playlist): segmentos primeiro, playlist por
     último, e playlist só sobe quando todos os .ts que ela anuncia já subiram.

O mesmo vídeo alimenta N câmeras (mesmos bytes sob N camera_ids) — o que
importa pro soak é o ciclo token/renovação/consumo, não o conteúdo.

Uso:
  python3 synthetic_edge.py \
      --redis redis://localhost:6379/0 \
      --camera-ids "uuid1,uuid2,..." \
      [--work-dir /tmp/soak-edge] [--ttl 20]

Encerra com Ctrl+C (mata o FFmpeg junto).
"""
from __future__ import annotations

import argparse
import logging
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import redis  # type: ignore[import-untyped]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("synthetic_edge")

SETTLE_SECONDS = 0.5  # espelho do edge: .ts "quente" não sobe


def start_ffmpeg(work_dir: Path) -> subprocess.Popen:  # type: ignore[type-arg]
    work_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "warning",
        "-re", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=15",
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
        "-g", "15", "-keyint_min", "15", "-sc_threshold", "0",
        "-f", "hls", "-hls_time", "1", "-hls_list_size", "3",
        "-hls_flags", "delete_segments+independent_segments",
        str(work_dir / "stream.m3u8"),
    ]
    log.info("ffmpeg: %s", " ".join(cmd))
    return subprocess.Popen(cmd)


def listed_segments(playlist: Path) -> list[str]:
    try:
        return [
            line.strip()
            for line in playlist.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip() and not line.startswith("#")
        ]
    except OSError:
        return []


def mirror_tick(
    r: "redis.Redis", work_dir: Path, camera_ids: list[str], ttl: int,
    pushed: dict[str, tuple[float, int]],
) -> None:
    playlist = work_dir / "stream.m3u8"
    if not playlist.is_file():
        return
    names = listed_segments(playlist)

    # Segmentos primeiro; qualquer pendência segura a playlist (contrato do
    # edge corrigido — a nuvem nunca anuncia .ts que não está no Redis).
    hold_playlist = False
    now = time.time()
    for name in names:
        seg = work_dir / name
        try:
            stat = seg.stat()
        except OSError:
            hold_playlist = True
            continue
        if now - stat.st_mtime < SETTLE_SECONDS:
            hold_playlist = True
            continue
        signature = (stat.st_mtime, stat.st_size)
        if pushed.get(name) == signature:
            continue
        try:
            data = seg.read_bytes()
        except OSError:
            hold_playlist = True
            continue
        if not data:
            hold_playlist = True
            continue
        for camera_id in camera_ids:
            r.setex(f"epi:edge_hls:{camera_id}:{name}", ttl, data)
        pushed[name] = signature

    if hold_playlist:
        return
    try:
        pstat = playlist.stat()
    except OSError:
        return
    psig = (pstat.st_mtime, pstat.st_size)
    if pushed.get("stream.m3u8") == psig:
        return
    pdata = playlist.read_bytes()
    if not pdata:
        return
    for camera_id in camera_ids:
        r.setex(f"epi:edge_hls:{camera_id}:stream.m3u8", ttl, pdata)
    pushed["stream.m3u8"] = psig


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--redis", default="redis://localhost:6379/0")
    ap.add_argument("--camera-ids", required=True, help="UUIDs separados por vírgula")
    ap.add_argument("--work-dir", default="/tmp/soak-edge")
    ap.add_argument("--ttl", type=int, default=20)
    args = ap.parse_args()

    camera_ids = [c.strip() for c in args.camera_ids.split(",") if c.strip()]
    work_dir = Path(args.work_dir)
    if work_dir.exists():
        shutil.rmtree(work_dir)

    r = redis.Redis.from_url(args.redis, decode_responses=False)
    r.ping()

    proc = start_ffmpeg(work_dir)

    def _stop(_sig, _frm):  # type: ignore[no-untyped-def]
        proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    pushed: dict[str, tuple[float, int]] = {}
    log.info("espelhando %d câmera(s) → %s", len(camera_ids), args.redis)
    while True:
        if proc.poll() is not None:
            log.error("ffmpeg morreu (rc=%s)", proc.returncode)
            return 1
        mirror_tick(r, work_dir, camera_ids, args.ttl, pushed)
        time.sleep(0.3)


if __name__ == "__main__":
    raise SystemExit(main())
