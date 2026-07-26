#!/usr/bin/env python3
"""edge_artery_probe.py — prova a "artéria" edge→cloud (enroll → heartbeat).

⚠️ UTILITÁRIO DE DIAGNÓSTICO, NÃO É O AGENTE DE PRODUÇÃO. O agente real é o
`services/edge-sync-agent/` (placeholder — Fase 4). Este script existe para provar
ponta a ponta que um device fala com a nuvem; não deixar rodando como gambiarra
permanente.

Contrato implementado a partir do CÓDIGO REAL (C-04), não da doc:
  - POST {API}/api/v1/edge/enroll  (público) → 201, envelope {"data": {...}}
        body: {enrollment_token, device_id, device_name, public_key_pem}
        resp: data = {tenant_id, site_id, device_id, scopes}
        → NÃO retorna JWT. O device AUTO-ASSINA (ADR-0019 S7).
  - POST {API}/api/v1/edge/heartbeat  (Authorization: Bearer <JWT RS256 do device>)
        JWT claims OBRIGATÓRIAS (recognition_shared.device.DeviceClaims):
            {tenant_id, site_id, device_id, scopes, iat, exp}
        Verificação no servidor: RS256, verify_exp; sem aud/iss.
        Exige o escopo "heartbeat:write" nas claims (senão 403).
        body: Heartbeat — só `device_id` e `status` são obrigatórios; o resto é
        opcional e aceita null.

Segurança:
  - A chave privada é gerada localmente e NUNCA sai do host. Por padrão fica só em
    memória; com --key-file é gravada com chmod 600. Nunca commitar.
  - Token/JWT nunca são logados (só status HTTP e prefixos de id).

Uso:
    export EDGE_API_URL="https://api-v3-desenvolvimento.up.railway.app"   # DEV
    export ENROLLMENT_TOKEN="<token one-time do Passo 3>"
    python3 scripts/edge_artery_probe.py --once            # enroll + 1 heartbeat
    python3 scripts/edge_artery_probe.py --loop            # + heartbeat a cada 10s

    # No Jetson (telemetria real de GPU via tegrastats):
    python3 scripts/edge_artery_probe.py --loop --jetson

Deps: requests, cryptography, pyjwt  (+ psutil para telemetria real)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout
)
logger = logging.getLogger("artery-probe")

DEFAULT_API = "https://api-v3-desenvolvimento.up.railway.app"  # DEV — nunca produção
EDGE_VERSION = "artery-probe-0.1"
HEARTBEAT_SCOPES = ["heartbeat:write"]  # mínimo exigido por /edge/heartbeat

# Host de PRODUÇÃO — guardrail: este utilitário é só para DEV.
_PROD_MARKERS = ("api-v3-production", "interchange")


def _die(msg: str) -> None:
    logger.error(msg)
    sys.exit(1)


def _require_deps():
    try:
        import jwt  # noqa: PLC0415
        import requests  # noqa: PLC0415
        from cryptography.hazmat.primitives import serialization  # noqa: PLC0415
        from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: PLC0415
    except ImportError as exc:
        _die(f"dependência ausente: {exc}\n  pip3 install requests cryptography pyjwt psutil")
    return jwt, requests, serialization, rsa


# ── Telemetria ────────────────────────────────────────────────────────────────
# Regra de honestidade: se não há fonte real, manda null — nunca número inventado.

def _cpu_mem_disk() -> dict:
    try:
        import psutil  # noqa: PLC0415
    except ImportError:
        logger.warning("psutil ausente → cpu/mem/disk = null (instale: pip3 install psutil)")
        return {"cpu_pct": None, "mem_pct": None, "disk_pct": None}
    return {
        "cpu_pct": round(psutil.cpu_percent(interval=0.5), 2),
        "mem_pct": round(psutil.virtual_memory().percent, 2),
        "disk_pct": round(psutil.disk_usage("/").percent, 2),
    }


def _jetson_gpu() -> dict:
    """GPU do Jetson via tegrastats (NÃO existe nvidia-smi no Orin).

    Parseia `GR3D_FREQ <n>%` (uso de GPU) e `RAM a/bMB` (memória). Qualquer falha
    de parse → null (nunca valor fake).
    """
    out = {"gpu_pct": None, "gpu_mem_pct": None, "gpu_temp_c": None, "cpu_temp_c": None}
    exe = shutil.which("tegrastats") or "/usr/bin/tegrastats"
    if not os.path.exists(exe):
        logger.warning("tegrastats não encontrado → gpu_* = null")
        return out
    try:
        proc = subprocess.run(  # noqa: S603
            [exe, "--interval", "1000"], capture_output=True, text=True, timeout=6
        )
        line = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else ""
    except subprocess.TimeoutExpired as exc:
        line = (exc.stdout or b"").decode(errors="replace").strip().splitlines()[-1] \
            if exc.stdout else ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("tegrastats falhou (%s) → gpu_* = null", exc)
        return out

    if not line:
        logger.warning("tegrastats sem saída → gpu_* = null")
        return out
    m = re.search(r"GR3D_FREQ\s+(\d+)%", line)
    if m:
        out["gpu_pct"] = float(m.group(1))
    m = re.search(r"RAM\s+(\d+)/(\d+)MB", line)
    if m and int(m.group(2)) > 0:
        out["gpu_mem_pct"] = round(int(m.group(1)) / int(m.group(2)) * 100, 2)
    # Sensores térmicos: no L4T r36.4.3 (Orin NX) os nomes são MINÚSCULOS —
    # `gpu@48.4C`, `cpu@50.7C`, `tj@50.7C`. Verificado no box real (2026-07-26);
    # um regex `GPU@` maiúsculo devolvia null silenciosamente.
    m = re.search(r"\bgpu@([\d.]+)C", line, re.IGNORECASE)
    if m:
        out["gpu_temp_c"] = float(m.group(1))
    m = re.search(r"\bcpu@([\d.]+)C", line, re.IGNORECASE)
    if m:
        out["cpu_temp_c"] = float(m.group(1))
    if out["gpu_pct"] is None:
        logger.warning("parse de GR3D_FREQ falhou → gpu_pct = null")
    return out


def build_heartbeat(device_id: str, jetson: bool, sample: bool) -> dict:
    """Monta o corpo do heartbeat.

    jetson=True  → tenta GPU real via tegrastats.
    sample=True  → rodada de "lógica de nuvem" (Mac): campos de pipeline vão como
                   null e o last_error diz explicitamente que NÃO é telemetria de
                   device — para ninguém ler 28 câmeras a 22 FPS que não existem.
    """
    hb = {"device_id": device_id, "status": "healthy", "edge_version": EDGE_VERSION}
    hb.update(_cpu_mem_disk())
    hb.update(_jetson_gpu() if jetson else {"gpu_pct": None, "gpu_mem_pct": None,
                                             "gpu_temp_c": None, "cpu_temp_c": None})

    # Pipeline de inferência ainda NÃO instrumentado (DeepStream não está ligado ao
    # agente — Fase 4 / task-112). null = "não instrumentado", não zero-real.
    hb.update({
        "inference_fps": None,
        "inference_latency_ms": None,
        "cameras_online": None,
        "cameras_total": None,
        "queue_depth": None,
    })
    hb["last_error"] = (
        "probe: rodada de validacao da nuvem (nao e telemetria de device)" if sample
        else "probe: pipeline nao instrumentado (Fase 4) — metricas de inferencia null"
    )
    return hb


# ── Cripto / JWT ──────────────────────────────────────────────────────────────

def gen_keypair(serialization, rsa, key_file: str | None):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    if key_file:
        with open(key_file, "w") as fh:
            fh.write(priv_pem)
        os.chmod(key_file, 0o600)
        logger.info("chave privada gravada em %s (chmod 600) — NUNCA commitar", key_file)
    return priv_pem, pub_pem


def sign_device_jwt(jwt_mod, priv_pem: str, tenant_id: str, site_id: str,
                    device_id: str, scopes: list[str], ttl_s: int = 300) -> str:
    """JWT RS256 auto-assinado com as claims que o DeviceClaims exige."""
    now = int(time.time())
    claims = {
        "tenant_id": tenant_id,
        "site_id": site_id,
        "device_id": device_id,
        "scopes": scopes,
        "iat": now,
        "exp": now + ttl_s,
    }
    return jwt_mod.encode(claims, priv_pem, algorithm="RS256")


# ── Fluxo ─────────────────────────────────────────────────────────────────────

def do_enroll(requests, api: str, token: str, device_id: str, device_name: str,
              pub_pem: str) -> dict:
    url = f"{api}/api/v1/edge/enroll"
    resp = requests.post(url, json={
        "enrollment_token": token,
        "device_id": device_id,
        "device_name": device_name,
        "public_key_pem": pub_pem,
    }, timeout=30)
    logger.info("POST /edge/enroll → HTTP %s", resp.status_code)
    if resp.status_code == 401:
        _die("enroll 401: token inválido, expirado ou já usado (é one-time/24h). Gere outro.")
    if resp.status_code == 409:
        _die(f"enroll 409: device_id '{device_id}' já cadastrado. Use --device-id diferente "
             "ou revogue o anterior no admin.")
    if resp.status_code != 201:
        _die(f"enroll falhou HTTP {resp.status_code}: {resp.text[:300]}")
    data = (resp.json() or {}).get("data") or {}   # envelope success()
    for k in ("tenant_id", "site_id"):
        if not data.get(k):
            _die(f"resposta de enroll sem '{k}': {json.dumps(data)[:200]}")
    logger.info("enrolled OK — tenant=%s… site=%s… scopes=%s",
                str(data["tenant_id"])[:8], str(data["site_id"])[:8], data.get("scopes"))
    return data


def do_heartbeat(requests, jwt_mod, api: str, priv_pem: str, enroll: dict,
                 device_id: str, jetson: bool, sample: bool) -> bool:
    scopes = enroll.get("scopes") or HEARTBEAT_SCOPES
    if "heartbeat:write" not in scopes:
        scopes = [*scopes, "heartbeat:write"]
    token = sign_device_jwt(jwt_mod, priv_pem, enroll["tenant_id"], enroll["site_id"],
                            device_id, scopes)
    body = build_heartbeat(device_id, jetson=jetson, sample=sample)
    resp = requests.post(f"{api}/api/v1/edge/heartbeat", json=body,
                         headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if resp.status_code == 201:
        data = (resp.json() or {}).get("data") or {}
        logger.info("heartbeat 201 — id=%s received_at=%s | cpu=%s mem=%s disk=%s gpu=%s",
                    data.get("id"), data.get("received_at"),
                    body["cpu_pct"], body["mem_pct"], body["disk_pct"], body["gpu_pct"])
        return True
    if resp.status_code == 403:
        logger.error("heartbeat 403 (escopo/claims): %s", resp.text[:200])
    elif resp.status_code == 422:
        logger.error("heartbeat 422 (payload): %s", resp.text[:300])
    else:
        logger.error("heartbeat HTTP %s: %s", resp.status_code, resp.text[:200])
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Prova a artéria edge→cloud (DEV).")
    ap.add_argument("--device-id", default="pandora-rvb-dev")
    ap.add_argument("--device-name", default="Pandora RVB (DEV)")
    ap.add_argument("--once", action="store_true", help="enroll + 1 heartbeat e sai")
    ap.add_argument("--loop", action="store_true", help="heartbeat contínuo")
    ap.add_argument("--interval", type=int, default=10, help="segundos entre heartbeats")
    ap.add_argument("--jetson", action="store_true", help="GPU real via tegrastats")
    ap.add_argument("--sample", action="store_true",
                    help="rodada de validação da nuvem (marca o heartbeat como não-device)")
    ap.add_argument("--key-file", help="grava a chave privada (chmod 600) p/ reuso")
    args = ap.parse_args()

    if not (args.once or args.loop):
        args.once = True

    jwt_mod, requests, serialization, rsa = _require_deps()

    api = (os.environ.get("EDGE_API_URL") or DEFAULT_API).rstrip("/")
    if any(m in api for m in _PROD_MARKERS):
        _die(f"GUARDRAIL: EDGE_API_URL parece ser PRODUÇÃO ({api}). Este utilitário é só DEV.")
    token = os.environ.get("ENROLLMENT_TOKEN")
    if not token:
        _die("ENROLLMENT_TOKEN não definido (export ENROLLMENT_TOKEN='<token do admin>').")

    logger.info("API alvo: %s", api)
    logger.info("device_id=%s | jetson=%s | modo=%s",
                args.device_id, args.jetson, "loop" if args.loop else "once")

    # Egress check — se isto falhar, nada mais importa (o ponto cego do #217).
    try:
        h = requests.get(f"{api}/api/v1/health", timeout=15)
        logger.info("GET /api/v1/health → HTTP %s", h.status_code)
    except Exception as exc:  # noqa: BLE001
        _die(f"sem egress até a nuvem ({exc}). Resolver rede/DNS/firewall ANTES de enrolar.")

    priv_pem, pub_pem = gen_keypair(serialization, rsa, args.key_file)
    enroll = do_enroll(requests, api, token, args.device_id, args.device_name, pub_pem)

    ok = do_heartbeat(requests, jwt_mod, api, priv_pem, enroll, args.device_id,
                      args.jetson, args.sample)
    if not ok:
        sys.exit(1)

    if args.loop:
        logger.info("loop de heartbeat a cada %ss (Ctrl-C para parar; "
                    "limiar de offline no health = 120s)", args.interval)
        sent, failed = 1, 0
        try:
            while True:
                time.sleep(args.interval)
                if do_heartbeat(requests, jwt_mod, api, priv_pem, enroll,
                                args.device_id, args.jetson, args.sample):
                    sent += 1
                else:
                    failed += 1
        except KeyboardInterrupt:
            logger.info("parado. heartbeats enviados=%d falhas=%d (%s)",
                        sent, failed, datetime.now(timezone.utc).isoformat())

    logger.info("FIM — artéria provada até onde este probe alcança. "
                "O agente de produção (Fase 4) NÃO é este script.")


if __name__ == "__main__":
    main()
