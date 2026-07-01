"""
CORE middleware.py — Flask middleware registration: error handlers, security headers,
request ID tracking, request/response logging, and rate limit handling.

Layer: core
Pattern: Middleware (Flask before/after_request hooks + errorhandlers)

Key exports:
  - register_error_handlers: catches EpiMonitorError subclasses and generic exceptions
  - register_security_headers: adds OWASP headers (X-Content-Type-Options, X-Frame-Options, HSTS in prod)
  - register_request_logging: logs method, path, status, duration, and request_id per request
  - register_request_id: propagates X-Request-ID header; generates UUID if absent
  - register_rate_limit_handler: returns 429 JSON for flask-limiter violations

Constraints:
  - /health path is excluded from request logging to avoid log noise
  - HSTS header is only injected when FLASK_ENV=production
  - Generic handler never exposes stack traces to clients — logs full traceback internally

Related: app/core/exceptions.py, app/__init__.py (registration order)
"""
import logging
import os
import time
import traceback
import uuid

from flask import Flask, g, request, jsonify

from app.core.exceptions import EpiMonitorError

logger = logging.getLogger(__name__)


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

    # Produção = qualquer ambiente que não seja debug/teste local. Não depende
    # da env FLASK_ENV (que pode não estar setada no deploy Railway) — usa as
    # flags da config para decidir se envia HSTS.
    is_prod = not app.config.get("DEBUG", False) and not app.config.get(
        "TESTING", False
    )

    # CSP em modo Report-Only por padrão: reporta violações sem bloquear
    # recursos (evita quebrar a SPA React / Swagger UI servidos pela app).
    # Migrar para enforcing (Content-Security-Policy) após calibrar com relatórios.
    csp_policy = (
        "default-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'self'"
    )

    @app.after_request
    def add_security_headers(response):  # type: ignore[no-untyped-def]
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )
        response.headers["Content-Security-Policy-Report-Only"] = csp_policy
        if is_prod or os.environ.get("FLASK_ENV") == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


def register_request_logging(app: Flask) -> None:
    """Log de request/response para debugging."""

    @app.before_request
    def log_request() -> None:
        request._start_time = time.time()  # type: ignore[attr-defined]

    @app.after_request
    def log_response(response):  # type: ignore[no-untyped-def]
        duration = time.time() - getattr(request, "_start_time", time.time())
        if request.path != "/health":
            logger.info(
                "request: %s %s → %d (%.3fs) rid=%s",
                request.method,
                request.path,
                response.status_code,
                duration,
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
    """Handler para 429 Too Many Requests do flask-limiter."""

    @app.errorhandler(429)
    def handle_rate_limit(exc: Exception) -> tuple:
        logger.warning(
            "rate_limit_exceeded: %s %s rid=%s",
            request.method,
            request.path,
            getattr(g, "request_id", "-"),
        )
        return (
            jsonify({"success": False, "error": "Muitas requisições. Tente novamente mais tarde."}),
            429,
        )
