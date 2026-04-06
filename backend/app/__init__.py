"""
EPI Monitor V2 — Application Factory.

Pattern: create_app(config_name) retorna Flask app configurado.
Gunicorn entry point: app:create_app()

Ordem de inicialização:
1. Flask app + config
2. Logging estruturado
3. Extensions (JWT, CORS, SocketIO)
4. Blueprints (api/v1/*)
5. Error handlers + middleware
"""
import logging
import os
from datetime import timedelta

from flask import Flask
from flask_cors import CORS

from app.config import get_config
from app.extensions import jwt, socketio
from app.core.middleware import (
    register_error_handlers,
    register_request_logging,
    register_security_headers,
)


def create_app(config_name: str | None = None) -> Flask:
    """Application Factory — cria e configura o Flask app."""
    app = Flask(__name__, static_folder=None)

    # Config
    config = get_config(config_name)
    app.config.from_object(config)
    app.config["JWT_SECRET_KEY"] = config.JWT_SECRET_KEY
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(
        hours=config.JWT_EXPIRY_HOURS
    )

    # Store config on app for access in blueprints
    app.epi_config = config  # type: ignore[attr-defined]

    # Logging
    _configure_logging(config)

    # Extensions
    CORS(app, origins=config.CORS_ORIGINS)
    jwt.init_app(app)

    # SocketIO — message_queue para escalar via Redis
    redis_url = config.REDIS_URL or None
    socketio.init_app(
        app,
        cors_allowed_origins=config.CORS_ORIGINS,
        async_mode="eventlet",
        message_queue=redis_url,
        logger=False,
        engineio_logger=False,
    )

    # Blueprints
    _register_blueprints(app)

    # Middleware
    register_error_handlers(app)
    register_security_headers(app)
    if not config.TESTING:
        register_request_logging(app)

    logging.getLogger(__name__).info(
        "app_created: env=%s, cors=%s",
        config_name or os.environ.get("FLASK_ENV", "production"),
        config.CORS_ORIGINS,
    )

    return app


def _configure_logging(config: object) -> None:
    """Configura logging estruturado — zero print() no backend."""
    level = logging.DEBUG if getattr(config, "DEBUG", False) else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _register_blueprints(app: Flask) -> None:
    """Registra todos os blueprints da API v1."""
    from app.api.v1.health.routes import health_bp

    app.register_blueprint(health_bp)

    from app.api.v1.auth.routes import auth_bp
    app.register_blueprint(auth_bp)

    from app.api.v1.training.routes import training_bp
    app.register_blueprint(training_bp)

    # Blueprints adicionados conforme implementados:
    # from app.api.v1.cameras.routes import cameras_bp
