#!/usr/bin/env python3
"""
EPI Monitor V2 — Inicialização Railway.
SERVICE_TYPE=api               → Flask API (padrão)
SERVICE_TYPE=worker            → Worker FFmpeg/YOLO
SERVICE_TYPE=pre-annotation    → Pre-Annotation Service (DINO+SAM)

LIÇÕES V1:
- Verifica módulo antes de passar ao gunicorn (evita api_server_full)
- postgres:// → postgresql:// automático
- Migrations idempotentes (IF NOT EXISTS)
- Admin criado idempotentemente
- Fallback de worker_class (eventlet → sync)
"""
import os, sys, glob, logging, importlib.util

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s [INIT] %(levelname)s %(message)s')
log = logging.getLogger(__name__)

SERVICE = os.environ.get('SERVICE_TYPE', 'api')
PORT    = os.environ.get('PORT', '8080')
DB_URL  = os.environ.get('DATABASE_URL', '')
REDIS   = os.environ.get('REDIS_URL', '')

# LIÇÃO V1: Railway usa postgres:// — corrigir automaticamente
if DB_URL.startswith('postgres://'):
    DB_URL = DB_URL.replace('postgres://', 'postgresql://', 1)
    os.environ['DATABASE_URL'] = DB_URL

log.info("=" * 50)
log.info(f"EPI Monitor V2 | SERVICE={SERVICE} | PORT={PORT}")
log.info(f"DB={'OK' if DB_URL else 'AUSENTE'} | REDIS={'OK' if REDIS else 'ausente'}")
log.info("=" * 50)


def check_db() -> bool:
    if not DB_URL:
        log.error("DATABASE_URL não definida")
        return False
    try:
        import psycopg2
        c = psycopg2.connect(DB_URL, connect_timeout=15)
        c.cursor().execute("SELECT 1")
        c.close()
        log.info("✅ Banco OK")
        return True
    except Exception as e:
        log.error(f"Banco: {e}")
        return False


def run_migrations():
    log.info("=== Migrations ===")
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        # Try V2 migrations first, fallback to V1
        migration_dirs = [
            'backend/app/infrastructure/database/migrations/*.sql',
            'migrations/*.sql',
        ]
        sql_files = []
        for pattern in migration_dirs:
            sql_files = sorted(glob.glob(pattern))
            if sql_files:
                log.info(f"  Migrations from: {pattern}")
                break
        for f in sql_files:
            log.info(f"  {f}...")
            try:
                cur.execute(open(f).read())
                conn.commit()
                log.info(f"  ✅")
            except Exception as e:
                conn.rollback()
                err = str(e).lower()
                if 'already exists' in err or 'duplicate' in err:
                    log.info(f"  ⚠️  já existe (OK — redeploy normal)")
                else:
                    log.error(f"  ❌ {e}")
        conn.close()
        log.info("✅ Migrations OK")
        return True
    except Exception as e:
        log.error(f"Migrations: {e}")
        return False


def create_admin():
    try:
        import psycopg2, bcrypt
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute(
            "SELECT EXISTS(SELECT FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name='users')"
        )
        if not cur.fetchone()[0]:
            conn.close()
            return
        email    = os.environ.get('ADMIN_EMAIL',    'admin@epimonitor.com')
        password = os.environ.get('ADMIN_PASSWORD', 'EpiMonitor@2024!')
        name     = os.environ.get('ADMIN_NAME',     'Administrador')
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            log.info(f"Admin já existe: {email}")
        else:
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            cur.execute(
                "INSERT INTO users (email,password_hash,name,role) VALUES(%s,%s,%s,'admin')",
                (email, hashed, name)
            )
            conn.commit()
            log.info(f"✅ Admin criado: {email} / {password}")
        conn.close()
    except Exception as e:
        log.warning(f"Admin: {e}")


