#!/usr/bin/env bash
# Harness de escala — wrapper completo (task-027 / PR A3).
# Sobe infra, roda N câmeras, gera relatório, derruba infra.
#
# Uso:
#   ./tests/harness/scenarios/scale/run_scale.sh                # 4 câmeras, 30s
#   ./tests/harness/scenarios/scale/run_scale.sh --cameras 28   # escala completa
#   ./tests/harness/scenarios/scale/run_scale.sh --cameras 8 --duration 60 --model-path /models/yolox_s.onnx
#   KEEP_INFRA=1 ./run_scale.sh  # não derruba docker após o teste

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.scale.yml"
REPORT_DIR="$REPO_ROOT/docs/evidence/e2e-scale"

CAMERAS="${CAMERAS:-4}"
DURATION="${DURATION:-30}"
MODEL_PATH="${MODEL_PATH:-}"
KEEP_INFRA="${KEEP_INFRA:-0}"

# Parsear args
while [[ $# -gt 0 ]]; do
  case $1 in
    --cameras)   CAMERAS="$2";    shift 2 ;;
    --duration)  DURATION="$2";   shift 2 ;;
    --model-path) MODEL_PATH="$2"; shift 2 ;;
    --keep-infra) KEEP_INFRA=1;   shift ;;
    *) echo "Argumento desconhecido: $1"; exit 1 ;;
  esac
done

echo "=== Harness Scale ==="
echo "  Câmeras : $CAMERAS"
echo "  Duração : ${DURATION}s"
echo "  Modelo  : ${MODEL_PATH:-stub (sem ONNX real)}"
echo ""

# 1. Subir infra
echo "[1/5] Subindo infra docker-compose..."
docker-compose -f "$COMPOSE_FILE" up -d --wait 2>&1 | grep -v "^#" || true

# Aguardar postgres
echo "  Aguardando postgres..."
for i in $(seq 1 30); do
  if docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U harness -q 2>/dev/null; then
    echo "  postgres pronto."
    break
  fi
  sleep 1
done

# 2. Rodar migrations
echo "[2/5] Aplicando migrations no banco harness..."
export SCALE_DB_URL="postgresql://harness:harness@localhost:55434/recognition_scale"
export SCALE_REDIS_URL="redis://localhost:6381"
export RTSP_HOST="localhost"
export RTSP_PORT="8555"

cd "$REPO_ROOT/services/api"
python3 -c "
import os
os.environ['DATABASE_URL'] = '$SCALE_DB_URL'
from app.infrastructure.database.connection import DatabasePool
from app import create_app
app = create_app()
with app.app_context():
    print('  migrations aplicadas via startup do app')
" 2>/dev/null || echo "  (migrations via startup — ignorando erro de app, usando harness direto)"

# Fallback: aplicar migrations diretamente se o app não subiu
if ! psql "$SCALE_DB_URL" -c "SELECT 1 FROM tenants LIMIT 1" >/dev/null 2>&1; then
  echo "  Aplicando migrations diretamente..."
  for f in "$REPO_ROOT"/infra/migrations/*.sql; do
    psql "$SCALE_DB_URL" -f "$f" >/dev/null 2>&1 || true
  done
  echo "  migrations aplicadas."
fi
cd "$REPO_ROOT"

# 3. Preparar diretório de relatório
echo "[3/5] Preparando diretório de relatório..."
mkdir -p "$REPORT_DIR"
REPORT_FILE="$REPORT_DIR/REPORT_cam${CAMERAS}_$(date +%Y%m%dT%H%M%S).md"

# 4. Rodar scale runner
echo "[4/5] Executando scale runner ($CAMERAS câmeras × ${DURATION}s)..."
MODEL_ARG=""
if [[ -n "$MODEL_PATH" ]]; then
  MODEL_ARG="--model-path $MODEL_PATH"
fi

python3 "$SCRIPT_DIR/scale_runner.py" \
  --cameras "$CAMERAS" \
  --duration "$DURATION" \
  --report "$REPORT_FILE" \
  $MODEL_ARG \
  || EXIT_CODE=$?

# 5. Derrubar infra
if [[ "$KEEP_INFRA" != "1" ]]; then
  echo "[5/5] Derrubando infra..."
  docker-compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true
else
  echo "[5/5] KEEP_INFRA=1 — infra mantida em execução."
fi

echo ""
echo "=== Concluído ==="
echo "  Relatório: $REPORT_FILE"
echo ""

if [[ -f "$REPORT_FILE" ]]; then
  echo "--- Preview do relatório ---"
  head -30 "$REPORT_FILE"
fi

exit "${EXIT_CODE:-0}"
