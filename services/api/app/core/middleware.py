"""
CORE middleware.py — Flask middleware registration: error handlers, security headers,
request ID tracking, request/response logging, and rate limit handling.

Layer: core
Pattern: Middleware (Flask before/after_request hooks + errorhandlers)

Key exports:
  - register_error_handlers: catches EpiMonitorError subclasses and generic exceptions
  - register_security_headers: adds OWASP headers (X-Content-Type-Options, X-Frame-Options, HSTS in prod)
  - register_request_logging: logs ONE consolidated access-log line per request — rid,
    método, rota, status, duração, bytes, IP do cliente. Esta é a única linha de access
    log emitida pelo app (o access log nativo do worker gevent/geventwebsocket é
    silenciado em app/core/logging_config.py — ver _silence_gevent_access_log).
  - register_request_id: propagates X-Request-ID header; generates UUID if absent
  - register_rate_limit_handler: returns 429 JSON for flask-limiter violations, e faz
    backfill de g.request_id/request._start_time quando necessário (ver nota abaixo)

Constraints:
  - /health path is excluded from request logging to avoid log noise
  - HSTS header is only injected when FLASK_ENV=production
  - Generic handler never exposes stack traces to clients — logs full traceback internally
  - flask-limiter registra seu próprio before_request em limiter.init_app() (chamado em
    app/__init__.py ANTES de register_request_id/register_request_logging). Quando o
    limite estoura, a request é abortada antes de chegar aos before_request deste
    módulo — sem o backfill em register_rate_limit_handler, a linha consolidada do 429
    sairia com rid="-" e duração inválida (bug observado em produção 04/08).

Related: app/core/exceptions.py, app/__init__.py (registration order),
         app/core/logging_config.py (split stdout/stderr + silêncio do access log gevent)
"""
import logging
import os
import re
import time
import traceback
import uuid

from flask import Flask, g, request, jsonify

from app.core.exceptions import EpiMonitorError

logger = logging.getLogger(__name__)

# task-068: routine HLS polling (`stream.m3u8` refresh + `.ts` segment fetches) happens
# at ~1 req/s per open camera and would otherwise flood INFO-level logs / log storage.
# Only these two routine, successful requests are downgraded to DEBUG; start/stop/status
# and any error response keep logging at INFO so operational events stay visible.
_ROUTINE_STREAM_PATH = re.compile(r"/stream/(stream\.m3u8|[^/]+\.ts)$")


def _client_ip() -> str:
    """IP do cliente real para o access log.

    Railway tem proxy na frente — `request.remote_addr` sozinho é o IP interno
    do proxy (100.64.x.x), não o do cliente. Usa o primeiro hop de
    X-Forwarded-For quando presente (mesmo hop único que ProxyFix(x_for=1)
    confia em app/__init__.py), com fallback para remote_addr fora desse
    cenário (ex.: TESTING, onde ProxyFix não é aplicado).
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "-"


def _response_bytes(response) -> str:  # type: ignore[no-untyped-def]
    """Bytes da resposta — Content-Length quando disponível.

    Streaming sem length conhecido (ex.: HLS via stream_with_context) não tem
    Content-Length setado; loga "-" em vez de inventar um valor.
    """
    length = response.content_length
    return str(length) if length is not None else "-"


def register_error_handlers(app: Flask) -> None:
    """Registra error handlers globais no Flask app."""

    @app.errorhandler(EpiMonitorError)
    def handle_app_error(exc: EpiMonitorError) -> tuple:
        """Handler para exceções de domínio — retorna status correto."""
        logger.warning(
            "app_error: %s (status=%d, path=%s)",
            exc.message,
            exc.status_code,
            request.path,
        )
        return (
            jsonify({"success": False, "error": exc.message}),
            exc.status_code,
        )

    @app.errorhandler(404)
    def handle_404(exc: Exception) -> tuple:
        return jsonify({"success": False, "error": "Recurso não encontrado"}), 404

    @app.errorhandler(405)
    def handle_405(exc: Exception) -> tuple:
        return jsonify({"success": False, "error": "Método não permitido"}), 405

    @app.errorhandler(Exception)
    def handle_generic(exc: Exception) -> tuple:
        """Handler genérico — nunca expõe stack trace ao cliente."""
        logger.error(
            "unhandled_error: %s %s\n%s",
            request.method,
            request.path,
            traceback.format_exc(),
        )
        return jsonify({"success": False, "error": "Erro interno"}), 500


def register_security_headers(app: Flask) -> None:
    """Adiciona security headers OWASP a todas as responses."""

    @app.after_request
    def add_security_headers(response):  # type: ignore[no-untyped-def]
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if os.environ.get("FLASK_ENV") == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


def register_request_logging(app: Flask) -> None:
    """Log de request/response — UMA linha por requisição no access log.

    Campos: rid · método · rota · status · duração · bytes · IP do cliente.
    Substitui as duas linhas que existiam antes (esta + o access log nativo do
    worker gevent/geventwebsocket, silenciado em logging_config.py): a linha
    do middleware já carrega tudo que a do gevent tinha (bytes, IP) além do
    que só ela tinha (rid, duração) — sem redundância nem perda de campo.
    """

    @app.before_request
    def log_request() -> None:
        request._start_time = time.time()  # type: ignore[attr-defined]

    @app.after_request
    def log_response(response):  # type: ignore[no-untyped-def]
        start_time = getattr(request, "_start_time", None)
        duration = (time.time() - start_time) if start_time is not None else 0.0
        if request.path != "/health":
            is_routine_stream = (
                response.status_code in (200, 304)
                and bool(_ROUTINE_STREAM_PATH.search(request.path))
            )
            log_fn = logger.debug if is_routine_stream else logger.info
            log_fn(
                "request: %s %s → %d (%.3fs) bytes=%s ip=%s rid=%s",
                request.method,
                request.path,
                response.status_code,
                duration,
                _response_bytes(response),
                _client_ip(),
                getattr(g, "request_id", "-"),
            )
        return response


def register_request_id(app: Flask) -> None:
    """Rastreamento de request via X-Request-ID header (distribuído)."""

    @app.before_request
    def set_request_id() -> None:
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    @app.after_request
    def inject_request_id(response):  # type: ignore[no-untyped-def]
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        return response


def register_rate_limit_handler(app: Flask) -> None:
    """Handler para 429 Too Many Requests do flask-limiter.

    flask-limiter registra seu before_request cedo (limiter.init_app(), antes de
    register_request_id/register_request_logging — ver app/__init__.py), então um
    429 nunca passa pelos before_request deste módulo: g.request_id e
    request._start_time não existem ainda quando chegamos aqui. Faz o backfill dos
    dois para que a ÚNICA linha de access log (log_response, em
    register_request_logging) cubra o 429 com rid real e duração válida — sem
    isso o caso mais importante para investigar rate limit sumiria do log
    correlacionável. Não loga nada diretamente aqui: log_response continua sendo
    a única fonte da linha de access log, para não duplicar.
    """

    @app.errorhandler(429)
    def handle_rate_limit(exc: Exception) -> tuple:
        if not hasattr(g, "request_id"):
            g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        if not hasattr(request, "_start_time"):
            request._start_time = time.time()  # type: ignore[attr-defined]
        return (
            jsonify({"success": False, "error": "Muitas requisições. Tente novamente mais tarde."}),
            429,
        )
