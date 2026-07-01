"""
Recognition — Camera probe endpoint (task-046).

POST /api/cameras/probe — testa conectividade antes de salvar câmera.

Gate SSRF (obrigatório, inegociável):
  1. ip_or_host resolvido para IP antecipadamente (DNS pinning — evita rebinding TOCTOU).
  2. IP resolvido validado: não loopback, não link-local (169.254.x.x / fe80::).
  3. RFC1918 (192.168/10/172.16) PERMITIDO — câmeras vivem na LAN.
  4. RTSPUrlValidator aplicado na URL final (command injection, scheme, port).
  5. ffprobe recebe o IP resolvido (não o hostname original) para evitar re-resolução.

NUNCA logar credenciais.
"""
import ipaddress
import json
import logging
import socket
import subprocess
import urllib.parse

from flask import request
from flask_jwt_extended import jwt_required

from app.core.auth import get_role, get_tenant_id
from app.core.exceptions import ValidationError
from app.core.responses import error, success
from app.core.validators import RTSPUrlValidator

from .manufacturer_profiles import PROFILES

logger = logging.getLogger(__name__)

_FFPROBE_TIMEOUT_S = 8
_SOCKET_RESOLVE_TIMEOUT_S = 3


def _check_ip_ssrf(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    """Levanta ValidationError se o IP for perigoso para probe (loopback ou link-local)."""
    if ip.is_loopback:
        raise ValidationError("Endereço loopback não permitido")
    if ip.is_link_local:
        raise ValidationError("Endereço link-local não permitido (169.254.x.x / fe80::)")


def _resolve_and_pin(host: str) -> str:
    """Resolve host para IP, valida anti-SSRF, retorna IP como string para pinning.

    Para hostnomes, pré-resolve e valida TODOS os IPs retornados pelo DNS antes
    de usar o primeiro — garante que um atacante não pode fazer DNS rebinding
    (IP público na validação, IP interno na conexão).
    """
    try:
        ip = ipaddress.ip_address(host)
        _check_ip_ssrf(ip)
        return str(ip)
    except ValueError:
        pass  # hostname, não IP literal — cai para resolução DNS

    try:
        records = socket.getaddrinfo(
            host, None,
            socket.AF_UNSPEC,
            socket.SOCK_STREAM,
            0,
            socket.AI_ADDRCONFIG,
        )
    except socket.gaierror:
        raise ValidationError(f"Host '{host}' não pôde ser resolvido")

    if not records:
        raise ValidationError(f"Host '{host}' não retornou endereços")

    pinned: str | None = None
    for _family, _type, _proto, _canonname, sockaddr in records:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
            _check_ip_ssrf(ip)
            if pinned is None:
                pinned = ip_str
        except ValidationError:
            raise  # Propaga erro de segurança imediatamente

    if pinned is None:
        raise ValidationError("Nenhum endereço válido retornado para o host")

    return pinned


def _ffprobe_stream(url: str) -> dict:
    """Executa ffprobe na URL e extrai metadados de vídeo.

    Retorna dict com ok, codec, resolution, fps.
    URL nunca é logada (pode conter credenciais).
    """
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-rtsp_transport", "tcp",
                "-print_format", "json",
                "-show_streams",
                "-timeout", "5000000",
                url,
            ],
            capture_output=True,
            timeout=_FFPROBE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Timeout ao conectar ao stream"}
    except FileNotFoundError:
        return {"ok": True, "codec": None, "resolution": None, "fps": None,
                "warning": "ffprobe não disponível — porta TCP acessível"}

    if proc.returncode != 0:
        stderr = proc.stderr.decode(errors="replace")
        if "401" in stderr or "Unauthorized" in stderr:
            return {"ok": False, "error": "Autenticação falhou — verifique usuário e senha"}
        if "Connection refused" in stderr:
            return {"ok": False, "error": "Câmera recusou a conexão RTSP"}
        if "404" in stderr or "Not Found" in stderr:
            return {"ok": False, "error": "Caminho do stream não encontrado"}
        return {"ok": False, "error": "Não foi possível conectar ao stream"}

    try:
        data = json.loads(proc.stdout)
        streams = data.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        if video:
            w = video.get("width")
            h = video.get("height")
            fps_raw = video.get("r_frame_rate", "0/1")
            try:
                num, den = fps_raw.split("/")
                fps = round(int(num) / int(den), 1) if int(den) else None
            except Exception:
                fps = None
            return {
                "ok": True,
                "codec": video.get("codec_name"),
                "resolution": f"{w}x{h}" if w and h else None,
                "fps": fps,
            }
    except Exception:
        pass

    return {"ok": True, "codec": None, "resolution": None, "fps": None}


