#!/usr/bin/env python3
"""soak_load.py — injeta carga realística durante o soak (task-113).

Exercita o CAMINHO COMPLETO edge->cloud da co-residência:
  detecção sintética -> Redis pub/sub detections:{camera_id} (ADR-0002)
  -> edge-sync-agent -> API -> Postgres, + queries de leitura no dashboard.

Layout RVB (CENARIO_RVB): cam0-15 EPI, cam16-23 Estacionamento, cam24-25
Qualidade aux, cam26-27 Qualidade principal (4MP). A taxa agregada default
(~210 inf/s no cenário) é parametrizável; aqui geramos EVENTOS de detecção
(subconjunto que vira alerta/evidência), não todos os frames.

Stdlib pura + redis-cli (presente no box). Sem deps. Tolerante a falha de rede.

Uso:
    python3 soak_load.py --redis-url redis://127.0.0.1:6379/0 \
        --api-url http://127.0.0.1:8000 --events-per-s 30 --duration-s 14400 \
        --read-every-s 10
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

# Layout de câmeras do cenário RVB (índices dos paths sintéticos cam{N}).
GROUPS = {
    "epi": (range(0, 16), ["capacete", "oculos", "luva", "bota", "sem_capacete"]),
    "parking": (range(16, 24), ["pessoa", "carro", "caminhao", "onibus", "moto"]),
    "quality_aux": (range(24, 26), ["etapa_ok", "etapa_pendente"]),
    "quality_main": (range(26, 28), ["atributo_ok", "atributo_falha"]),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_detection(cam_idx: int, group: str, classes: list[str], rng: random.Random) -> dict:
    """Payload de detecção sintético (contrato relay ADR-0002)."""
    n = rng.randint(1, 5)
    dets = []
    for _ in range(n):
        cls = rng.choice(classes)
        x, y = rng.uniform(0, 0.7), rng.uniform(0, 0.7)
        dets.append({
            "class": cls,
            "confidence": round(rng.uniform(0.35, 0.98), 3),
            "bbox": [round(x, 4), round(y, 4),
                     round(x + rng.uniform(0.05, 0.3), 4),
                     round(y + rng.uniform(0.05, 0.3), 4)],
        })
    return {
        "camera_id": f"cam{cam_idx}",
        "group": group,
        "ts": _now_iso(),
        "detections": dets,
    }


def publish_redis(redis_url: str, channel: str, payload: dict) -> bool:
    if not shutil.which("redis-cli"):
        return False
    try:
        subprocess.run(
            ["redis-cli", "-u", redis_url, "PUBLISH", channel, json.dumps(payload)],
            capture_output=True, timeout=3, check=False,
        )
        return True
    except Exception:
        return False


def api_read(api_url: str, path: str, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(api_url.rstrip("/") + path, timeout=timeout) as r:
            r.read(256)
            return r.status < 500
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Soak load injector (task-113)")
    p.add_argument("--redis-url", default="redis://127.0.0.1:6379/0")
    p.add_argument("--api-url", default="http://127.0.0.1:8000")
    p.add_argument("--channel-template", default="detections:{camera_id}")
    p.add_argument("--events-per-s", type=float, default=30.0)
    p.add_argument("--duration-s", type=float, default=14400.0)  # 4h
    p.add_argument("--read-every-s", type=float, default=10.0)
    p.add_argument("--seed", type=int, default=1337)
    args = p.parse_args(argv)

    rng = random.Random(args.seed)  # determinístico (sem Math.random surpresa)
    cams = [(idx, g, classes) for g, (rng_idx, classes) in GROUPS.items() for idx in rng_idx]

    # endpoints de leitura que o dashboard/operador realmente bate
    read_paths = ["/api/v1/health", "/api/v1/health/metrics"]

    t_end = time.monotonic() + args.duration_s
    next_read = time.monotonic()
    period = 1.0 / max(0.1, args.events_per_s)
    published = failed = reads = 0
    redis_ok_once = False

    print(f"soak_load: {args.events_per_s} ev/s por {args.duration_s/3600:.1f}h "
          f"em {len(cams)} câmeras", file=sys.stderr)
    try:
        while time.monotonic() < t_end:
            cam_idx, group, classes = rng.choice(cams)
            payload = make_detection(cam_idx, group, classes, rng)
            channel = args.channel_template.format(camera_id=payload["camera_id"])
            if publish_redis(args.redis_url, channel, payload):
                published += 1
                redis_ok_once = True
            else:
                failed += 1

            now = time.monotonic()
            if now >= next_read:
                api_read(args.api_url, rng.choice(read_paths))
                reads += 1
                next_read = now + args.read_every_s

            if published % 500 == 0 and published:
                print(f"  publicados={published} falhas={failed} reads={reads}",
                      file=sys.stderr)
            time.sleep(period)
    except KeyboardInterrupt:
        pass

    print(f"soak_load FIM: publicados={published} falhas={failed} reads={reads}",
          file=sys.stderr)
    if not redis_ok_once:
        print("[AVISO] nenhum PUBLISH teve sucesso — redis-cli ausente ou Redis fora.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
