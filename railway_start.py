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
    """Serve a landing page estática.
    Tenta build Node.js se dist/ não existir, depois serve com Python HTTP server.
    """
    log.info(f"=== Landing Page na porta {PORT} ===")
    root = os.path.dirname(os.path.abspath(__file__))
    lp_dir = os.path.join(root, 'landing-page')

    if not os.path.exists(lp_dir):
        log.error(f"❌ landing-page/ não encontrado em {lp_dir}")
        sys.exit(1)

    dist_dir = os.path.join(lp_dir, 'dist')

    # Tentar build Astro se dist/ não existir
    if not os.path.exists(dist_dir):
        log.info("dist/ não encontrado — tentando npm build...")
        import subprocess
        try:
            subprocess.run(['npm', 'ci'], cwd=lp_dir, check=True)
            subprocess.run(['npm', 'run', 'build'], cwd=lp_dir, check=True)
            log.info("✅ Astro build OK")
        except Exception as exc:
            log.warning(f"npm build falhou: {exc} — servindo placeholder")

    # Servir dist/ (ou placeholder) com Python HTTP server
    if os.path.exists(dist_dir):
        serve_dir = dist_dir
    else:
        # Placeholder mínimo em memória
        _serve_landing_placeholder(PORT)
        return

    log.info(f"✅ Servindo static: {serve_dir} na porta {PORT}")
    os.chdir(serve_dir)
    os.execvp('python3', ['python3', '-m', 'http.server', PORT, '--bind', '0.0.0.0'])


def _serve_landing_placeholder(port: str):
    """Serve página placeholder quando build não está disponível."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    html = (
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
        '<title>EPI Monitor</title>'
        '<style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;'
        'display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;}'
        'h1{font-size:2rem;margin-bottom:.5rem;}p{color:#94a3b8;}</style></head>'
        '<body><div><h1>EPI Monitor</h1>'
        '<p>Visao computacional para seguranca industrial</p>'
        '<p style="margin-top:2rem"><a href="https://app.epimonitor.com.br"'
        ' style="color:#f97316;text-decoration:none;font-weight:600">Acessar App</a>'
        '</p></div></body></html>'
    ).encode('utf-8')
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html)
        def log_message(self, *_): pass
    log.info(f"✅ Placeholder na porta {port}")
    HTTPServer(('0.0.0.0', int(port)), H).serve_forever()


def start_pre_annotation():
    """Inicia o Pre-Annotation Service (DINO + SAM) a partir do subdiretório."""
    log.info(f"=== Pre-Annotation Service na porta {PORT} ===")
    service_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pre-annotation-service')
    if not os.path.exists(service_dir):
        log.error(f"❌ pre-annotation-service/ não encontrado em {service_dir}")
        sys.exit(1)
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
