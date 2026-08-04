#!/usr/bin/env python3
"""
EPI Monitor V2 — Inicialização Railway.
SERVICE_TYPE=api               → Flask API (padrão)
SERVICE_TYPE=worker            → Celery Worker (todas as filas)
SERVICE_TYPE=celery-worker     → Alias para worker
SERVICE_TYPE=beat              → Celery Beat (scheduler — RÉPLICA ÚNICA)
SERVICE_TYPE=pre-annotation    → Pre-Annotation Service (DINO+SAM)
SERVICE_TYPE=landing-page      → Landing page estática (Astro)

LIÇÕES V1:
- Verifica módulo antes de passar ao gunicorn (evita api_server_full)
- postgres:// → postgresql:// automático
- Migrations idempotentes (IF NOT EXISTS)
- Admin criado idempotentemente
- Worker selection: GeventWebSocketWorker (preferred, supports WebSocket) → sync (fallback)
"""
import os, sys, logging, importlib.util

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
    """Aplica infra/migrations/*.sql.

    Delega para infra/migrations/runner_core.py (módulo único compartilhado com o
    harness — ver PEND em tests/harness/migrations/README.md). Por padrão continua
    usando o loop LEGADO, byte-a-byte igual ao que este arquivo fazia antes desta
    refatoração: reexecuta tudo a cada boot, sem tabela de controle, tolera "already
    exists"/"duplicate" como sucesso, loga falha real e CONTINUA o boot (nunca aborta).

    MIGRATIONS_LEDGER_CUTOVER=1 troca para o runner novo (ledger + advisory xact lock,
    aborta em erro real). Flag TRANSITÓRIA — o loop legado só é removido depois do
    backfill (infra/migrations/backfill_schema_migrations.py) rodar em produção e um
    humano confirmar (gate humano, passo 3.5 do mutirão). NÃO ligar sem backfill antes:
    um banco já migrado pelo loop antigo, exposto ao runner novo sem backfill, tentaria
    reaplicar 50+ SQLs do zero.
    """
    migrations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'infra', 'migrations')
    sys.path.insert(0, migrations_dir)
    import runner_core  # infra/migrations/runner_core.py
    return runner_core.run_migrations(DB_URL, migrations_dir=migrations_dir, log=log)


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
        email    = os.environ.get('ADMIN_EMAIL', 'admin@epimonitor.com')
        password = os.environ.get('ADMIN_PASSWORD')
        name     = os.environ.get('ADMIN_NAME',  'Administrador')
        if not password:
            log.warning("ADMIN_PASSWORD não definida — admin padrão não criado. Defina a variável no Railway.")
            conn.close()
            return
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
            log.info(f"✅ Admin criado: {email}")
        conn.close()
    except Exception as e:
        log.warning(f"Admin: {e}")



def _resolve_api_dir():
    """Localiza o diretório que contém o pacote `app` nos dois layouts reais:
    - checkout monorepo (build GitHub / dev local): <repo>/services/api/app
    - imagem Dockerfile.worker: services/api/ copiado para a raiz → <raiz>/app
    Detecção por presença do pacote, não por convenção — None se nenhum existir."""
    base = os.path.dirname(os.path.abspath(__file__))
    for d in (os.path.join(base, 'services', 'api'), base):
        if os.path.isdir(os.path.join(d, 'app')):
            return d
    return None