def start_api():
    log.info(f"=== API V2 na porta {PORT} ===")

    # V2: backend/app/__init__.py com create_app()
    # Adicionar backend/ ao PYTHONPATH
    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
    if os.path.exists(backend_dir):
        sys.path.insert(0, backend_dir)
        os.environ['PYTHONPATH'] = backend_dir + ':' + os.environ.get('PYTHONPATH', '')

    # Verificar módulo V2
    module_str = 'app:create_app()'
    spec = importlib.util.find_spec('app')
    if spec is None:
        # Fallback para V1 se V2 não encontrado
        log.warning("V2 não encontrado, tentando V1...")
        module_str = 'api.app:app'
        spec = importlib.util.find_spec('api.app')
        if spec is None:
            log.error("❌ Nenhum módulo de API encontrado (V2 ou V1)")
            sys.exit(1)
    log.info(f"✅ Módulo: {module_str}")

    try:
        import eventlet
        wclass, workers = 'eventlet', '1'
        log.info("Worker: eventlet")
    except ImportError:
        wclass, workers = 'sync', '2'
        log.warning("Worker: sync (fallback)")

    os.execvp('gunicorn', [
        'gunicorn', '--worker-class', wclass, '-w', workers,
        '--bind', f'0.0.0.0:{PORT}',
        '--timeout', '120', '--keep-alive', '5',
        '--log-level', 'info',
        '--access-logfile', '-', '--error-logfile', '-',
        '--chdir', backend_dir if os.path.exists(backend_dir) else '.',
        module_str
    ])


def start_worker():
    log.info("=== Worker ===")
    if not REDIS:
        log.error("REDIS_URL obrigatório para Worker")
        sys.exit(1)
    try:
        import redis as r
        r.from_url(REDIS, socket_timeout=5).ping()
        log.info("✅ Redis OK")
    except Exception as e:
        log.error(f"Redis: {e}")
        sys.exit(1)
    sys.path.insert(0, '.')
    spec = importlib.util.find_spec('worker.worker_server')
    if spec is None:
        log.error("❌ worker/worker_server.py não encontrado")
        sys.exit(1)
    from worker.worker_server import main
    main()


def start_landing_page():
    """Serve a landing page estática via Flask.
    Tenta dist/ pré-build, depois placeholder — /health sempre responde 200.
    """
    log.info(f"=== Landing Page na porta {PORT} ===")
    root = os.path.dirname(os.path.abspath(__file__))

    # Procura dist/ em várias localizações
    candidates = [
        os.path.join(root, 'landing-page', 'dist'),
        os.path.join(os.getcwd(), 'landing-page', 'dist'),
        '/app/landing-page/dist',
    ]
    dist_dir = None
    for path in candidates:
        log.info(f"  checking: {path} — exists={os.path.exists(path)}")
        if os.path.exists(path) and os.path.exists(os.path.join(path, 'index.html')):
            dist_dir = path
            break

    from flask import Flask, send_from_directory, jsonify
    app = Flask(__name__, static_folder=None)

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'has_dist': dist_dir is not None}), 200

    if dist_dir:
        log.info(f"✅ Servindo static: {dist_dir}")

        @app.route('/', defaults={'path': 'index.html'})
        @app.route('/<path:path>')
        def serve_static(path):
            if os.path.exists(os.path.join(dist_dir, path)):
                return send_from_directory(dist_dir, path)
            return send_from_directory(dist_dir, 'index.html')
    else:
        log.warning("dist/ não encontrado — servindo placeholder")
        HTML = (
            '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
            '<title>EPI Monitor</title>'
            '<style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;'
            'display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;}'
            'h1{font-size:2rem;}p{color:#94a3b8;}</style></head>'
            '<body><div><h1>EPI Monitor</h1>'
            '<p>Visao computacional para seguranca industrial</p>'
            '<p style="margin-top:2rem"><a href="https://app.epimonitor.com.br"'
            ' style="color:#f97316;text-decoration:none;font-weight:600">Acessar App</a>'
            '</p></div></body></html>'
        )

        @app.route('/', defaults={'path': ''})
        @app.route('/<path:path>')
        def serve_placeholder(path):
            return HTML, 200, {'Content-Type': 'text/html; charset=utf-8'}

    log.info(f"✅ Flask landing page na porta {PORT}")
    app.run(host='0.0.0.0', port=int(PORT), debug=False)



