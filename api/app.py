"""
EPI Monitor V2 — Flask Application Factory.

LIÇÃO V1: App factory permite testes isolados e múltiplas instâncias.
Módulo para gunicorn: api.app:app (verificado no railway_start.py)
"""
import os, logging, traceback
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO

logger = logging.getLogger(__name__)
socketio = SocketIO()


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)

    # Configuração via ENV — NUNCA hardcoded
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'dev-change-in-prod')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-flask-change-in-prod')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False

    # Extensions
    CORS(app, origins=os.environ.get('CORS_ORIGINS', '*').split(','))
    JWTManager(app)
    socketio.init_app(app, cors_allowed_origins='*', async_mode='eventlet',
                      logger=False, engineio_logger=False)

    # Blueprints — registrar aqui conforme forem criados
    from api.blueprints.auth import auth_bp
    from api.blueprints.cameras import cameras_bp
    from api.blueprints.streams import streams_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(cameras_bp)
    app.register_blueprint(streams_bp)
    # TODO adicionar conforme implementados:
    # from api.blueprints.training import training_bp
    # from api.blueprints.rules import rules_bp
    # from api.blueprints.dashboard import dashboard_bp

    # Health check (sem JWT — Railway usa para healthcheck)
    @app.route('/health')
    def health():
        from services.shared.database import test_connection
        from services.shared.events import is_redis_available
        db_ok = test_connection()
        return jsonify({
            'status': 'healthy' if db_ok else 'degraded',
            'services': {'database': db_ok, 'redis': is_redis_available()}
        }), 200 if db_ok else 503

    # Security headers (OWASP básico)
    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if os.environ.get('FLASK_ENV') == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    # Handler global — backend NUNCA morre por exceção
    @app.errorhandler(Exception)
    def handle_exception(e):
        logger.error(f"Unhandled: {request.method} {request.path}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': 'Erro interno'}), 500

    # Servir frontend React buildado em produção
    dist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'frontend', 'dist')

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        if path and os.path.exists(os.path.join(dist, path)):
            return send_from_directory(dist, path)
        index = os.path.join(dist, 'index.html')
        if os.path.exists(index):
            return send_from_directory(dist, 'index.html')
        return jsonify({'status': 'API online', 'frontend': 'não buildado — rodar npm build'}), 200

    # Iniciar listener de detecções se Redis disponível
    _init_detection_listener(app)

    return app


def _init_detection_listener(app: Flask):
    from services.shared.events import is_redis_available
    if not is_redis_available():
        logger.info("Redis indisponível — detection listener não iniciado")
        return

    def on_detection(camera_id, detections, timestamp):
        with app.app_context():
            try:
                # TODO: chamar Rules Engine quando implementado
                # from api.blueprints.rules.service import process_detections
                # process_detections(camera_id, detections, timestamp)
                logger.debug(f"Detecção: cam={camera_id} objs={len(detections)}")
            except Exception as e:
                logger.error(f"Detection callback: {e}")

    from api.utils.worker_proxy import start_detection_listener
    start_detection_listener(on_detection)


# Ponto de entrada para gunicorn
app = create_app()
