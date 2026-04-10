"""
EPI Monitor V2 — Input validators.

RTSPUrlValidator: multi-layer validation antes de qualquer URL chegar ao FFmpeg.
VideoUploadValidator: validação de extensão e filename antes de presigned URL.
"""
import ipaddress
import logging
import re
from urllib.parse import urlparse

from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Characters perigosos em filenames
_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Regex para validar filename HLS (evitar path traversal)
_HLS_FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-]+\.(m3u8|ts)$')


class VideoUploadValidator:
    """Valida uploads de vídeo antes de gerar presigned URL."""

    ALLOWED_EXTENSIONS: frozenset[str] = frozenset({"mp4", "avi", "mov"})
    MAX_FILENAME_LENGTH: int = 255
    MAX_SIZE_BYTES: int = 2 * 1024 * 1024 * 1024  # 2GB

    @staticmethod
    def validate_extension(filename: str) -> str:
        """Extrai e valida extensão. Retorna extensão normalizada."""
        if not filename or "." not in filename:
            raise ValidationError("Filename deve ter extensão")
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in VideoUploadValidator.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"Extensão '{ext}' não permitida. "
                f"Aceitas: {', '.join(sorted(VideoUploadValidator.ALLOWED_EXTENSIONS))}"
            )
        return ext

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Remove caracteres perigosos, limita tamanho."""
        if not filename:
            raise ValidationError("Filename não pode ser vazio")
        sanitized = _UNSAFE_FILENAME_CHARS.sub("_", filename)
        sanitized = sanitized.strip(". ")
        if len(sanitized) > VideoUploadValidator.MAX_FILENAME_LENGTH:
            ext = sanitized.rsplit(".", 1)[-1] if "." in sanitized else ""
            max_name = VideoUploadValidator.MAX_FILENAME_LENGTH - len(ext) - 1
            sanitized = sanitized[:max_name] + "." + ext
        return sanitized


class RTSPUrlValidator:
    """Multi-layer validation de URLs de stream (RTSP e HTTP/ISAPI).

    Camadas de validação:
    1. Formato da URL (scheme, host, port)
    2. IP address validation (não aceita loopback, multicast)
    3. Blocklist de caracteres perigosos (command injection)
    4. Tamanho máximo da URL
    """

    MAX_URL_LENGTH: int = 2048
    ALLOWED_SCHEMES: frozenset[str] = frozenset({"rtsp", "rtsps", "http", "https"})
    MIN_PORT: int = 1
    MAX_PORT: int = 65535

    # Caracteres que podem ser usados para command injection no FFmpeg.
    # NOTA: '&' excluído intencionalmente — é separador de query string em URLs RTSP
    # (ex: ?channel=1&subtype=0). Credenciais com '&' são URL-encoded como '%26'
    # por build_rtsp_url(), portanto não chegam como literal aqui.
    _DANGEROUS_CHARS = re.compile(r'[;|$`\n\r]')

    @classmethod
    def validate(cls, url: str) -> str:
        """Valida URL de stream (RTSP ou HTTP). Retorna URL ou raises ValidationError."""
        if not url:
            raise ValidationError("URL de stream não pode ser vazia")

        # Layer 1: tamanho
        if len(url) > cls.MAX_URL_LENGTH:
            raise ValidationError(
                f"URL excede tamanho máximo ({cls.MAX_URL_LENGTH} chars)"
            )

        # Layer 2: caracteres perigosos (command injection)
        if cls._DANGEROUS_CHARS.search(url):
            raise ValidationError(
                "URL contém caracteres não permitidos"
            )

        # Layer 3: formato da URL
        try:
            parsed = urlparse(url)
            # Force port parsing to catch invalid ports early
            _ = parsed.port
        except ValueError as exc:
            raise ValidationError(f"URL malformada: {exc}") from exc
        except Exception as exc:
            raise ValidationError(f"URL malformada: {exc}") from exc

        if parsed.scheme.lower() not in cls.ALLOWED_SCHEMES:
            raise ValidationError(
                f"Scheme '{parsed.scheme}' não permitido. "
                f"Aceitos: {', '.join(sorted(cls.ALLOWED_SCHEMES))}"
            )

        if not parsed.hostname:
            raise ValidationError("URL deve ter hostname")

        # Layer 4: validação de IP (se for IP, não hostname)
        try:
            ip = ipaddress.ip_address(parsed.hostname)
            if ip.is_loopback:
                raise ValidationError("Endereço loopback não permitido")
            if ip.is_multicast:
                raise ValidationError("Endereço multicast não permitido")
            if ip.is_reserved:
                raise ValidationError("Endereço reservado não permitido")
            if ip.is_unspecified:
                raise ValidationError("Endereço 0.0.0.0 não permitido")
        except ValueError:
            # É um hostname, não um IP — OK
            pass

        # Layer 5: porta
        if parsed.port is not None:
            if not (cls.MIN_PORT <= parsed.port <= cls.MAX_PORT):
                raise ValidationError(
                    f"Porta {parsed.port} fora do range permitido "
                    f"({cls.MIN_PORT}-{cls.MAX_PORT})"
                )

        logger.debug("Stream URL validated: %s://%s", parsed.scheme, parsed.hostname)
        return url


class HLSFilenameValidator:
    """Valida filenames de HLS para evitar path traversal."""

    @staticmethod
    def validate(filename: str) -> str:
        """Valida filename HLS. Raises ValidationError se inválido."""
        if not filename:
            raise ValidationError("Filename não pode ser vazio")
        if ".." in filename or "/" in filename or "\\" in filename:
            raise ValidationError("Path traversal detectado")
        if not _HLS_FILENAME_PATTERN.match(filename):
            raise ValidationError(
                "Filename HLS inválido — apenas [a-zA-Z0-9_-].(m3u8|ts)"
            )
        return filename
