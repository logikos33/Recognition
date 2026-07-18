#!/usr/bin/env bash
set -uo pipefail
cd ~/soak113
echo "[$(date +%T)] installing micromamba (no sudo)"
export MAMBA_ROOT_PREFIX=~/soak113/micromamba
mkdir -p bin
if [ ! -x ~/soak113/bin/micromamba ]; then
  curl -Ls https://micro.mamba.pm/api/micromamba/linux-aarch64/latest | tar -xvj -C ~/soak113 bin/micromamba >/dev/null 2>&1
fi
~/soak113/bin/micromamba --version || { echo "MICROMAMBA_FAIL"; exit 1; }
echo "[$(date +%T)] creating pg env (postgresql from conda-forge)"
~/soak113/bin/micromamba create -y -r $MAMBA_ROOT_PREFIX -n pg -c conda-forge postgresql=16 2>&1 | tail -8
PGBIN=$MAMBA_ROOT_PREFIX/envs/pg/bin
$PGBIN/postgres --version && echo "PG_OK" || echo "PG_FAIL"
echo "[$(date +%T)] DONE"
