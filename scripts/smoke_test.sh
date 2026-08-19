#!/bin/bash
# Smoke test obrigatório antes de qualquer merge para staging/main
#
# Credenciais vêm do AMBIENTE, nunca do arquivo (#222):
#   SMOKE_EMAIL=... SMOKE_PASSWORD=... ./scripts/smoke_test.sh https://host
#
# Antes deste commit o script embutia `admin@epimonitor.com / EpiMonitor@2024!`.
# Credencial default versionada é credencial vazada — e enquanto ela estivesse
# aqui, a rotação do #222 deixaria o próprio smoke quebrado sem ninguém notar.
BASE="${1:-http://localhost:5001}"
PASS=0; FAIL=0

check() {
    local label="$1" url="$2" expected="${3:-200}"
    local status=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$url" 2>/dev/null)
    if [ "$status" = "$expected" ]; then echo "  ✅ $label → $status"; PASS=$((PASS+1))
    else echo "  ❌ $label → $status (esperado $expected)"; FAIL=$((FAIL+1)); fi
}

# Como `check`, mas MANDA o token.
#
# Existe porque a versão anterior chamava `check` passando a resposta
# AUTENTICADA como valor esperado, e o `check` media a resposta SEM token:
#
#     check "Auth/me" "$BASE/api/auth/me" "$(curl -H "Authorization: ..." ...)"
#            \_ mede 401 (sem header)      \_ espera 200 (com header)
#
# O resultado era um teste INVERTIDO: 401≠200 reprovava o sistema saudável, e
# só aprovava quando o token não valia nada (401 dos dois lados). Um gate que
# passa justamente quando a autenticação está quebrada é pior que gate nenhum.
check_auth() {
    local label="$1" url="$2" expected="${3:-200}"
    local status=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 \
        -H "Authorization: Bearer $TOKEN" "$url" 2>/dev/null)
    if [ "$status" = "$expected" ]; then echo "  ✅ $label → $status"; PASS=$((PASS+1))
    else echo "  ❌ $label → $status (esperado $expected)"; FAIL=$((FAIL+1)); fi
}

echo "=== Smoke Test: $BASE ==="
check "Health"           "$BASE/health"
check "Streams status"   "$BASE/api/streams/status"

if [ -z "$SMOKE_EMAIL" ] || [ -z "$SMOKE_PASSWORD" ]; then
    echo "  ❌ SMOKE_EMAIL/SMOKE_PASSWORD não definidos — endpoints autenticados NÃO testados"
    echo "     Rode: SMOKE_EMAIL=... SMOKE_PASSWORD=... $0 $BASE"
    FAIL=$((FAIL+1))
else
    TOKEN=$(curl -s -X POST "$BASE/api/auth/login" \
      -H "Content-Type: application/json" \
      -d "{\"email\":\"$SMOKE_EMAIL\",\"password\":\"$SMOKE_PASSWORD\"}" | \
      python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('token',''))" 2>/dev/null)

    if [ -n "$TOKEN" ]; then
        check_auth "Auth/me"    "$BASE/api/auth/me"
        check_auth "Cameras"    "$BASE/api/cameras"
    else
        echo "  ❌ Login falhou para $SMOKE_EMAIL — endpoints autenticados não testados"
        FAIL=$((FAIL+1))
    fi
fi

echo ""
echo "=== $PASS passou | $FAIL falhou ==="
[ $FAIL -eq 0 ] && echo "✅ APROVADO — pode fazer merge" || { echo "❌ REPROVADO — não fazer merge"; exit 1; }
