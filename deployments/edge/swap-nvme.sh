#!/usr/bin/env bash
# swap-nvme.sh — swap grande em NVMe para o edge Jetson (task-113).
#
# POR QUÊ: memória unificada + stack co-residente = risco de OOM. Uma válvula de
# swap em NVMe dá ao kernel para onde mandar páginas FRIAS (sem thrashing das
# páginas QUENTES da inferência, graças a swappiness baixo), evitando que o
# OOM-killer escolha o pipeline. zram-only NÃO serve para alocações grandes
# (consome a própria RAM que queremos poupar) — ver REGRAS §FASE 1.
#
# Fonte: jetson-ai-lab RAM Optimization; NVIDIA fóruns (swapfile NVMe no Orin).
# EXIGE SUDO. Idempotente. Rodar no box (pandora), NVMe é o disco raiz (116G).
set -euo pipefail

SWAPFILE="${SWAPFILE:-/var/swap/recognition.swap}"
SWAPSIZE_GB="${SWAPSIZE_GB:-16}"

if [[ $EUID -ne 0 ]]; then echo "ERRO: rode com sudo."; exit 1; fi

echo "==> 1. Desabilitar zram grande (nvzramconfig) — evita zram-only em alocação grande"
# Mantém o serviço no disco, apenas para de subir zram gigante no boot.
if systemctl list-unit-files | grep -q '^nvzramconfig'; then
  systemctl disable --now nvzramconfig 2>/dev/null || true
  echo "    nvzramconfig desabilitado (swap real vem do NVMe abaixo)."
else
  echo "    nvzramconfig ausente — ok."
fi

echo "==> 2. Criar swapfile de ${SWAPSIZE_GB}G em NVMe (${SWAPFILE})"
if swapon --show=NAME --noheadings | grep -qx "$SWAPFILE"; then
  echo "    já ativo — nada a fazer."
else
  mkdir -p "$(dirname "$SWAPFILE")"
  if [[ ! -f "$SWAPFILE" ]]; then
    # fallocate pode falhar em alguns FS; fallback para dd.
    fallocate -l "${SWAPSIZE_GB}G" "$SWAPFILE" 2>/dev/null \
      || dd if=/dev/zero of="$SWAPFILE" bs=1M count=$((SWAPSIZE_GB*1024)) status=progress
  fi
  chmod 600 "$SWAPFILE"
  mkswap "$SWAPFILE" >/dev/null
  swapon "$SWAPFILE"
  echo "    swap ativo."
fi

echo "==> 3. Persistir no /etc/fstab (sobrevive a reboot)"
if ! grep -qs "$SWAPFILE" /etc/fstab; then
  echo "$SWAPFILE none swap sw 0 0" >> /etc/fstab
  echo "    linha adicionada ao fstab."
else
  echo "    fstab já contém — ok."
fi

echo "==> 4. swappiness=10 (prioriza RAM/inferência; swap só para páginas frias)"
sysctl -w vm.swappiness=10 >/dev/null

echo "==> Estado final:"
swapon --show
echo "vm.swappiness = $(cat /proc/sys/vm/swappiness)"
echo "OK. (persistência de swappiness vem do sysctl-edge.conf)"
