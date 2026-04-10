#!/bin/bash
# ============================================================================
# EPI Monitor — Camera Gateway Local Runner
#
# Roda o gateway localmente na mesma rede das cameras.
# O gateway conecta ao Redis do Railway e recebe comandos de stream.
#
# Requisitos:
#   - Python 3.11+
#   - FFmpeg instalado (brew install ffmpeg / apt install ffmpeg)
#   - Redis URL do Railway (copie do dashboard Railway)
#
# Uso:
#   export REDIS_URL="redis://default:SENHA@HOST:PORT"
#   ./run-local.sh
# ============================================================================

set -e

if [ -z "$REDIS_URL" ]; then
    echo "ERRO: Defina REDIS_URL com a URL do Redis Railway"
    echo ""
    echo "  export REDIS_URL=\"redis://default:SENHA@HOST:PORT\""
    echo "  ./run-local.sh"
    echo ""
    echo "Copie a REDIS_URL do dashboard Railway > Variables"
    exit 1
fi

# Verificar FFmpeg
if ! command -v ffmpeg &>/dev/null; then
    echo "ERRO: FFmpeg nao encontrado. Instale com:"
    echo "  macOS: brew install ffmpeg"
    echo "  Linux: sudo apt install ffmpeg"
    exit 1
fi

cd "$(dirname "$0")"

# Instalar dependencias
if [ ! -d "venv" ]; then
    echo "Criando ambiente virtual..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

# Configurar variaveis
export GATEWAY_ID="${GATEWAY_ID:-gateway-local}"
export PORT="${PORT:-8080}"
export HLS_SEGMENT_TIME="${HLS_SEGMENT_TIME:-2}"
export HLS_LIST_SIZE="${HLS_LIST_SIZE:-3}"
export GATEWAY_HEALTH_TTL="${GATEWAY_HEALTH_TTL:-60}"
export GATEWAY_HEALTH_INTERVAL="${GATEWAY_HEALTH_INTERVAL:-20}"

echo ""
echo "=== EPI Camera Gateway (Local) ==="
echo "  Redis:    ${REDIS_URL:0:30}..."
echo "  Gateway:  $GATEWAY_ID"
echo "  Port:     $PORT"
echo "  FFmpeg:   $(ffmpeg -version 2>&1 | head -1)"
echo ""
echo "Aguardando comandos de stream via Redis..."
echo ""

python3 -m gateway.main
