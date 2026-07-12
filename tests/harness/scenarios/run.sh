#!/usr/bin/env bash
# Harness D2 — Cenários RTSP sintético (task-027).
# Uso:
#   bash tests/harness/scenarios/run.sh          # subset rápido (sem MediaMTX)
#   bash tests/harness/scenarios/run.sh --full   # inclui MediaMTX (RTSP sintético real)
#
# O que faz:
#   1. Sobe postgres + redis via docker-compose (+ mediamtx se --full).
#   2. Aguarda pg_isready.
#   3. Aplica migrations (runner.py — 2 passadas, C-02).
#   4. Instala deps (venv isolado).
#   5. Inicia API Flask como subprocesso em porta 5055.
#   6. Aguarda /health retornar 200.
#   7. Roda pytest (cenários 1 e 5).
#   8. Teardown garantido via trap (mesmo em falha).
#
# Pré-requisitos: Docker, Python 3.11+

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/tests/harness/scenarios/docker-compose.harness.yml"
MIGRATIONS_RUNNER="$REPO_ROOT/tests/harness/migrations/runner.py"
API_DIR="$REPO_ROOT/services/api"
SHARED_PATH="$REPO_ROOT/shared/python"

FULL=0
for arg in "$@"; do [[ "$arg" == "--full" ]] && FULL=1; done

export HARNESS_SCENARIOS_DATABASE_URL="postgresql://harness:harness@localhost:55433/recognition_scenarios"
export HARNESS_REDIS_URL="redis://localhost:6380"
export HARNESS_API_URL="http://localhost:5055"
# Usado pelo runner.py de migrations
export HARNESS_DATABASE_URL="$HARNESS_SCENARIOS_DATABASE_URL"

API_PID=""

cleanup() {
    echo ""
    echo "[harness-d2] Encerrando..."
    [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
    if [[ $FULL -eq 1 ]]; then
        docker compose --profile full -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true
    else
        docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true
    fi
}
trap cleanup EXIT

# ── 1. Infra ───────────────────────────────────────────────────────────────
echo "[harness-d2] Subindo infra (FULL=$FULL)..."
if [[ $FULL -eq 1 ]]; then
    docker compose --profile full -f "$COMPOSE_FILE" up -d
else
    docker compose -f "$COMPOSE_FILE" up -d
fi

echo "[harness-d2] Aguardando pg_isready..."
for i in $(seq 1 30); do
    docker compose -f "$COMPOSE_FILE" exec -T postgres \
        pg_isready -U harness -d recognition_scenarios -q 2>/dev/null && break
    sleep 1
done

# ── 2. venv do harness ─────────────────────────────────────────────────────
HARNESS_VENV="$REPO_ROOT/tests/harness/scenarios/.venv"
echo "[harness-d2] Preparando venv..."
[ -d "$HARNESS_VENV" ] || python3 -m venv "$HARNESS_VENV"

"$HARNESS_VENV/bin/pip" install -q --upgrade pip
"$HARNESS_VENV/bin/pip" install -q \
    -r "$REPO_ROOT/tests/harness/scenarios/requirements.txt"
"$HARNESS_VENV/bin/pip" install -q \
    -r "$API_DIR/requirements.txt" \
    "$SHARED_PATH/recognition_shared/"

PYTHON="$HARNESS_VENV/bin/python"
PYTEST="$HARNESS_VENV/bin/pytest"

# ── 3. Migrations (2 passadas — C-02) ─────────────────────────────────────
echo "[harness-d2] === Migrations passada 1 (banco limpo) ==="
"$PYTHON" "$MIGRATIONS_RUNNER" --pass 1

echo "[harness-d2] === Migrations passada 2 (idempotência C-02) ==="
"$PYTHON" "$MIGRATIONS_RUNNER" --pass 2

# ── 4. Iniciar API Flask ───────────────────────────────────────────────────
echo "[harness-d2] Iniciando API Flask (porta 5055)..."

# PYTHONPATH em vez de sys.path.insert inline — evita quebra em paths com espaços
SERVICE_TYPE=api \
DATABASE_URL="$HARNESS_SCENARIOS_DATABASE_URL" \
REDIS_URL="$HARNESS_REDIS_URL" \
JWT_SECRET_KEY="harness-scenarios-secret-key-minimum-32chars!!" \
PORT=5055 \
PYTHONPATH="$API_DIR:$SHARED_PATH" \
PYTHONUNBUFFERED=1 \
"$PYTHON" -c "
from app import create_app
app = create_app()
app.run(host='0.0.0.0', port=5055, use_reloader=False, debug=False)
" &
API_PID=$!

echo "[harness-d2] Aguardando API (pid=$API_PID)..."
API_READY=0
for i in $(seq 1 45); do
    "$PYTHON" -c "
import requests, sys
try:
    r = requests.get('http://localhost:5055/health', timeout=2)
    sys.exit(0 if r.status_code == 200 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null && API_READY=1 && break

    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo "[harness-d2] ❌ API morreu prematuramente. Abortando."
        exit 1
    fi
    sleep 1
done

if [[ $API_READY -eq 0 ]]; then
    echo "[harness-d2] ❌ API não respondeu em 45s. Abortando."
    exit 1
fi
echo "[harness-d2] API pronta."

# ── 5. pytest ─────────────────────────────────────────────────────────────
echo "[harness-d2] === pytest (cenários 1 e 5) ==="
cd "$REPO_ROOT"
"$PYTEST" tests/harness/scenarios/ -v --no-header -p no:cacheprovider

echo ""
echo "[harness-d2] ✅ Cenários 1 e 5 verdes."
