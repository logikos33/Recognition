#!/bin/bash
# Teste do próprio smoke: prova que ele reprova o que deve reprovar.
#
# Existe por causa de um defeito real (#222): a versão anterior comparava a
# resposta SEM token contra a resposta COM token, e por isso
#
#     sistema saudável       -> ❌ REPROVADO
#     autenticação quebrada  -> ✅ APROVADO — pode fazer merge
#
# Um gate que passa justamente quando a autenticação está quebrada é pior que
# gate nenhum. Este teste falha se alguém reintroduzir a inversão.
#
# Uso: bash scripts/tests/test_smoke_test.sh
set -u
AQUI="$(cd "$(dirname "$0")" && pwd)"
SMOKE="$AQUI/../smoke_test.sh"
PORTA="${FAKE_API_PORT:-8099}"
BASE="http://127.0.0.1:$PORTA"
FALHAS=0

FAKE_API_TTL=45 python3 "$AQUI/_fake_api_smoke.py" >/dev/null 2>&1 &
FAKE_PID=$!
trap 'kill $FAKE_PID 2>/dev/null' EXIT

for _ in $(seq 1 25); do
  curl -s -o /dev/null --max-time 1 "$BASE/health" && break
  sleep 0.2
done

espera() {  # espera <descrição> <exit esperado> <comando...>
  local desc="$1" esperado="$2"; shift 2
  "$@" >/dev/null 2>&1
  local real=$?
  if [ "$real" = "$esperado" ]; then
    echo "  ✅ $desc (exit=$real)"
  else
    echo "  ❌ $desc — exit=$real, esperado=$esperado"; FALHAS=$((FALHAS+1))
  fi
}

echo "=== teste do smoke_test.sh ==="
espera "sistema saudável APROVA" 0 \
  env SMOKE_EMAIL=x@y.z SMOKE_PASSWORD=senha-certa bash "$SMOKE" "$BASE"
espera "autenticação quebrada REPROVA" 1 \
  env SMOKE_EMAIL=x@y.z SMOKE_PASSWORD=senha-ERRADA bash "$SMOKE" "$BASE"
espera "sem credencial no ambiente REPROVA" 1 \
  env -u SMOKE_EMAIL -u SMOKE_PASSWORD bash "$SMOKE" "$BASE"

echo ""
[ "$FALHAS" = "0" ] && { echo "✅ smoke_test.sh está honesto"; exit 0; } || { echo "❌ $FALHAS falha(s)"; exit 1; }
