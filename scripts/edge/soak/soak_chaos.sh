#!/usr/bin/env bash
# soak_chaos.sh — chaos leve + prova de recuperação automática (task-113 FASE 4).
# Testa que o systemd RESSUSCITA tudo (Restart=always/enabled) sob carga e após
# reboot. Rodar NO BOX, com a stack + carga (soak_load.py) já rodando.
#
# Uso:
#   bash soak_chaos.sh kill-aux      # mata auxiliares, mede recovery
#   bash soak_chaos.sh restart-load  # reinicia serviços sob carga
#   sudo bash soak_chaos.sh reboot   # REBOOT completo (valida enabled) — SUDO
#
# Registra tempos em /var/log/recognition/soak/chaos.log.
set -uo pipefail
LOG=/var/log/recognition/soak/chaos.log
mkdir -p "$(dirname "$LOG")"
ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
say() { echo "$(ts) $*" | tee -a "$LOG"; }

AUX=(recognition-edge-telemetry recognition-soak-sampler recognition-edge-sync)
CORE=(recognition-api recognition-redis recognition-postgres)
DEEPSTREAM=(recognition-deepstream@epi recognition-deepstream@parking \
            recognition-deepstream@quality-aux recognition-deepstream@quality-main)

wait_active() {  # $1=unit  $2=timeout_s → mede segundos até active
  local unit="$1" timeout="${2:-60}" start now
  start=$(date +%s)
  while true; do
    if systemctl is-active --quiet "$unit"; then
      now=$(date +%s); echo $((now - start)); return 0
    fi
    now=$(date +%s); (( now - start > timeout )) && { echo "-1"; return 1; }
    sleep 1
  done
}

case "${1:-}" in
  kill-aux)
    say "CHAOS kill-aux: matando auxiliares (systemd deve ressuscitar)"
    for u in "${AUX[@]}"; do
      pid=$(systemctl show -p MainPID --value "$u" 2>/dev/null || echo 0)
      say "  kill -9 $u (pid=$pid)"; [ "$pid" -gt 0 ] && kill -9 "$pid" 2>/dev/null
    done
    for u in "${AUX[@]}"; do say "  recovery $u: $(wait_active "$u" 60)s"; done
    say "IMPORTANTE: confirmar que o DeepStream NÃO foi tocado (OOMScoreAdjust -900)."
    ;;
  kill-pipeline)
    say "CHAOS kill-pipeline: matando 1 instância DeepStream (deve voltar em RestartSec)"
    u="${2:-recognition-deepstream@epi}"
    pid=$(systemctl show -p MainPID --value "$u"); say "  kill -9 $u (pid=$pid)"
    [ "$pid" -gt 0 ] && kill -9 "$pid" 2>/dev/null
    say "  recovery $u: $(wait_active "$u" 90)s"
    ;;
  restart-load)
    say "CHAOS restart-load: reiniciando core sob carga"
    for u in "${CORE[@]}"; do
      systemctl restart "$u" 2>/dev/null || sudo systemctl restart "$u"
      say "  restart $u -> active em $(wait_active "$u" 60)s"
    done
    ;;
  reboot)
    say "CHAOS reboot: gravando marcador e reiniciando o box (SUDO)."
    say "  Após o boot, rode: bash soak_chaos.sh post-reboot"
    echo "$(ts)" > /var/log/recognition/soak/reboot_marker
    sync; sudo reboot
    ;;
  post-reboot)
    say "POST-REBOOT: verificando que TUDO voltou sozinho (enabled)"
    for u in "${CORE[@]}" "${AUX[@]}" "${DEEPSTREAM[@]}"; do
      st=$(systemctl is-active "$u" 2>/dev/null || echo inactive)
      en=$(systemctl is-enabled "$u" 2>/dev/null || echo disabled)
      say "  $u: active=$st enabled=$en"
    done
    say "Tempo de boot->multi-user: $(systemd-analyze 2>/dev/null | head -1)"
    say "Conferir dmesg por OOM: $(dmesg | grep -ic 'Out of memory' || echo 0) ocorrências"
    ;;
  *)
    echo "uso: $0 {kill-aux|kill-pipeline [unit]|restart-load|reboot|post-reboot}"; exit 1;;
esac
say "chaos '$1' concluído."