def _check_gateway_available(tenant_id: str) -> bool:
    """Verifica se o tenant tem um site_gateway ativo (caminho NAT)."""
    try:
        from app.infrastructure.database.connection import DatabasePool
        pool = DatabasePool.get_instance()
        if pool is None:
            return False
        with pool.get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM public.site_gateways sg "
                "JOIN public.edge_sites es ON es.id = sg.site_id "
                "WHERE sg.tenant_id = %s AND sg.status = 'active' LIMIT 1",
                (str(tenant_id),),
            )
            return cur.fetchone() is not None
    except Exception:
        return False


@jwt_required()
def probe_camera():  # type: ignore[no-untyped-def]
    """POST /api/cameras/probe — testa URL de câmera antes de salvar.

    Body:
      manufacturer  (str)  — intelbras|hikvision|dahua|generic
      ip_or_host    (str)  — IP ou hostname da câmera
      port          (int)  — porta RTSP (padrão: 554)
      username      (str)
      password      (str)
      channel       (int)  — canal (padrão: 1)
      is_behind_nat (bool) — câmera sem IP público (caminho NAT)

    Retorna:
      ok, codec, resolution, fps, substream_url_sugerida, gateway_available (se NAT)
    """
    role = get_role()
    if role not in ("admin", "operator", "superadmin"):
        return error("Acesso não autorizado", 403)

    body = request.get_json(silent=True) or {}
    manufacturer = str(body.get("manufacturer", "generic")).lower().strip()
    ip_or_host = str(body.get("ip_or_host", "")).strip()
    username = str(body.get("username", ""))
    password = str(body.get("password", ""))
    channel = int(body.get("channel", 1))
    is_behind_nat = bool(body.get("is_behind_nat", False))

    if not ip_or_host:
        return error("ip_or_host é obrigatório", 422)

    profile = PROFILES.get(manufacturer)
    if not profile:
        return error(
            f"Fabricante '{manufacturer}' não suportado. "
            f"Aceitos: {', '.join(PROFILES.keys())}",
            422,
        )

    try:
        port = int(body.get("port") or profile["default_port"])
    except (TypeError, ValueError):
        return error("Porta inválida", 422)

    # Caminho NAT: câmera não tem IP público — probe direto impossível
    if is_behind_nat:
        tenant_id = get_tenant_id()
        gateway_available = _check_gateway_available(str(tenant_id))
        # Gera URL sugerida com o host original (para preenchimento da UI)
        url_kwargs = dict(
            user=urllib.parse.quote(username, safe=""),
            password=urllib.parse.quote(password, safe=""),
            host=ip_or_host,
            port=port,
            channel=channel,
        )
        substream_url = profile["rtsp_sub"].format(**url_kwargs)
        return success({
            "ok": None,
            "method": "nat",
            "gateway_available": gateway_available,
            "substream_url_sugerida": substream_url,
            "message": (
                "Câmera atrás de NAT — probe direto não disponível. "
                + ("Gateway ativo detectado para este tenant."
                   if gateway_available
                   else "Configure um gateway de site para acesso remoto.")
            ),
        })

    # Gate SSRF: resolve DNS → valida IP → pina endereço
    try:
        pinned_ip = _resolve_and_pin(ip_or_host)
    except ValidationError as exc:
        return error(str(exc), 422)

    # Constrói URLs com IP pinado (evita re-resolução pelo ffprobe)
    url_kwargs_pinned = dict(
        user=urllib.parse.quote(username, safe=""),
        password=urllib.parse.quote(password, safe=""),
        host=pinned_ip,
        port=port,
        channel=channel,
    )
    main_url = profile["rtsp_main"].format(**url_kwargs_pinned)
    sub_url = profile["rtsp_sub"].format(**url_kwargs_pinned)

    # Valida URL construída (command injection, scheme, port range)
    try:
        RTSPUrlValidator.validate(main_url)
    except ValidationError as exc:
        return error(str(exc), 422)

    # URL sugerida usa o host original (para exibição na UI)
    url_kwargs_display = {**url_kwargs_pinned, "host": ip_or_host}
    substream_url_display = profile["rtsp_sub"].format(**url_kwargs_display)

    # Tenta probe no main stream, depois no sub stream
    result = _ffprobe_stream(main_url)
    if not result.get("ok") and "Não foi possível" not in result.get("error", ""):
        pass  # erro de autenticação/404 — não tenta sub
    elif not result.get("ok"):
        result = _ffprobe_stream(sub_url)

    logger.info(
        "camera_probe: manufacturer=%s host=%s port=%d ok=%s",
        manufacturer, ip_or_host, port, result.get("ok"),
    )

    return success({
        "ok": result.get("ok"),
        "codec": result.get("codec"),
        "resolution": result.get("resolution"),
        "fps": result.get("fps"),
        "substream_url_sugerida": substream_url_display if result.get("ok") else None,
        "warning": result.get("warning"),
        "error": result.get("error"),
    })
