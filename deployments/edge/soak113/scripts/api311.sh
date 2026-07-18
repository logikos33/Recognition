#!/usr/bin/env bash
set -uo pipefail
export MAMBA_ROOT_PREFIX=~/soak113/micromamba
MM=~/soak113/bin/micromamba
echo "[$(date +%T)] create api env python=3.11"
$MM create -y -r $MAMBA_ROOT_PREFIX -n api -c conda-forge python=3.11 pip 2>&1 | tail -4
PY=$MAMBA_ROOT_PREFIX/envs/api/bin/python
echo "[$(date +%T)] $($PY --version)"
echo "[$(date +%T)] pip install requirements/api.txt"
$PY -m pip install -q -r ~/soak113/recognition/requirements/api.txt 2>&1 | tail -8
$PY -c "import flask,gevent,psycopg2,bcrypt,redis,jwt,pydantic,boto3,structlog,geventwebsocket; print('API311_DEPS_OK')" 2>&1
echo "[$(date +%T)] DONE_API311"
