"""
EPI Monitor V2 — Camera test endpoint handler.

Handler: test_camera — 5-check connectivity diagnostic.
"""
import logging

from flask_jwt_extended import jwt_required

from app.core.auth import get_current_user_id
from app.core.exceptions import EpiMonitorError
from app.core.responses import success, error

from .helpers import _get_camera_service, _is_admin

logger = logging.getLogger(__name__)


@jwt_required()
def test_camera(camera_id: str):  # type: ignore[no-untyped-def]
    """Testa conectividade da câmera. Retorna diagnóstico estruturado com 5 checks."""
    import socket  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import urllib.parse  # noqa: PLC0415
    from uuid import UUID

    def _check(status: str, message: str) -> dict:
        return {"status": status, "message": message}

    result: dict = {
        "camera_id": camera_id,
        "success": False,
        "error": None,
        "suggestion": None,
        "checks": {
            "url_format": _check("pending", ""),
            "host_reachable": _check("pending", ""),
            "port_open": _check("pending", ""),
            "rtsp_response": _check("pending", ""),
            "stream_available": _check("pending", ""),
        },
    }

    try:
        user_id = get_current_user_id()
        service = _get_camera_service()

        # Check 1: construir URL RTSP
        try:
            rtsp_url = service.build_rtsp_url(UUID(camera_id), user_id, _is_admin(user_id))
            result["checks"]["url_format"] = _check("ok", "URL RTSP construída com sucesso")
        except EpiMonitorError as exc:
            result["checks"]["url_format"] = _check("error", str(exc.message))
            result["error"] = str(exc.message)
            result["suggestion"] = "Verifique se os dados de IP, porta e credenciais estão corretos"
            return success(result)

        parsed = urllib.parse.urlparse(rtsp_url)
        host = parsed.hostname or ""
        port = parsed.port or 554

        # Check 2: host acessível (DNS/IP resolve)
        try:
            socket.gethostbyname(host)
            result["checks"]["host_reachable"] = _check("ok", f"Host {host} encontrado")
        except socket.gaierror:
            result["checks"]["host_reachable"] = _check("error", f"Host {host} não encontrado na rede")
            result["error"] = "Endereço IP não encontrado"
            result["suggestion"] = "Verifique se o IP está correto e se a câmera está na mesma rede"
            return success(result)

        # Check 3: porta aberta (TCP)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            port_result = sock.connect_ex((host, port))
        finally:
            sock.close()

        if port_result != 0:
            result["checks"]["port_open"] = _check("error", f"Porta {port} fechada ou bloqueada")
            result["error"] = f"Porta {port} não está acessível"
            result["suggestion"] = "Verifique se a câmera está ligada e se a porta não está bloqueada no firewall"
            return success(result)

        result["checks"]["port_open"] = _check("ok", f"Porta {port} aberta")

        # Check 4: resposta RTSP via ffprobe (opcional — pode não estar instalado)
        # Mascarar senha na URL antes de logar
        safe_url = rtsp_url
        if parsed.password:
            safe_url = rtsp_url.replace(f":{parsed.password}@", ":****@")

        try:
            proc = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-rtsp_transport", "tcp",
                    "-i", rtsp_url,
                    "-show_entries", "stream=codec_type",
                    "-of", "json",
                    "-timeout", "5000000",
                ],
                capture_output=True,
                timeout=10,
            )
            if proc.returncode == 0:
                result["checks"]["rtsp_response"] = _check("ok", "Câmera respondeu ao RTSP")
                result["checks"]["stream_available"] = _check("ok", "Stream disponível")
                result["success"] = True
            else:
                stderr = proc.stderr.decode(errors="replace")
                if "401" in stderr or "Unauthorized" in stderr:
                    result["checks"]["rtsp_response"] = _check("error", "Autenticação falhou (401)")
                    result["error"] = "Usuário ou senha incorretos"
                    result["suggestion"] = "Verifique as credenciais de acesso da câmera"
                elif "Connection refused" in stderr:
                    result["checks"]["rtsp_response"] = _check("error", "Conexão recusada pela câmera")
                    result["error"] = "Câmera recusou a conexão RTSP"
                    result["suggestion"] = "Verifique se o serviço RTSP está ativo nas configurações da câmera"
                elif "404" in stderr or "Not Found" in stderr:
                    result["checks"]["rtsp_response"] = _check("error", "Caminho do stream não encontrado (404)")
                    result["error"] = "Caminho do stream incorreto"
                    result["suggestion"] = "Verifique o caminho RTSP (ex: /Streaming/Channels/101 para Hikvision)"
                else:
                    result["checks"]["rtsp_response"] = _check("error", "Erro na conexão RTSP")
                    result["error"] = "Não foi possível conectar ao stream"
                    result["suggestion"] = "Verifique se a URL RTSP está correta"
                    logger.debug("ffprobe stderr: %s", stderr[:500])
        except subprocess.TimeoutExpired:
            result["checks"]["rtsp_response"] = _check("error", "Timeout — câmera demorou para responder")
            result["error"] = "Timeout ao conectar ao stream"
            result["suggestion"] = "A câmera pode estar sobrecarregada ou a rede está lenta"
        except FileNotFoundError:
            # ffprobe não instalado — fallback: TCP OK já é suficiente
            result["checks"]["rtsp_response"] = _check("warning", "ffprobe não disponível — teste básico de TCP OK")
            result["checks"]["stream_available"] = _check("warning", "Não foi possível verificar o stream sem ffprobe")
            result["success"] = True  # TCP aberto = provavelmente funciona

        # Persistir resultado do teste na câmera (best-effort)
        service.record_test_result(UUID(camera_id), None if result["success"] else result["error"])

        return success(result)

    except EpiMonitorError:
        raise
    except Exception as exc:
        logger.error("test_camera_error: %s", exc, exc_info=True)
        return error("Erro ao testar câmera", 500)
