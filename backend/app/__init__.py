"""
EPI Monitor V2 — Application Factory.

Pattern: create_app(config_name) retorna Flask app configurado.
Gunicorn entry point: app:create_app()
"""
import logging
import os
from datetime import timedelta

from flask import Flask, send_from_directory, jsonify
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

    app.epi_config = config  # type: ignore[attr-defined]

    # Logging
    _configure_logging(config)
    logger = logging.getLogger(__name__)

    # Database pool initialization
    if config.DATABASE_URL and not config.TESTING:
        _init_database_pool(config)

    # Extensions
    CORS(app, origins=config.CORS_ORIGINS)
    jwt.init_app(app)

    # SocketIO
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

    # Frontend serving (production)
    _register_frontend_serving(app)

    # Middleware
    register_error_handlers(app)
    register_security_headers(app)
    if not config.TESTING:
        register_request_logging(app)

    # WebSocket bridge (Redis pub/sub → SocketIO → Browser)
    if not config.TESTING and config.REDIS_URL:
        try:
            from app.core.socket_bridge import start_redis_bridge
            start_redis_bridge(socketio)
        except Exception as exc:
            logger.warning("redis_bridge_init_failed: %s", exc)

    logger.info(
        "app_created: env=%s, cors=%s",
        config_name or os.environ.get("FLASK_ENV", "production"),
        config.CORS_ORIGINS,
    )

    return app


def _configure_logging(config: object) -> None:
    """Configura logging estruturado."""
    level = logging.DEBUG if getattr(config, "DEBUG", False) else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _init_database_pool(config: object) -> None:
    """Inicializa ThreadedConnectionPool singleton."""
    try:
        from app.infrastructure.database.connection import DatabasePool

        db_url = getattr(config, "DATABASE_URL", "")
        if db_url:
            DatabasePool.initialize(
                db_url,
                min_conn=getattr(config, "DB_POOL_MIN", 1),
                max_conn=getattr(config, "DB_POOL_MAX", 10),
            )
    except Exception as exc:
        logging.getLogger(__name__).error("db_pool_init_failed: %s", exc)


def _register_blueprints(app: Flask) -> None:
    """Registra todos os blueprints da API v1."""
    from app.api.v1.health.routes import health_bp
    from app.api.v1.auth.routes import auth_bp
    from app.api.v1.training.routes import training_bp
    from app.api.v1.cameras.routes import cameras_bp
    from app.api.v1.streams.routes import streams_bp
    from app.api.v1.videos.routes import videos_bp
    from app.api.v1.dashboard.routes import dashboard_bp
    from app.api.v1.storage.routes import storage_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(cameras_bp)
    app.register_blueprint(streams_bp)
    app.register_blueprint(videos_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(storage_bp)


def _register_frontend_serving(app: Flask) -> None:
    """Serve frontend React em produção (fallback para index.html)."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    possible_paths = [
        os.path.join(base_dir, "frontend", "dist"),
        os.path.join(os.path.dirname(base_dir), "frontend", "dist"),
        os.path.join(os.getcwd(), "frontend", "dist"),
    ]

    dist = None
    for p in possible_paths:
        if os.path.exists(p) and os.path.exists(os.path.join(p, "index.html")):
            dist = p
            break

    logger = logging.getLogger(__name__)
    if dist:
        logger.info("frontend_dist: %s", dist)
    else:
        logger.info("frontend_dist: not found (API-only mode)")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path: str):  # type: ignore[no-untyped-def]
        if dist is None:
            return jsonify({"status": "API online", "frontend": "separate service"}), 200
        if path and os.path.exists(os.path.join(dist, path)):
            return send_from_directory(dist, path)
        index = os.path.join(dist, "index.html")
        if os.path.exists(index):
            return send_from_directory(dist, "index.html")
        return jsonify({"status": "API online"}), 200
