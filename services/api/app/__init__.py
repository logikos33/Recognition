"""
Recognition — Application Factory.

Pattern: create_app(config_name) retorna Flask app configurado.
Gunicorn entry point: app:create_app()
"""
import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

# Make shared/python (recognition_shared) importable from the monorepo root.
# Sobe a árvore até achar shared/python — funciona local (services/api/app)
# e no container (/app/app, achatado pelo COPY do Dockerfile).
_here = Path(__file__).resolve()
for _ancestor in _here.parents:
    _candidate = _ancestor / "shared" / "python"
    if _candidate.is_dir():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from app.config import get_config
from app.core.middleware import (
    register_error_handlers,
    register_rate_limit_handler,
    register_request_id,
    register_request_logging,
    register_security_headers,
)
from app.extensions import jwt, limiter, socketio

try:
    from flasgger import Swagger as _Swagger
    _HAS_FLASGGER = True
except ImportError:
    _HAS_FLASGGER = False
    _Swagger = None  # type: ignore[assignment]


def create_app(config_name: str | None = None) -> Flask:
    """Application Factory — cria e configura o Flask app."""
    app = Flask(__name__, static_folder=None)

    # Config
    config = get_config(config_name)
    app.config.from_object(config)
    app.config["JWT_SECRET_KEY"] = config.JWT_SECRET_KEY
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["JWT_ALGORITHM"] = config.JWT_ALGORITHM
    app.config["JWT_DECODE_ALGORITHMS"] = [config.JWT_ALGORITHM]
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
        _auto_version_on_deploy()

    # Extensions
    CORS(app, origins=config.CORS_ORIGINS)
    jwt.init_app(app)
    _register_jwt_error_handlers(jwt)

    # Rate limiter (Redis in prod, memory in dev/test)
    app.config["RATELIMIT_STORAGE_URI"] = config.REDIS_URL or "memory://"
    app.config["RATELIMIT_ENABLED"] = not config.TESTING
    limiter.init_app(app)

    # SocketIO — gevent in production; threading in tests (gevent not required for tests)
    redis_url = config.REDIS_URL or None
    socketio.init_app(
        app,
        cors_allowed_origins=config.CORS_ORIGINS,
        async_mode="threading" if config.TESTING else "gevent",
        message_queue=redis_url if not config.TESTING else None,
        logger=False,
        engineio_logger=False,
    )

    # Blueprints
    _register_blueprints(app)

    # Frontend serving (production)
    _register_frontend_serving(app)

    # Swagger UI
    if not config.TESTING:
        _configure_swagger(app)

    # Middleware
    register_error_handlers(app)
    register_rate_limit_handler(app)
    register_request_id(app)
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

    # Sentry OPT-IN: no-op sem SENTRY_DSN — dev/CI nunca quebram sem segredo
    _init_sentry(config_name)

    logger.info(
        "app_created: env=%s, cors=%s",
        config_name or os.environ.get("FLASK_ENV", "production"),
        config.CORS_ORIGINS,
    )

    return app