def start_api():
    log.info(f"=== API V2 na porta {PORT} ===")

    # O start command da API já faz `cd services/api`, mas garantir o sys.path
    # aqui torna o boot independente do cwd do start command.
    api_dir = _resolve_api_dir()
    if api_dir:
        sys.path.insert(0, api_dir)
        os.environ['PYTHONPATH'] = api_dir + ':' + os.environ.get('PYTHONPATH', '')

    # Verificar módulo da API (app:create_app()). V1 (api.app:app) foi absorvido
    # pelo monolito em ADR-0014 e não existe mais no repo — tentar importá-lo
    # como fallback só adiava um sys.exit(1) que já ia acontecer, sugerindo uma
    # rota viva que está morta há mais de um ano. Falha imediata e alto.
    module_str = 'app:create_app()'
    spec = importlib.util.find_spec('app')
    if spec is None:
        log.error("❌ Módulo de API 'app' não encontrado — verifique PYTHONPATH/diretório de trabalho")
        sys.exit(1)
    log.info(f"✅ Módulo: {module_str}")

    # SEM fallback para 'sync': GeventWebSocketWorker é o único worker que
    # cumpre o contrato de WebSocket deste serviço. gevent ausente = boot
    # falha aqui, alto e cedo — nunca sobe silenciosamente em 'sync' (que
    # devolve /health 200 mas mata o SocketIO; ver docs/runbooks/SINAIS_DEGRADACAO.md).
    import gevent  # noqa: F401
    from geventwebsocket.gunicorn.workers import GeventWebSocketWorker  # noqa: F401
    wclass = 'geventwebsocket.gunicorn.workers.GeventWebSocketWorker'
    workers = '1'
    log.info("Worker: GeventWebSocketWorker (with WebSocket support)")

    os.execvp('gunicorn', [
        'gunicorn', '--worker-class', wclass, '-w', workers,
        '--bind', f'0.0.0.0:{PORT}',
        '--timeout', '120', '--keep-alive', '5',
        # 500 req ≈ 40 s a ~12,5 req/s (25 câmeras × ~0,5 segmento/s) — reciclava
        # o worker e derrubava todo SocketIO a cada ~40 s. 100_000 ≈ 2,2 h nesse
        # mesmo regime: mantém a contenção de vazamento sem matar o WebSocket.
        # Reavaliar com ru_maxrss da rota /api/v1/admin/introspection após
        # medição em produção.
        '--max-requests', '100000', '--max-requests-jitter', '10000',
        '--log-level', 'info',
        '--access-logfile', '-', '--error-logfile', '-',
        '--chdir', api_dir or '.',
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

    # COOP/COEP headers required for SharedArrayBuffer (ONNX Runtime Web)
    @app.after_request
    def add_isolation_headers(response):
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
        response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
        return response

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

    # Instalar requirements do pre-annotation-service (torch, groundingdino, etc.)
    # Necessário porque o Dockerfile base instala apenas requirements/api.txt
    import subprocess as _sp
    req_file = os.path.join(service_dir, 'requirements.txt')
    log.info(f"  req_file={req_file} exists={os.path.exists(req_file)}")
    if os.path.exists(req_file):
        log.info("=== Instalando deps do pre-annotation-service (torch, groundingdino) ===")
        result = _sp.run(
            [sys.executable, '-m', 'pip', 'install', '-r', req_file, '--no-warn-script-location'],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode == 0:
            log.info("✅ Deps instaladas com sucesso")
        else:
            log.error(f"❌ Pip install falhou: {result.stderr[-500:]}")
    else:
        log.warning(f"⚠️ requirements.txt não encontrado em {req_file}")

    # Fix frames: reset pre_annotated_at vazio + backfill quality_status
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        # 1. Reset frames pré-anotados com resultado vazio
        cur.execute("""
            UPDATE training_frames
            SET pre_annotated_at = NULL
            WHERE pre_annotated_at IS NOT NULL
            AND (pre_annotations IS NULL OR pre_annotations = '[]'::jsonb)
        """)
        reset_count = cur.rowcount
        # 2. Backfill quality_status para frames sem status (fix get_approved_by_video)
        cur.execute("""
            UPDATE training_frames
            SET quality_status = 'approved'
            WHERE quality_status IS NULL OR quality_status = 'pending'
        """)
        quality_count = cur.rowcount
        conn.commit()
        conn.close()
        if reset_count > 0:
            log.info(f"✅ Reset {reset_count} frames para re-processamento")
        if quality_count > 0:
            log.info(f"✅ Backfill quality_status: {quality_count} frames → approved")
    except Exception as e:
        log.warning(f"Fix frames: {e}")

    # Adicionar o diretório ao PYTHONPATH
    sys.path.insert(0, service_dir)
    os.environ['PYTHONPATH'] = service_dir + ':' + os.environ.get('PYTHONPATH', '')
    log.info(f"✅ Service dir: {service_dir}")

    # Start gunicorn as subprocess (NOT os.execvp — that kills threads)
    import subprocess as _sp
    import signal as _signal
    proc = _sp.Popen([
        'gunicorn', '-w', '1',
        '--bind', f'0.0.0.0:{PORT}',
        '--timeout', '300',
        '--log-level', 'info',
        '--access-logfile', '-', '--error-logfile', '-',
        '--chdir', service_dir,
        'src.main:app',
    ])

    # Prefetch em background, depois recarrega gunicorn workers
    def _prefetch_and_reload():
        _preannot_prefetch_models()
        # SIGHUP faz gunicorn graceful reload — workers reimportam src.main com torch disponível
        log.info("=== Reloading gunicorn workers (SIGHUP) para carregar modelos ===")
        try:
            import os as _os
            _os.kill(proc.pid, _signal.SIGHUP)
            log.info("✅ Gunicorn reload triggered")
        except Exception as e:
            log.warning(f"Gunicorn reload falhou: {e}")

    t = threading.Thread(target=_prefetch_and_reload, daemon=True)
    t.start()
    log.info("Prefetch + reload started in background")

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

    # O antigo backend/ não existe mais; chdir incondicional para backend/
    # crashava qualquer deploy novo (produção só sobrevive num snapshot antigo).
    api_dir = _resolve_api_dir()
    if api_dir is None:
        log.error("❌ pacote `app` não encontrado (nem services/api/app nem ./app) — layout inesperado")
        sys.exit(1)
    sys.path.insert(0, api_dir)
    os.environ['PYTHONPATH'] = api_dir + ':' + os.environ.get('PYTHONPATH', '')
    os.chdir(api_dir)
    log.info(f"api_dir={api_dir} sys.path[0]={sys.path[0]}")

    # Health real (item 2.3): era {"status":"ok"} hardcoded — respondia 200
    # mesmo com o worker morto/broker inalcançável. Agora checa (1) o broker
    # Redis alcançável e (2) o worker responde a um ping do Celery. Cacheado
    # por _HEALTH_TTL_SECONDS: control.inspect().ping() manda broadcast pelo
    # broker a cada chamada — sem cache, o próprio healthcheck vira carga.
    import json as _json
    import time as _time

    _HEALTH_TTL_SECONDS = 10.0
    _health_cache = {"ok": False, "checked_at": 0.0, "detail": "not checked yet"}

    def _worker_health() -> tuple[bool, str]:
        now = _time.monotonic()
        if now - _health_cache["checked_at"] < _HEALTH_TTL_SECONDS:
            return _health_cache["ok"], _health_cache["detail"]

        try:
            import redis as _redis
            _redis.from_url(REDIS, socket_timeout=2).ping()
        except Exception as e:
            detail = f"broker (redis) inalcançável: {e}"
            _health_cache.update(ok=False, checked_at=now, detail=detail)
            return False, detail

        try:
            from app.infrastructure.queue.celery_app import celery
            pong = celery.control.inspect(timeout=2).ping()
        except Exception as e:
            detail = f"celery inspect falhou: {e}"
            _health_cache.update(ok=False, checked_at=now, detail=detail)
            return False, detail

        ok = bool(pong)
        detail = "ok" if ok else "nenhum worker respondeu ao ping (broker OK, worker não)"
        _health_cache.update(ok=ok, checked_at=now, detail=detail)
        return ok, detail

    class _HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            ok, detail = _worker_health()
            body = _json.dumps(
                {"status": "ok" if ok else "down", "worker": "celery", "detail": detail}
            ).encode()
            self.send_response(200 if ok else 503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_):
            pass  # suppress access logs

    health_server = HTTPServer(('0.0.0.0', int(PORT)), _HealthHandler)
    threading.Thread(target=health_server.serve_forever, daemon=True).start()
    log.info(f"Health server on port {PORT}")

    # Observability collector (WS11) — daemon thread com lock Redis, mantido
    # como thread (não task de beat). O agendamento das tasks seguras roda num
    # serviço beat SEPARADO (SERVICE_TYPE=beat, schedule curado). O worker NÃO
    # usa -B: beat é singleton próprio, e os cleanups destrutivos de quality
    # seguem FORA do schedule (DEFERRED_BEAT_SCHEDULE em celery_app.py).
    # O loop dorme 60s antes do 1º ciclo (pool psycopg2 só nasce pós-fork).
    def _obs_collector():
        try:
            from app.infrastructure.queue.tasks.observability import run_collector_loop
            run_collector_loop()
        except Exception as e:
            log.warning(f"Observability collector morreu: {e}")

    threading.Thread(target=_obs_collector, daemon=True, name='obs-collector').start()
    log.info("Observability collector: thread daemon iniciada (60s + lock Redis)")

    # Iniciar worker programaticamente — sys.path correto é herdado pelos forks.
    # 'reports' e 'quality_cep' incluídas para o worker consumir as tasks
    # agendadas pelo beat (SERVICE_TYPE=beat): compliance (reports), CEP baseline
    # e shift-reports (quality_cep). Seguro: os cleanups destrutivos de quality_cep
    # NÃO são agendados (DEFERRED_BEAT_SCHEDULE) nem despachados em nenhum outro
    # ponto do código — logo nunca chegam a esta fila.
    queues = 'extraction,quality,versioning,inference,training,reports,quality_cep'
    log.info(f"Consumindo filas: {queues}")
    from app.infrastructure.queue.celery_app import celery
    celery.worker_main([
        'worker',
        f'--queues={queues}',
        '--concurrency=2',
        '--loglevel=info',
    ])


def start_celery_beat():
    """Inicia o Celery Beat (scheduler) — DEVE RODAR EM RÉPLICA ÚNICA.

    Agenda apenas o SAFE_BEAT_SCHEDULE (compliance diário, CEP baseline,
    shift-reports e model-drift) — ver celery_app.py. NÃO agenda os cleanups
    destrutivos de R2, o wiser-retry nem o auto-retraining (DEFERRED_BEAT_SCHEDULE).

    ⚠️ Mais de uma réplica = disparo duplicado das tasks. Manter em 1 réplica.
    Serve /health em $PORT para o healthcheck do Railway.
    """
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    log.info("=== Celery Beat (scheduler) ===")
    if not REDIS:
        log.error("REDIS_URL obrigatório para Celery Beat")
        sys.exit(1)

    # O antigo backend/ não existe mais; chdir incondicional para backend/
    # crashava qualquer deploy novo (produção só sobrevive num snapshot antigo).
    api_dir = _resolve_api_dir()
    if api_dir is None:
        log.error("❌ pacote `app` não encontrado (nem services/api/app nem ./app) — layout inesperado")
        sys.exit(1)
    sys.path.insert(0, api_dir)
    os.environ['PYTHONPATH'] = api_dir + ':' + os.environ.get('PYTHONPATH', '')
    os.chdir(api_dir)
    log.info(f"api_dir={api_dir} sys.path[0]={sys.path[0]}")

    # Minimal health server so Railway healthcheck passes
    class _HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'{"status":"ok","service":"celery-beat"}'
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

    from app.infrastructure.queue.celery_app import celery
    log.info("Beat schedule (curado): %s", sorted(celery.conf.beat_schedule.keys()))
    # Estado do PersistentScheduler em /tmp (efêmero; ok para réplica única)
    celery.Beat(loglevel="INFO", schedule="/tmp/celerybeat-schedule").run()


if SERVICE == 'api':
    if not check_db():
        sys.exit(1)
    run_migrations()
    create_admin()
    start_api()
elif SERVICE in ('worker', 'celery-worker'):
    check_db()
    start_celery_worker()
elif SERVICE in ('beat', 'celery-beat'):
    start_celery_beat()
elif SERVICE == 'pre-annotation':
    start_pre_annotation()
elif SERVICE == 'landing-page':
    start_landing_page()
else:
    log.error(f"SERVICE_TYPE inválido: '{SERVICE}' — use 'api', 'worker', 'beat', 'pre-annotation' ou 'landing-page'")
    sys.exit(1)
