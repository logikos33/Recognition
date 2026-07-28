#!/usr/bin/env bash
# install.sh — instala/remove o edge-sync-agent como serviço systemd --user.
# SEM SUDO por design (docs/edge/REGRAS_PLATAFORMA_JETSON.md §3.4: sudo no box
# exige senha, bloqueado pra execução autônoma; o padrão já provado no soak
# task-113 é systemctl --user + cgroup delegado + Linger=yes). Roda como o
# usuário do serviço (ex.: pandora) — nunca como root.
#
# Uso: ./install.sh install | uninstall | status
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_NAME="edge-sync-agent"
UNIT_DIR="$HOME/.config/systemd/user"
CONFIG_DIR="$HOME/.config/recognition"
ENV_FILE="$CONFIG_DIR/edge-sync-agent.env"

_check_not_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    echo "ERRO: não rode como root/sudo — este serviço é systemctl --user, roda como o usuário de serviço." >&2
    exit 1
  fi
}

_check_linger() {
  local linger
  linger="$(loginctl show-user "$USER" --property=Linger --value 2>/dev/null || echo "unknown")"
  if [[ "$linger" != "yes" ]]; then
    echo "AVISO: linger não está 'yes' para $USER (está: '$linger')."
    echo "       Sem linger, o serviço --user só roda com $USER logado — não sobrevive a reboot sem login."
    echo "       Habilitar (NÃO exige sudo): loginctl enable-linger $USER"
  else
    echo "linger=yes para $USER — ok, sobrevive a reboot sem login."
  fi
}

cmd="${1:-install}"

case "$cmd" in
  install)
    _check_not_root
    _check_linger

    install -d -m 755 "$UNIT_DIR" "$CONFIG_DIR" "$CONFIG_DIR/keys"
    install -m 644 "$HERE/edge-sync-agent.service" "$UNIT_DIR/$UNIT_NAME.service"

    if [[ ! -f "$ENV_FILE" ]]; then
      install -m 600 "$HERE/edge-sync-agent.env.example" "$ENV_FILE"
      echo "criado $ENV_FILE (chmod 600) — EDITAR (DEVICE_ID, ENROLLMENT_TOKEN, EVIDENCE_*, RECORDER_*) antes de habilitar!"
    else
      echo "$ENV_FILE já existe — não sobrescrito."
    fi

    systemctl --user daemon-reload
    echo
    echo "OK. Próximos passos (depois de editar $ENV_FILE):"
    echo "  systemctl --user enable --now $UNIT_NAME"
    echo "  systemctl --user status $UNIT_NAME"
    echo "  journalctl --user -u $UNIT_NAME -f"
    ;;

  uninstall)
    _check_not_root
    systemctl --user disable --now "$UNIT_NAME" 2>/dev/null || true
    rm -f "$UNIT_DIR/$UNIT_NAME.service"
    systemctl --user daemon-reload
    echo "OK. Unit removida. Config em $CONFIG_DIR preservada (tem a chave/identidade do device) — remover manualmente se for descomissionar o device de vez."
    ;;

  status)
    systemctl --user status "$UNIT_NAME" --no-pager || true
    echo
    echo "--- NTP (pré-requisito do RS256: iat/exp) ---"
    timedatectl show --property=NTPSynchronized --value 2>/dev/null \
      && echo "(NTPSynchronized acima — 'yes' esperado; 'no' bloqueia enroll/heartbeat/lease)" \
      || echo "timedatectl indisponível"
    ;;

  *)
    echo "uso: $0 install|uninstall|status" >&2
    exit 1
    ;;
esac