def _configure_logging(config: object) -> None:
    """Configura logging estruturado (JSON quando LOG_JSON=true, texto em dev/test)."""
    level = logging.DEBUG if getattr(config, "DEBUG", False) else logging.INFO
    use_json = os.environ.get("LOG_JSON", "").lower() in ("1", "true", "yes")
    if use_json:
        from app.core.logging_config import configure_json_logging
        configure_json_logging(level=level)
    else:
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
    from app.api.v1.admin.routes import admin_bp, client_bp
    from app.api.v1.alerts.routes import alerts_bp
    from app.api.v1.auth.routes import auth_bp
    from app.api.v1.cameras.routes import cameras_bp
    from app.api.v1.counting.routes import counting_bp
    from app.api.v1.dashboard.routes import dashboard_bp
    from app.api.v1.frames.routes import frames_bp
    from app.api.v1.health.routes import health_bp
    from app.api.v1.modules.routes import modules_bp

    # Módulo de Qualidade Industrial (isolado — não afeta módulos existentes)
    from app.api.v1.chat.routes import chat_bp
    from app.api.v1.fueling.routes import fueling_bp
    from app.api.v1.quality.routes import quality_bp
    from app.api.v1.reports.routes import reports_bp
    from app.api.v1.rules.routes import rules_bp
    from app.api.v1.storage.routes import storage_bp
    from app.api.v1.streams.routes import streams_bp
    from app.api.v1.training.routes import training_bp
    from app.api.v1.verification.routes import verification_bp
    from app.api.v1.videos.routes import videos_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(cameras_bp)
    app.register_blueprint(streams_bp)
    app.register_blueprint(videos_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(storage_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(rules_bp)
    app.register_blueprint(modules_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(frames_bp)
    app.register_blueprint(counting_bp)
    app.register_blueprint(verification_bp)
    app.register_blueprint(quality_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(fueling_bp)

    from app.api.v1.edge.routes import edge_bp
    app.register_blueprint(edge_bp)

    from app.api.v1.operations.routes import operations_bp
    app.register_blueprint(operations_bp)

    from app.api.v1.scenarios.routes import scenarios_bp
    app.register_blueprint(scenarios_bp)

    from app.api.v1.models.routes import models_rollout_bp
    app.register_blueprint(models_rollout_bp)

    from app.api.v1.branding.routes import branding_bp
    app.register_blueprint(branding_bp)

    from app.api.v1.events.routes import events_bp
    app.register_blueprint(events_bp)

    # A4/A5: edge infra + notification + flywheel (migrations 055-059)
    from app.api.v1.edge_events.routes import edge_events_bp
    app.register_blueprint(edge_events_bp)
    from app.api.v1.edge_commands.routes import edge_commands_bp
    app.register_blueprint(edge_commands_bp)
    from app.api.v1.site_gateways.routes import site_gateways_bp
    app.register_blueprint(site_gateways_bp)
    from app.api.v1.notifications.routes import notifications_bp
    app.register_blueprint(notifications_bp)
    from app.api.v1.feedback.routes import feedback_bp
    app.register_blueprint(feedback_bp)

    from app.api.v1.retention.routes import retention_bp
    app.register_blueprint(retention_bp)

    # Admin isolado — erro aqui não derruba o restante da aplicação
    try:
        app.register_blueprint(admin_bp)
        app.register_blueprint(client_bp)
        from app.api.v1.admin.routes_versions import admin_versions_bp
        app.register_blueprint(admin_versions_bp)
        # Vídeos demo para modo demonstração (superadmin only)
        from app.api.v1.admin.demo_videos_routes import demo_videos_bp
        app.register_blueprint(demo_videos_bp)
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).error("admin_blueprint_load_failed: %s", exc)


def _configure_swagger(app: Flask) -> None:
    """Configura Swagger UI em /api/v1/docs (no-op se flasgger não instalado)."""
    if not _HAS_FLASGGER:
        logging.getLogger(__name__).info("swagger: flasgger not installed, UI disabled")
        return
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/api/v1/apispec.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/api/v1/docs",
    }
    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "Recognition API",
            "description": (
                "Sistema de monitoramento de EPIs via câmeras CCTV com detecção YOLOv8. "
                "Autenticação: Bearer token JWT via POST /api/auth/login."
            ),
            "version": "2.0.0",
            "contact": {"email": "admin@epimonitor.com"},
        },
        "basePath": "/",
        "schemes": ["https", "http"],
        "securityDefinitions": {
            "Bearer": {
                "type": "apiKey",
                "name": "Authorization",
                "in": "header",
                "description": "JWT token. Formato: Bearer <token>",
            }
        },
        "security": [{"Bearer": []}],
        "consumes": ["application/json"],
        "produces": ["application/json"],
        "tags": [
            {"name": "auth", "description": "Autenticação JWT"},
            {"name": "cameras", "description": "Câmeras IP e streaming HLS"},
            {"name": "videos", "description": "Upload e processamento de vídeos de treino"},
            {"name": "training", "description": "Frames, anotações, jobs e modelos"},
            {"name": "storage", "description": "Health check do storage R2"},
            {"name": "health", "description": "Health checks do sistema"},
            {"name": "dashboard", "description": "KPIs e relatórios"},
        ],
    }
    _Swagger(app, config=swagger_config, template=swagger_template)


def _register_jwt_error_handlers(jwt_manager: object) -> None:
    """Normaliza erros do Flask-JWT-Extended para o formato padrão da API."""
    from flask_jwt_extended import JWTManager
    j: JWTManager = jwt_manager  # type: ignore[assignment]

    @j.expired_token_loader
    def expired_token(_header: dict, _payload: dict):
        msg = "Token expirado. Faça login novamente."
        return jsonify({"status": "error", "data": {"error": msg}}), 401

    @j.unauthorized_loader
    def missing_token(reason: str):
        return jsonify({"status": "error", "data": {"error": f"Não autorizado: {reason}"}}), 401

    @j.invalid_token_loader
    def invalid_token(reason: str):
        return jsonify({"status": "error", "data": {"error": f"Token inválido: {reason}"}}), 422

    @j.revoked_token_loader
    def revoked_token(_header: dict, _payload: dict):
        msg = "Token revogado. Faça login novamente."
        return jsonify({"status": "error", "data": {"error": msg}}), 401


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


def _init_sentry(config_name: str | None = None) -> None:
    """Inicializa Sentry SDK apenas se SENTRY_DSN estiver configurado (OPT-IN).

    Sem DSN → no-op total; app nunca quebra em dev/CI sem o segredo.
    send_default_pii=False garante C-05 (sem PII no Sentry).
    """
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return
    try:
        import sentry_sdk  # noqa: PLC0415

        sentry_sdk.init(
            dsn=dsn,
            environment=config_name or os.environ.get("FLASK_ENV", "production"),
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            send_default_pii=False,
        )
        logging.getLogger(__name__).info(
            "sentry_initialized: env=%s",
            config_name or os.environ.get("FLASK_ENV", "production"),
        )
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("sentry_init_failed: %s", exc)


def _auto_version_on_deploy() -> None:
    """Dispara auto-versionamento Railway no startup — nunca bloqueia nem levanta."""
    try:
        from app.core.auto_version import auto_create_version_on_deploy
        auto_create_version_on_deploy()
    except Exception as exc:
        logging.getLogger(__name__).warning("auto_version_on_deploy_failed: %s", exc)