def start_pre_annotation():
    """Inicia o Pre-Annotation Service (DINO + SAM) a partir do subdiretório."""
    log.info(f"=== Pre-Annotation Service na porta {PORT} ===")
    service_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pre-annotation-service')
    if not os.path.exists(service_dir):
        log.error(f"❌ pre-annotation-service/ não encontrado em {service_dir}")
        sys.exit(1)

    # 1. Instalar pacotes DINO+SAM se não disponíveis
    import subprocess
    for pkg, import_name in [('groundingdino-py', 'groundingdino'), ('segment-anything', 'segment_anything')]:
        try:
            importlib.import_module(import_name)
            log.info(f"✅ {pkg} já instalado")
        except ImportError:
            log.info(f"Instalando {pkg}...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', pkg, '-q'], check=False)

    # 2. Download checkpoints do R2 se necessário
    dino_ckpt = os.environ.get('PREANNOT_DINO_CHECKPOINT', '')
    sam_ckpt = os.environ.get('PREANNOT_SAM_CHECKPOINT', '')
    r2_endpoint = os.environ.get('PREANNOT_R2_ENDPOINT', os.environ.get('R2_ENDPOINT', ''))
    r2_bucket = os.environ.get('PREANNOT_R2_BUCKET', os.environ.get('R2_BUCKET', 'epi-monitor'))
    r2_key = os.environ.get('PREANNOT_R2_KEY', os.environ.get('R2_KEY', ''))
    r2_secret = os.environ.get('PREANNOT_R2_SECRET', os.environ.get('R2_SECRET', ''))
    models_dir = '/tmp/epi-models'
    os.makedirs(models_dir, exist_ok=True)

    if r2_endpoint and r2_key:
        try:
            import boto3
            from botocore.config import Config
            s3 = boto3.client(
                's3',
                endpoint_url=r2_endpoint,
                aws_access_key_id=r2_key,
                aws_secret_access_key=r2_secret,
                config=Config(signature_version='s3v4'),
            )
            for ckpt_key in [dino_ckpt, sam_ckpt]:
                if ckpt_key:
                    local_path = os.path.join(models_dir, os.path.basename(ckpt_key))
                    if not os.path.exists(local_path):
                        log.info(f"Downloading {ckpt_key} from R2...")
                        s3.download_file(r2_bucket, ckpt_key, local_path)
                        log.info(f"✅ Downloaded: {local_path}")
                    else:
                        log.info(f"✅ Cached: {local_path}")
            # Set env vars to local paths for pre-annotation service config
            if dino_ckpt:
                os.environ['PREANNOT_DINO_CHECKPOINT'] = os.path.join(models_dir, os.path.basename(dino_ckpt))
            if sam_ckpt:
                os.environ['PREANNOT_SAM_CHECKPOINT'] = os.path.join(models_dir, os.path.basename(sam_ckpt))
        except Exception as exc:
            log.warning(f"R2 checkpoint download failed: {exc} — running without models")

    # Adicionar o diretório ao PYTHONPATH para que src.main seja encontrado
    sys.path.insert(0, service_dir)
    os.environ['PYTHONPATH'] = service_dir + ':' + os.environ.get('PYTHONPATH', '')
    log.info(f"✅ Service dir: {service_dir}")
    os.execvp('gunicorn', [
        'gunicorn', '-w', '1',
        '--bind', f'0.0.0.0:{PORT}',
        '--timeout', '300',
        '--log-level', 'info',
        '--access-logfile', '-', '--error-logfile', '-',
        '--chdir', service_dir,
        'src.main:app',
    ])


if SERVICE == 'api':
    if not check_db():
        sys.exit(1)
    run_migrations()
    create_admin()
    start_api()
elif SERVICE == 'worker':
    check_db()
    start_worker()
elif SERVICE == 'pre-annotation':
    start_pre_annotation()
elif SERVICE == 'landing-page':
    start_landing_page()
else:
    log.error(f"SERVICE_TYPE inválido: '{SERVICE}' — use 'api', 'worker', 'pre-annotation' ou 'landing-page'")
    sys.exit(1)
