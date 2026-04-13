#!/usr/bin/env python3
"""
EPI Monitor V2 — Inicialização Railway.
SERVICE_TYPE=api               → Flask API (padrão)
SERVICE_TYPE=worker            → Celery Worker (todas as filas)
SERVICE_TYPE=celery-worker     → Alias para worker
SERVICE_TYPE=pre-annotation    → Pre-Annotation Service (DINO+SAM)
SERVICE_TYPE=landing-page      → Landing page estática (Astro)

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



def _try_build_landing_page(landing_dir: str) -> bool:
    """Tenta compilar a landing page com npm ci + npm run build."""
    import subprocess
    if not os.path.exists(os.path.join(landing_dir, 'package.json')):
        log.warning(f"  package.json não encontrado em {landing_dir}")
        return False
    try:
        log.info("  Building landing page: npm ci...")
        subprocess.run(['npm', 'ci'], cwd=landing_dir, check=True, timeout=120)
        log.info("  Building landing page: npm run build...")
        subprocess.run(['npm', 'run', 'build'], cwd=landing_dir, check=True, timeout=120)
        log.info("  ✅ Landing page build OK")
        return True
    except FileNotFoundError:
        log.warning("  npm não encontrado — Node.js não instalado")
        return False
    except Exception as e:
        log.error(f"  ❌ Build falhou: {e}")
        return False


def start_landing_page():
    """Serve a landing page estática via Flask.
    Tenta dist/ pré-build, depois build on-demand, depois placeholder.
    /health sempre responde 200.
    """
    log.info(f"=== Landing Page na porta {PORT} ===")
    root = os.path.dirname(os.path.abspath(__file__))

    # Procura dist/ em várias localizações
    landing_dir = None
    candidates = [
        os.path.join(root, 'landing-page'),
        os.path.join(os.getcwd(), 'landing-page'),
        '/app/landing-page',
    ]
    for path in candidates:
        dist_path = os.path.join(path, 'dist')
        log.info(f"  checking: {dist_path} — exists={os.path.exists(dist_path)}")
        if os.path.exists(os.path.join(dist_path, 'index.html')):
            landing_dir = path
            break
        elif os.path.exists(os.path.join(path, 'package.json')):
            landing_dir = path

    dist_dir = os.path.join(landing_dir, 'dist') if landing_dir else None
    if dist_dir and not os.path.exists(os.path.join(dist_dir, 'index.html')):
        log.info("  dist/index.html não encontrado — tentando build...")
        if _try_build_landing_page(landing_dir):
            if not os.path.exists(os.path.join(dist_dir, 'index.html')):
                dist_dir = None
        else:
            dist_dir = None
    elif not dist_dir:
        dist_dir = None

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



def _preannot_prefetch_models():
    """Background thread: instala pacotes e baixa checkpoints do R2."""
    import subprocess
    models_dir = '/tmp/epi-models'
    os.makedirs(models_dir, exist_ok=True)

    # 1. Instalar pacotes
    for pkg, import_name in [('groundingdino-py', 'groundingdino'), ('segment-anything', 'segment_anything')]:
        try:
            importlib.util.find_spec(import_name)
        except Exception:
            pass
        log.info(f"[preannot-prefetch] pip install {pkg}...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', pkg, '-q'], check=False)

    # 2. Download checkpoints
    dino_ckpt = os.environ.get('PREANNOT_DINO_CHECKPOINT', '')
    sam_ckpt = os.environ.get('PREANNOT_SAM_CHECKPOINT', '')
    r2_endpoint = os.environ.get('PREANNOT_R2_ENDPOINT', os.environ.get('R2_ENDPOINT', ''))
    r2_bucket = os.environ.get('PREANNOT_R2_BUCKET', os.environ.get('R2_BUCKET', 'epi-monitor'))
    r2_key = os.environ.get('PREANNOT_R2_KEY', os.environ.get('R2_KEY', ''))
    r2_secret = os.environ.get('PREANNOT_R2_SECRET', os.environ.get('R2_SECRET', ''))

    if not (r2_endpoint and r2_key):
        log.warning("[preannot-prefetch] R2 vars not set — skipping download")
        return

    try:
        import boto3
        from botocore.config import Config
        s3 = boto3.client('s3', endpoint_url=r2_endpoint, aws_access_key_id=r2_key,
                          aws_secret_access_key=r2_secret, config=Config(signature_version='s3v4'))
        for ckpt_key in [dino_ckpt, sam_ckpt]:
            if ckpt_key:
                local_path = os.path.join(models_dir, os.path.basename(ckpt_key))
                if not os.path.exists(local_path):
                    log.info(f"[preannot-prefetch] Downloading {ckpt_key}...")
                    s3.download_file(r2_bucket, ckpt_key, local_path)
                    log.info(f"[preannot-prefetch] ✅ {local_path}")
                # Write marker file so gunicorn workers know to reload models
                open(local_path + '.ready', 'w').close()
        log.info("[preannot-prefetch] ✅ All checkpoints ready — next restart will load models")
    except Exception as exc:
        log.warning(f"[preannot-prefetch] Failed: {exc}")


def start_pre_annotation():
    """Inicia o Pre-Annotation Service (DINO + SAM).
    Gunicorn arranca imediatamente; download de checkpoints roda em background.
    """
    import threading
    log.info(f"=== Pre-Annotation Service na porta {PORT} ===")
    service_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pre-annotation-service')
    if not os.path.exists(service_dir):
        log.error(f"❌ pre-annotation-service/ não encontrado em {service_dir}")
        sys.exit(1)

    # Set local checkpoint paths so gunicorn workers pick them up if already cached
    models_dir = '/tmp/epi-models'
    for env_key, ckpt_env in [('PREANNOT_DINO_CHECKPOINT', 'PREANNOT_DINO_CHECKPOINT'),
                               ('PREANNOT_SAM_CHECKPOINT', 'PREANNOT_SAM_CHECKPOINT')]:
        ckpt_key = os.environ.get(env_key, '')
        if ckpt_key:
            local_path = os.path.join(models_dir, os.path.basename(ckpt_key))
            if os.path.exists(local_path):
                os.environ[env_key] = local_path
                log.info(f"✅ Cached checkpoint: {local_path}")

    # Adicionar o diretório ao PYTHONPATH
    sys.path.insert(0, service_dir)
    os.environ['PYTHONPATH'] = service_dir + ':' + os.environ.get('PYTHONPATH', '')
    log.info(f"✅ Service dir: {service_dir}")

    # Start gunicorn as subprocess (NOT os.execvp — that kills threads)
    import subprocess as _sp
    proc = _sp.Popen([
        'gunicorn', '-w', '1',
        '--bind', f'0.0.0.0:{PORT}',
        '--timeout', '300',
        '--log-level', 'info',
        '--access-logfile', '-', '--error-logfile', '-',
        '--chdir', service_dir,
        'src.main:app',
    ])

    # Background prefetch can now run (thread survives subprocess Popen)
    t = threading.Thread(target=_preannot_prefetch_models, daemon=True)
    t.start()
    log.info("Backgr model prefetch started in background")

    sys.exit(proc.wait())


def start_celery_worker():
    """Inicia Celery worker para todas as filas do sistema.

    Filas: extraction, quality, versioning, inference, training.
    Worker é iniciado de forma programática (não como subprocess) para garantir
    que sys.path seja herdado corretamente pelos forked workers.
    Também serve /health em $PORT para o healthcheck do Railway.
    """
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    log.info("=== Celery Worker ===")
    if not REDIS:
        log.error("REDIS_URL obrigatório para Celery Worker")
        sys.exit(1)
    if not DB_URL:
        log.error("DATABASE_URL obrigatório para Celery Worker")
        sys.exit(1)

    backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
    if os.path.exists(backend_dir):
        sys.path.insert(0, backend_dir)
        os.environ['PYTHONPATH'] = backend_dir + ':' + os.environ.get('PYTHONPATH', '')
    os.chdir(backend_dir)
    log.info(f"backend_dir={backend_dir} sys.path[0]={sys.path[0]}")

    # Minimal health server so Railway healthcheck passes
    class _HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'{"status":"ok","worker":"celery"}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_):
            pass  # suppress access logs

    health_server = HTTPServer(('0.0.0.0', int(PORT)), _HealthHandler)
    threading.Thread(target=health_server.serve_forever, daemon=True).start()
    log.info(f"Health server on port {PORT}")

    # Iniciar worker programaticamente — sys.path correto é herdado pelos forks
    queues = 'extraction,quality,versioning,inference,training'
    log.info(f"Consumindo filas: {queues}")
    from app.infrastructure.queue.celery_app import celery
    celery.worker_main([
        'worker',
        f'--queues={queues}',
        '--concurrency=2',
        '--loglevel=info',
    ])


if SERVICE == 'api':
    if not check_db():
        sys.exit(1)
    run_migrations()
    create_admin()
    start_api()
elif SERVICE in ('worker', 'celery-worker'):
    check_db()
    start_celery_worker()
elif SERVICE == 'pre-annotation':
    start_pre_annotation()
elif SERVICE == 'landing-page':
    start_landing_page()
else:
    log.error(f"SERVICE_TYPE inválido: '{SERVICE}' — use 'api', 'worker', 'pre-annotation' ou 'landing-page'")
    sys.exit(1)
