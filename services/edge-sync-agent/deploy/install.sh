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
REPO_ROOT="$(cd "$HERE/../../.." && pwd)"
UNIT_NAME="edge-sync-agent"
UPDATER_UNIT="edge-sync-agent-updater"
UNIT_DIR="$HOME/.config/systemd/user"
CONFIG_DIR="$HOME/.config/recognition"
ENV_FILE="$CONFIG_DIR/edge-sync-agent.env"
RECOGNITION_DIR="$HOME/recognition"
CURRENT_SYMLINK="$RECOGNITION_DIR/current"

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

# OTA (ADR-0057 item 10): a unit principal usa %h/recognition/current no
# ExecStart/WorkingDirectory. Num box novo isso ainda não existe — aponta
# pro checkout de onde este install.sh está rodando (o mesmo comportamento
# de path fixo que o PR-D original tinha). O primeiro ciclo real do updater
# (edge-sync-agent-updater.timer) migra sozinho pro layout releases/<ref>/
# de verdade assim que um target_ref for publicado — não precisa de lógica
# de bootstrap especial aqui além de apontar o symlink uma vez.
_bootstrap_current_symlink() {
  local service_dir="$REPO_ROOT/services/edge-sync-agent"
  if [[ -e "$CURRENT_SYMLINK" || -L "$CURRENT_SYMLINK" ]]; then
    echo "$CURRENT_SYMLINK já existe — não sobrescrito (OTA cuida de atualizá-lo)."
    return
  fi
  install -d -m 755 "$RECOGNITION_DIR"
  ln -s "$service_dir" "$CURRENT_SYMLINK"
  echo "criado $CURRENT_SYMLINK -> $service_dir"

  if [[ ! -d "$service_dir/.venv" ]]; then
    echo "criando venv em $service_dir/.venv ..."
    python3 -m venv "$service_dir/.venv"
    "$service_dir/.venv/bin/pip" install -q -r "$service_dir/requirements.txt"
  fi
}

cmd="${1:-install}"

case "$cmd" in
  install)
    _check_not_root
    _check_linger

    install -d -m 755 "$UNIT_DIR" "$CONFIG_DIR" "$CONFIG_DIR/keys"
    install -m 644 "$HERE/edge-sync-agent.service" "$UNIT_DIR/$UNIT_NAME.service"
    install -m 644 "$HERE/edge-sync-agent-updater.service" "$UNIT_DIR/$UPDATER_UNIT.service"
    install -m 644 "$HERE/edge-sync-agent-updater.timer" "$UNIT_DIR/$UPDATER_UNIT.timer"

    if [[ ! -f "$ENV_FILE" ]]; then
      install -m 600 "$HERE/edge-sync-agent.env.example" "$ENV_FILE"
      echo "criado $ENV_FILE (chmod 600) — EDITAR (DEVICE_ID, ENROLLMENT_TOKEN, EVIDENCE_*, RECORDER_*, OTA_SOURCE_REPO) antes de habilitar!"
    else
      echo "$ENV_FILE já existe — não sobrescrito."
    fi

    _bootstrap_current_symlink

    systemctl --user daemon-reload
    echo
    echo "OK. Próximos passos (depois de editar $ENV_FILE — sobretudo OTA_SOURCE_REPO=$REPO_ROOT):"
    echo "  systemctl --user enable --now $UNIT_NAME"
    echo "  systemctl --user enable --now $UPDATER_UNIT.timer   # canal de software (OTA), opcional"
    echo "  systemctl --user status $UNIT_NAME"
    echo "  journalctl --user -u $UNIT_NAME -f"
    ;;

  uninstall)
    _check_not_root
    systemctl --user disable --now "$UNIT_NAME" 2>/dev/null || true
    systemctl --user disable --now "$UPDATER_UNIT.timer" 2>/dev/null || true
    rm -f "$UNIT_DIR/$UNIT_NAME.service" "$UNIT_DIR/$UPDATER_UNIT.service" "$UNIT_DIR/$UPDATER_UNIT.timer"
    systemctl --user daemon-reload
    echo "OK. Units removidas. Config em $CONFIG_DIR e releases em $RECOGNITION_DIR preservados (tem a chave/identidade do device e os releases) — remover manualmente se for descomissionar o device de vez."
    ;;

  status)
    systemctl --user status "$UNIT_NAME" --no-pager || true
    echo
    echo "--- OTA (canal de software) ---"
    systemctl --user status "$UPDATER_UNIT.timer" --no-pager 2>/dev/null || echo "updater timer não instalado/habilitado"
    if [[ -L "$CURRENT_SYMLINK" ]]; then
      echo "current -> $(readlink "$CURRENT_SYMLINK")"
    fi
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
