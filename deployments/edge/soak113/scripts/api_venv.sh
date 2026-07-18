#!/usr/bin/env bash
set -uo pipefail
source ~/soak113/venv/bin/activate
cd ~/soak113/recognition
echo "[$(date +%T)] installing requirements/api.txt"
pip install -q -r requirements/api.txt 2>&1 | tail -12
echo "[$(date +%T)] verify imports"
python -c "import flask, gevent, psycopg2, bcrypt, redis, jwt, pydantic, boto3, structlog; print('API_DEPS_OK')" 2>&1
echo "[$(date +%T)] DONE_APIVENV"
