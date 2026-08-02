#!/usr/bin/env bash
# Dump normalizado de schema (--schema-only) para o diff de idempotência (C-02).
#
# Uso: dump_schema.sh <dsn> <arquivo_de_saida>
#
# Por que normalizar:
#   - "-- Dumped from/by ..." reflete versão do client/servidor, não o schema.
#   - "\restrict <token>" / "\unrestrict <token>" (pg_dump >= 16) é um par de
#     diretivas psql com um token ALEATÓRIO gerado a cada dump — muda sempre,
#     mesmo comparando o MESMO schema duas vezes seguidas. Sem removê-las,
#     todo diff "daria positivo" por ruído, mascarando o sinal real.
# Nenhuma das duas normalizações esconde divergência de schema de verdade —
# só ruído determinístico de metadado do próprio pg_dump.
set -euo pipefail

DSN="${1:?uso: dump_schema.sh <dsn> <arquivo_de_saida>}"
OUT="${2:?uso: dump_schema.sh <dsn> <arquivo_de_saida>}"

pg_dump --schema-only --no-owner --no-privileges --no-tablespaces "$DSN" \
  | grep -v -E '^-- Dumped (from|by) ' \
  | grep -v -E '^\\(un)?restrict ' \
  > "$OUT"
