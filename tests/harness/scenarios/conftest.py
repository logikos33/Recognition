"""
Fixtures do harness D2 (cenários RTSP sintético — task-027).

Isolado de services/api/tests/: sem import Flask direto.
A API é iniciada como subprocesso quando HARNESS_API_URL não está definida.

Ordem de resolução para api_url:
  1. HARNESS_API_URL (env) — API externa já em execução (run.sh ou CI)
  2. Porta padrão (5055) já aberta — run.sh pode ter iniciado antes do pytest
  3. Subprocesso iniciado aqui — uso standalone: pytest tests/harness/scenarios/
"""
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

# Garante que `from helpers.xxx import` funcione em qualquer CWD
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import psycopg2
import psycopg2.extras
import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent.parent.parent  # repo root

_DEFAULT_DB_URL = "postgresql://harness:harness@localhost:55433/recognition_scenarios"
_DEFAULT_API_PORT = 5055
_DEFAULT_API_URL = f"http://localhost:{_DEFAULT_API_PORT}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [HARNESS-D2] %(message)s")
log = logging.getLogger("harness.scenarios")


@pytest.fixture(scope="session")
def db_url() -> str:
    return os.environ.get("HARNESS_SCENARIOS_DATABASE_URL", _DEFAULT_DB_URL)


@pytest.fixture(scope="session")
def db_conn(db_url):  # noqa: N803 — fixture name matches env convention
    """Conexão psycopg2 ao banco harness (migrações já aplicadas pelo runner / run.sh)."""
    if not db_url:
        pytest.fail(
            "HARNESS_SCENARIOS_DATABASE_URL não definida. "
            "Execute via run.sh ou defina a variável."
        )
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def api_url(db_url):  # noqa: N803
    """URL base da API em execução para os cenários."""
    external = os.environ.get("HARNESS_API_URL", "").strip()
    if external:
        _wait_for_api(external, timeout=20)
        yield external
        return

    # Tenta porta padrão (run.sh pode ter iniciado a API antes do pytest)
    try:
        _wait_for_api(_DEFAULT_API_URL, timeout=3)
        yield _DEFAULT_API_URL
        return
    except RuntimeError:
        pass

    # Inicia API como subprocesso (uso standalone — pytest sem run.sh)
    log.info("Iniciando API Flask como subprocesso (porta %d)...", _DEFAULT_API_PORT)
    proc = _start_api_subprocess(db_url)
    try:
        _wait_for_api(_DEFAULT_API_URL, timeout=45)
        log.info("API pronta em %s", _DEFAULT_API_URL)
        yield _DEFAULT_API_URL
    finally:
        log.info("Encerrando subprocesso API (pid=%s)...", proc.pid)
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()


def _start_api_subprocess(db_url: str) -> subprocess.Popen:
    api_dir = str(ROOT / "services" / "api")
    shared_path = str(ROOT / "shared" / "python")
    redis_url = os.environ.get(
        "HARNESS_REDIS_URL",
        os.environ.get("REDIS_URL", "redis://localhost:6380"),
    )
    # Paths passados via env vars (evita quebrar em paths com espaços)
    env = {
        **os.environ,
        "SERVICE_TYPE": "api",
        "DATABASE_URL": db_url,
        "REDIS_URL": redis_url,
        "JWT_SECRET_KEY": "harness-scenarios-secret-key-minimum-32chars!!",
        # PYTHONPATH via env — não inline no -c (evita problema com spaces no path)
        "PYTHONPATH": f"{api_dir}{os.pathsep}{shared_path}{os.pathsep}{os.environ.get('PYTHONPATH', '')}",
        "PORT": str(_DEFAULT_API_PORT),
        "PYTHONUNBUFFERED": "1",
    }
    startup = (
        "from app import create_app; "
        f"app = create_app(); "
        f"app.run(host='0.0.0.0', port={_DEFAULT_API_PORT}, use_reloader=False, debug=False)"
    )
    return subprocess.Popen(
        [sys.executable, "-c", startup],
        env=env,
        cwd=api_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _wait_for_api(url: str, timeout: int = 30) -> None:
    deadline = time.time() + timeout
    last_exc: Exception | None = None
    while time.time() < deadline:
        try:
            resp = requests.get(f"{url}/health", timeout=2)
            if resp.status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
        time.sleep(1)
    raise RuntimeError(
        f"API não respondeu em {timeout}s em {url}/health. Último erro: {last_exc}"
    )
