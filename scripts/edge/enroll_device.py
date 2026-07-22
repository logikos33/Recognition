#!/usr/bin/env python3
"""Cliente de enrollment + auto-assinatura RS256 para device edge (Recognition).

Preenche a peça que faltava no caminho de heartbeat: o backend
(`/api/v1/edge/heartbeat`, `/events/ingest`) exige um JWT RS256 **assinado pela
chave privada do device** (ADR-0019 — o device auto-assina). O coletor de
telemetria (`edge-sync-agent/app/telemetry`) só consome um `EDGE_DEVICE_BEARER`
pronto — nada no repo o gerava. Este script gera.

Fluxo (o operador roda no box, uma vez):

  1. `enroll`  — gera um keypair RSA-2048, chama `POST /api/v1/edge/enroll` com a
     public key + o enrollment-token (que o admin gera na nuvem), guarda a chave
     privada + o contexto (tenant/site/device/scopes) e imprime as linhas de env
     (`EDGE_API_URL` + `EDGE_DEVICE_BEARER`) para o `edge-telemetry.env`.
  2. `sign`    — re-assina um bearer novo a partir da chave/contexto já salvos
     (quando o token expira), sem re-enrolar.

Contrato do token (idêntico ao verificado em `core/device_auth.verify_device_token`
e ao recibo de `tests/integration/test_edge_heartbeat._make_token`):
  claims = {tenant_id, site_id, device_id, scopes:[...], iat, exp}, alg RS256.

Dependências: `cryptography`, `PyJWT`, `requests` (já em requirements/base+api).

Uso:
  python enroll_device.py enroll \\
      --api-url https://api-v3-production-2b22.up.railway.app \\
      --enrollment-token <TOKEN_DO_ADMIN> \\
      --device-id pandora-orin-rvb --device-name "Orin RVB (teste)"
  python enroll_device.py sign            # re-assina do estado salvo
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import time
from pathlib import Path

DEFAULT_STATE_DIR = Path(os.environ.get("EDGE_STATE_DIR", str(Path.home() / ".recognition")))
DEFAULT_KEY_PATH = DEFAULT_STATE_DIR / "device_key.pem"
DEFAULT_CTX_PATH = DEFAULT_STATE_DIR / "device_ctx.json"
DEFAULT_TTL_HOURS = 720  # 30 dias — ambiente de teste; renovar com `sign`
_ENROLL_PATH = "/api/v1/edge/enroll"


def _crypto_imports():
    """Importa cryptography + PyJWT (keygen/assinatura). Mensagem clara se faltarem."""
    try:
        import jwt  # noqa: PLC0415
        from cryptography.hazmat.primitives import serialization  # noqa: PLC0415
        from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - ambiente sem deps
        sys.exit(f"Dependência ausente ({exc.name}). Instale: pip install cryptography PyJWT")
    return jwt, serialization, rsa


def _requests_import():
    """Importa requests (só o comando `enroll` precisa)."""
    try:
        import requests  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - ambiente sem deps
        sys.exit(f"Dependência ausente ({exc.name}). Instale: pip install requests")
    return requests


def generate_keypair() -> tuple[str, str]:
    """Gera um keypair RSA-2048. Retorna (private_pem, public_pem)."""
    _, serialization, rsa = _crypto_imports()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def sign_token(private_pem: str, ctx: dict, ttl_hours: int = DEFAULT_TTL_HOURS) -> str:
    """Auto-assina um DeviceClaims JWT RS256 a partir do contexto do enrollment."""
    jwt, _, _ = _crypto_imports()
    now = int(time.time())
    return jwt.encode(
        {
            "tenant_id": str(ctx["tenant_id"]),
            "site_id": str(ctx["site_id"]),
            "device_id": ctx["device_id"],
            "scopes": list(ctx["scopes"]),
            "iat": now,
            "exp": now + ttl_hours * 3600,
        },
        private_pem,
        algorithm="RS256",
    )


def _write_private_key(path: Path, private_pem: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(private_pem)
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600 — chave privada


def _emit_env(api_url: str, bearer: str) -> None:
    print("\n# --- cole no edge-telemetry.env (e reinicie o coletor) ---")
    print(f"EDGE_API_URL={api_url.rstrip('/')}")
    print(f"EDGE_DEVICE_BEARER={bearer}")


def cmd_enroll(args: argparse.Namespace) -> int:
    requests = _requests_import()
    private_pem, public_pem = generate_keypair()

    url = args.api_url.rstrip("/") + _ENROLL_PATH
    resp = requests.post(
        url,
        json={
            "enrollment_token": args.enrollment_token,
            "device_id": args.device_id,
            "device_name": args.device_name,
            "public_key_pem": public_pem,
        },
        timeout=30,
    )
    if resp.status_code != 201:
        sys.stderr.write(f"Enroll falhou ({resp.status_code}): {resp.text}\n")
        return 1

    data = resp.json().get("data", resp.json())
    ctx = {
        "api_url": args.api_url.rstrip("/"),
        "tenant_id": data["tenant_id"],
        "site_id": data["site_id"],
        "device_id": data["device_id"],
        "scopes": data.get("scopes") or ["heartbeat:write", "events:write"],
    }

    _write_private_key(args.key_path, private_pem)
    args.ctx_path.write_text(json.dumps(ctx, indent=2))

    sys.stderr.write(
        f"Enrolado: device={ctx['device_id']} tenant={ctx['tenant_id'][:8]} "
        f"site={ctx['site_id'][:8]} scopes={ctx['scopes']}\n"
        f"Chave privada: {args.key_path} · contexto: {args.ctx_path}\n"
    )
    bearer = sign_token(private_pem, ctx, args.ttl_hours)
    _emit_env(ctx["api_url"], bearer)
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    if not args.key_path.exists() or not args.ctx_path.exists():
        sys.stderr.write(
            f"Estado não encontrado ({args.key_path} / {args.ctx_path}). Rode `enroll` primeiro.\n"
        )
        return 1
    private_pem = args.key_path.read_text()
    ctx = json.loads(args.ctx_path.read_text())
    bearer = sign_token(private_pem, ctx, args.ttl_hours)
    _emit_env(ctx["api_url"], bearer)
    return 0


def build_parser() -> argparse.ArgumentParser:
    # Args comuns disponíveis antes E depois do subcomando (parent parser).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--key-path", type=Path, default=DEFAULT_KEY_PATH, help="PEM da chave privada")
    common.add_argument("--ctx-path", type=Path, default=DEFAULT_CTX_PATH, help="JSON do contexto")
    common.add_argument("--ttl-hours", type=int, default=DEFAULT_TTL_HOURS, help="validade do bearer (h)")

    p = argparse.ArgumentParser(
        description="Enrollment + auto-assinatura RS256 do device edge.", parents=[common]
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("enroll", parents=[common], help="gera keypair, enrola e imprime o env")
    e.add_argument("--api-url", required=True, help="base da API cloud")
    e.add_argument("--enrollment-token", required=True, help="token one-time do admin")
    e.add_argument("--device-id", required=True, help="id estável do device")
    e.add_argument("--device-name", default=None, help="nome amigável (opcional)")
    e.set_defaults(func=cmd_enroll)

    s = sub.add_parser("sign", parents=[common], help="re-assina um bearer do estado salvo")
    s.set_defaults(func=cmd_sign)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
