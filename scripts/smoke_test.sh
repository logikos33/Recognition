#!/bin/bash
# Smoke test obrigatório antes de qualquer merge para staging/main
BASE="${1:-http://localhost:5001}"
PASS=0; FAIL=0

check() {
    local label="$1" url="$2" expected="${3:-200}"
    local status=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$url" 2>/dev/null)
    if [ "$status" = "$expected" ]; then echo "  ✅ $label → $status"; PASS=$((PASS+1))
    else echo "  ❌ $label → $status (esperado $expected)"; FAIL=$((FAIL+1)); fi
}

echo "=== Smoke Test: $BASE ==="
check "Health"           "$BASE/health"
check "Streams status"   "$BASE/api/streams/status"

TOKEN=$(curl -s -X POST "$BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@epimonitor.com","password":"EpiMonitor@2024!"}' | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('token',''))" 2>/dev/null)

if [ -n "$TOKEN" ]; then
    check "Auth/me"    "$BASE/api/auth/me"              "$(curl -s -o/dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" $BASE/api/auth/me)"
    check "Cameras"    "$BASE/api/cameras"              "$(curl -s -o/dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" $BASE/api/cameras)"
else
    echo "  ⚠️  Token não obtido — endpoints autenticados não testados"
    FAIL=$((FAIL+1))
fi

echo ""
echo "=== $PASS passou | $FAIL falhou ==="
[ $FAIL -eq 0 ] && echo "✅ APROVADO — pode fazer merge" || { echo "❌ REPROVADO — não fazer merge"; exit 1; }
