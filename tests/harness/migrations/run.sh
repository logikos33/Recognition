#!/usr/bin/env bash
# Harness de migrations — Fase D1.  Um comando para rodar tudo localmente.
# Uso: bash tests/harness/migrations/run.sh
#
# O que faz:
#   1. Sobe Postgres 15-alpine efêmero (porta 55432, tmpfs — zero persistência).
#   2. Aguarda pg_isready.
#   3. Roda runner.py --pass 1 (aplica 54 migrations num banco limpo).
#   4. Roda runner.py --pass 2 (idempotência — a 2ª passada deve sair com código 0).
#   5. Roda pytest (asserts de schema).
#   6. Derruba o container (trap garante cleanup mesmo em falha).
#
# Pré-requisito: Docker em execução, Python 3.11+, pip.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/tests/harness/migrations/docker-compose.harness.yml"
export HARNESS_DATABASE_URL="postgresql://harness:harness@localhost:55432/recognition_harness"

cd "$REPO_ROOT"

cleanup() {
    echo "[harness] Derrubando container..."
    docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

echo "[harness] Subindo Postgres efêmero..."
docker compose -f "$COMPOSE_FILE" up -d

echo "[harness] Aguardando pg_isready..."
for i in $(seq 1 30); do
    docker compose -f "$COMPOSE_FILE" exec -T postgres \
        pg_isready -U harness -d recognition_harness -q && break
    sleep 1
done

HARNESS_VENV="$REPO_ROOT/tests/harness/migrations/.venv"
echo "[harness] Preparando venv..."
[ -d "$HARNESS_VENV" ] || python3 -m venv "$HARNESS_VENV"
"$HARNESS_VENV/bin/pip" install -q -r tests/harness/migrations/requirements.txt

PYTHON="$HARNESS_VENV/bin/python"
PYTEST="$HARNESS_VENV/bin/pytest"

echo "[harness] === Passada 1 (banco limpo) ==="
"$PYTHON" tests/harness/migrations/runner.py --pass 1

echo "[harness] === Passada 2 (idempotência) ==="
"$PYTHON" tests/harness/migrations/runner.py --pass 2

echo "[harness] === pytest ==="
"$PYTEST" tests/harness/migrations/ -v

echo "[harness] ✅ Tudo verde."
