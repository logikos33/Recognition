"""
CORE playback_token.py — token de playback HLS assinado, de vida curta (S2).

Motivo (S2): `serve_hls` é público por design (hls.js não envia headers de auth),
então qualquer um que soubesse o UUID da câmera lia os segmentos de QUALQUER
tenant. Este token amarra a URL de playback a uma câmera específica e a uma
janela curta de tempo, sem depender de headers.

Formato: "<exp>.<sig_b64url>" — seguro para um segmento de path.
  - exp: epoch (s) de expiração
  - sig: HMAC-SHA256(secret, "<camera_id>:<exp>")

Distribuição por PATH (não query): a URL do playlist é
`/api/cameras/<id>/stream/s/<token>/stream.m3u8`; os segmentos `.ts` são
referências relativas no m3u8 e resolvem para
`/api/cameras/<id>/stream/s/<token>/stream0.ts` — o token viaja no path
automaticamente, sem reescrever o m3u8 (query param seria descartado pelo
hls.js na resolução relativa).

Constraints:
  - Segredo = JWT_SECRET_KEY (mesmo já usado para tokens de usuário).
  - Comparação de assinatura em tempo constante (hmac.compare_digest).
  - Zero PII no token; nunca logar o token.
"""
import base64
import hashlib
import hmac
import logging
import os
import time

logger = logging.getLogger(__name__)

# TTL padrão: 1h. O player renova via novo /stream/start quando expira.
DEFAULT_PLAYBACK_TTL_S = int(os.environ.get("HLS_PLAYBACK_TOKEN_TTL", "3600"))


def playback_enforced() -> bool:
    """True se a checagem de tenant no serve_hls deve ser OBRIGATÓRIA.

    Default ON (era OFF). Enquanto esteve desligado, `serve_hls` ficava
    completamente PÚBLICO: ele não tem `@jwt_required` por design (hls.js não
    envia header de auth), e o token era o único portão. Qualquer um que
    soubesse o UUID de uma câmera assistia ao vivo — sem login, de qualquer
    tenant. Com o live view do edge (LV-1) o Redis passou a ter segmento
    sempre, então sempre havia vídeo a vazar.

    O default só pôde virar depois de o frontend consumir a URL tokenizada de
    `/stream/start` e `/stream/info` (mesmo PR) — ligar antes disso quebraria
    o player, que fixava a URL legada.

    `HLS_REQUIRE_PLAYBACK_TOKEN=0` ainda desliga, como escape hatch de
    diagnóstico. É um downgrade de segurança consciente: NÃO usar em produção
    (gate de go-live em docs/ROADMAP_GO_LIVE.md).
    """
    raw = os.environ.get("HLS_REQUIRE_PLAYBACK_TOKEN", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def _secret() -> bytes:
    # Sem fallback silencioso de tenant, mas o segredo de assinatura tem um
    # default só para ambiente de teste/dev (o mesmo padrão do resto do app).
    return (os.environ.get("JWT_SECRET_KEY") or "test-secret-key").encode()


def _sign(camera_id: str, exp: int) -> str:
    mac = hmac.new(_secret(), f"{camera_id}:{exp}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def mint_playback_token(camera_id: str, ttl_s: int = DEFAULT_PLAYBACK_TTL_S) -> str:
    """Emite token de playback para `camera_id`, válido por `ttl_s` segundos."""
    exp = int(time.time()) + ttl_s
    return f"{exp}.{_sign(str(camera_id), exp)}"


def verify_playback_token(token: str, camera_id: str) -> bool:
    """Valida assinatura + expiração + vínculo com `camera_id`.

    Retorna False (nunca levanta) para qualquer token malformado/expirado/adulterado.
    """
    if not token or not isinstance(token, str):
        return False
    try:
        exp_str, sig = token.split(".", 1)
        exp = int(exp_str)
    except (ValueError, AttributeError):
        return False
    if exp < int(time.time()):
        return False
    expected = _sign(str(camera_id), exp)
    return hmac.compare_digest(expected, sig)
