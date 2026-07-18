#!/usr/bin/env bash
set -uo pipefail
cd ~/soak113
echo "[$(date +%T)] === venv ==="
python3 -m venv ~/soak113/venv
source ~/soak113/venv/bin/activate
pip install -q --upgrade pip
echo "[$(date +%T)] === pip installs (pgserver, redis, psycopg2-binary, requests) ==="
pip install -q pgserver redis psycopg2-binary requests 2>&1 | tail -5
python -c "import pgserver, redis, psycopg2, requests; print('PYDEPS_OK', pgserver.__version__ if hasattr(pgserver,'__version__') else 'pg')" 2>&1
echo "[$(date +%T)] === redis from source ==="
cd ~/soak113/redis
if [ ! -x src/redis-server ]; then
  ver=7.4.1
  wget -q https://download.redis.io/releases/redis-$ver.tar.gz -O redis.tar.gz && \
  tar xzf redis.tar.gz --strip-components=1 && \
  make -j4 BUILD_TLS=no USE_SYSTEMD=no >build.log 2>&1
fi
[ -x src/redis-server ] && echo "REDIS_BUILT $(src/redis-server --version)" || { echo "REDIS_BUILD_FAILED"; tail -20 build.log; }
echo "[$(date +%T)] === DONE ==="
