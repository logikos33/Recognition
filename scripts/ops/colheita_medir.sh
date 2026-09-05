#!/bin/bash
# Roda a colheita medindo link (enP8p1s0, o que fala com o gravador) e disco.
IF=enP8p1s0
rx0=$(grep "$IF:" /proc/net/dev | awk "{print \$2}")
tx0=$(grep "$IF:" /proc/net/dev | awk "{print \$10}")
d0=$(df --output=used -k / | tail -1)
t0=$(date +%s)
PATH=$HOME/.local/bin:$PATH "$HOME/colheita-full-0902/.venv/bin/python" "$HOME/colheita-full-0902/colheita_full.py"
rc=$?
t1=$(date +%s)
rx1=$(grep "$IF:" /proc/net/dev | awk "{print \$2}")
tx1=$(grep "$IF:" /proc/net/dev | awk "{print \$10}")
d1=$(df --output=used -k / | tail -1)
dt=$((t1-t0)); [ $dt -eq 0 ] && dt=1
echo "=== MEDIDA DE LINK E DISCO ($IF) ==="
echo "duracao_s=$dt"
awk -v a=$rx0 -v b=$rx1 -v t=$dt "BEGIN{printf \"rx_MB=%.1f  rx_MBps=%.3f\n\",(b-a)/1048576,(b-a)/1048576/t}"
awk -v a=$tx0 -v b=$tx1 -v t=$dt "BEGIN{printf \"tx_MB=%.1f  tx_MBps=%.3f\n\",(b-a)/1048576,(b-a)/1048576/t}"
awk -v a=$d0 -v b=$d1 "BEGIN{printf \"disco_delta_MB=%.1f\n\",(b-a)/1024}"
df -h / | tail -1
exit $rc
