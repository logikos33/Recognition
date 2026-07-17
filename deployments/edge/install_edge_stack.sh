#!/usr/bin/env bash
# install_edge_stack.sh — instala units + drop-ins + configs da stack co-residente.
# Idempotente. EXIGE SUDO no box. Ajustar os PATHS abaixo ao inventário real
# (reuse-first: aponte para onde o checkout/venv/runners JÁ estão no box).
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "ERRO: rode com sudo."; exit 1; fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEMD_DIR=/etc/systemd/system

echo "==> 1. Diretórios de config/estado"
install -d -m 755 /etc/recognition
install -d -m 755 /var/log/recognition/soak
[[ -f /etc/recognition/edge.env ]] || {
  cp "$HERE/edge.env.example" /etc/recognition/edge.env
  chmod 600 /etc/recognition/edge.env
  echo "   criado /etc/recognition/edge.env — EDITAR (segredos)!"
}

echo "==> 2. Configs de Redis/Postgres (edge)"
install -D -m 644 "$HERE/redis-edge.conf"      /etc/recognition/redis-edge.conf
install -D -m 644 "$HERE/postgresql-edge.conf" /etc/recognition/postgresql-edge.conf
echo "   incluir manualmente:"
echo "     - redis: adicionar 'include /etc/recognition/redis-edge.conf' no redis.conf"
echo "     - postgres: colocar postgresql-edge.conf no conf.d/ do cluster e reload"

echo "==> 3. Drop-ins de budget (Postgres/Redis do pacote)"
install -D -m 644 "$HERE/systemd/postgresql.service.d/10-recognition-edge.conf" \
  "$SYSTEMD_DIR/postgresql.service.d/10-recognition-edge.conf"
install -D -m 644 "$HERE/systemd/redis-server.service.d/10-recognition-edge.conf" \
  "$SYSTEMD_DIR/redis-server.service.d/10-recognition-edge.conf"

echo "==> 4. Units da stack Recognition"
for u in recognition-api.service recognition-edge-sync.service \
         recognition-edge-telemetry.service recognition-deepstream@.service \
         recognition-soak-sampler.service; do
  install -m 644 "$HERE/systemd/$u" "$SYSTEMD_DIR/$u"
done

echo "==> 5. daemon-reload"
systemctl daemon-reload

cat <<'EOF'

OK. Próximos passos (ajuste paths nas units antes se necessário):

  # subir a base
  sudo systemctl enable --now postgresql redis-server
  sudo systemctl enable --now recognition-api recognition-edge-sync recognition-edge-telemetry

  # subir os 3 módulos (4 instâncias) — runners mm/ já existentes no box
  sudo systemctl enable --now recognition-deepstream@epi recognition-deepstream@parking \
       recognition-deepstream@quality-aux recognition-deepstream@quality-main

  # durante o soak
  sudo systemctl enable --now recognition-soak-sampler

  # conferir budget aplicado
  systemctl show recognition-api -p MemoryMax -p MemoryHigh -p OOMScoreAdjust

VERIFICAR: todos com Restart=always e enabled (sobrevivem a reboot). Ver soak_chaos.sh.
EOF
