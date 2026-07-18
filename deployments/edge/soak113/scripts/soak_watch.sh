#!/usr/bin/env bash
# task-113 soak watcher — snapshots 5min, cold-start T+90m, final report T+240m. Autônomo.
LOG=~/soak113/logs/soak_watch.jsonl
INC=~/soak113/logs/incidents.log
RC=~/soak113/redis/src/redis-cli
T0=$(date +%s)
COLD_AT=${COLD_AT:-5400}      # 90 min
FINAL_AT=${FINAL_AT:-14400}   # 240 min
cold_done=0
units() { systemctl --user list-units 'soak-*' --no-legend --no-pager | awk '{print $1}'; }
snap() {
  local el=$(( $(date +%s) - T0 ))
  local active=$(systemctl --user list-units 'soak-*' --state=active --no-legend --no-pager | wc -l)
  local failed=$(systemctl --user list-units 'soak-*' --state=failed --no-legend --no-pager | wc -l)
  local restarts=0 oom=0
  for u in $(units); do
    r=$(systemctl --user show -p NRestarts --value $u); restarts=$((restarts+r))
    [ "$(systemctl --user show -p Result --value $u)" = "oom-kill" ] && oom=$((oom+1))
  done
  local mem=$(awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}END{print int((t-a)/1024)}' /proc/meminfo)
  local swap=$(awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo)
  local gpu=$(( $(cat /sys/devices/platform/17000000.gpu/load 2>/dev/null||echo 0)/10 ))
  local gt=$(for tz in /sys/devices/virtual/thermal/thermal_zone*; do [ "$(cat $tz/type)" = "GPU-therm" ] && awk '{printf "%.1f",$1/1000}' $tz/temp; done)
  echo "{\"el_s\":$el,\"active\":$active,\"failed\":$failed,\"restarts\":$restarts,\"oom\":$oom,\"mem_used_mb\":$mem,\"swap_used_mb\":$swap,\"gpu_pct\":$gpu,\"gpu_temp\":\"$gt\",\"cold_done\":$cold_done}" >> $LOG
  [ "$failed" -gt 0 ] && echo "$(date -u +%FT%TZ) FAILED_UNITS=$failed" >> $INC
  [ "$oom" -gt 0 ] && echo "$(date -u +%FT%TZ) OOM_KILL detected on $oom units" >> $INC
  [ "$swap" -gt 3000 ] && echo "$(date -u +%FT%TZ) HIGH_SWAP=${swap}MB" >> $INC
}
echo "$(date -u +%FT%TZ) WATCH_START" >> $INC
while true; do
  el=$(( $(date +%s) - T0 ))
  snap
  if [ $cold_done -eq 0 ] && [ $el -ge $COLD_AT ]; then
    echo "$(date -u +%FT%TZ) COLD_START begin (reboot-equivalente: stop+start toda a stack)" >> $INC
    c0=$(date +%s)
    systemctl --user stop 'soak-*'; sleep 5; systemctl --user start soak-postgres soak-redis; sleep 4
    systemctl --user start soak-api soak-producer soak-consumer soak-sampler soak-infer-park soak-infer-qaux soak-infer-qmain soak-infer-epi
    sleep 30
    up=$(systemctl --user list-units 'soak-*' --state=active --no-legend --no-pager | wc -l)
    echo "$(date -u +%FT%TZ) COLD_START done in $(( $(date +%s)-c0 ))s, active=$up/10" >> $INC
    cold_done=1
  fi
  if [ $el -ge $FINAL_AT ]; then
    echo "$(date -u +%FT%TZ) FINAL report" >> $INC
    python3 ~/soak113/scripts/soak_report.py > ~/soak113/logs/SOAK_FINAL.json 2>&1
    echo "DONE $(date -u +%FT%TZ)" > ~/soak113/logs/SOAK_DONE.marker
    # continue logging overnight but marker signals >=4h reached
  fi
  sleep 300
done
