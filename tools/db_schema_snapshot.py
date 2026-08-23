#!/usr/bin/env python3
"""Snapshot SOMENTE-LEITURA do schema real de um banco (para o mapa de migração).

Por que existe
--------------
A seção "Banco" do mapa-contrato tem de vir do banco REAL (C-04), não de
migrations antigas. Este script lê ``information_schema`` + ``pg_stat_user_tables``
e grava tabelas/colunas por schema (public × tenant schemas), com contagem
exata de linhas (``row_count``; ``n_live_tup`` fica como referência) para
sinalizar tabelas vazias.

Nunca lê dados de linhas. Nunca imprime a URL de conexão.

Uso
---
    DATABASE_URL=$(railway variables --service Postgres --environment Desenvolvimento \
        --json | python3 -c 'import sys,json;print(json.load(sys.stdin)["DATABASE_PUBLIC_URL"])') \
    python3 tools/db_schema_snapshot.py --out docs/migration/inventory/db_schema_dev.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default=os.environ.get("DB_SNAPSHOT_LABEL", "dev"))
    args = ap.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL ausente", file=sys.stderr)
        return 2

    import psycopg2  # noqa: PLC0415
    from psycopg2.extras import RealDictCursor  # noqa: PLC0415

    conn = psycopg2.connect(url, connect_timeout=20, options="-c default_transaction_read_only=on")
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """
        SELECT nspname AS schema
        FROM pg_namespace
        WHERE nspname NOT IN ('pg_catalog','information_schema','pg_toast')
          AND nspname NOT LIKE 'pg_temp%'
        ORDER BY 1
        """
    )
    schemas = [r["schema"] for r in cur.fetchall()]

    cur.execute(
        """
        SELECT table_schema, table_name, column_name, data_type, is_nullable, column_default, ordinal_position
        FROM information_schema.columns
        WHERE table_schema = ANY(%s)
        ORDER BY table_schema, table_name, ordinal_position
        """,
        (schemas,),
    )
    cols = defaultdict(lambda: defaultdict(list))
    for r in cur.fetchall():
        cols[r["table_schema"]][r["table_name"]].append(
            {
                "name": r["column_name"],
                "type": r["data_type"],
                "nullable": r["is_nullable"] == "YES",
                "default": (r["column_default"] or "")[:80] or None,
            }
        )

    cur.execute(
        """
        SELECT schemaname, relname, n_live_tup
        FROM pg_stat_user_tables
        WHERE schemaname = ANY(%s)
        """,
        (schemas,),
    )
    live = {(r["schemaname"], r["relname"]): int(r["n_live_tup"]) for r in cur.fetchall()}
    # n_live_tup é estatística (pode estar zerada após restore sem ANALYZE) —
    # contagem exata por tabela, com timeout por statement.
    cur.execute("SET statement_timeout = '20s'")
    exact: dict[tuple[str, str], int | None] = {}
    for (schema, table) in sorted(live):
        try:
            cur.execute(
                'SELECT count(*) AS n FROM "' + schema.replace('"', '""') + '"."' + table.replace('"', '""') + '"'
            )
            exact[(schema, table)] = int(cur.fetchone()["n"])
        except Exception:  # noqa: BLE001 — timeout/permissão: fica None
            exact[(schema, table)] = None

    cur.execute(
        """
        SELECT table_schema, table_name, table_type
        FROM information_schema.tables
        WHERE table_schema = ANY(%s)
        ORDER BY 1,2
        """,
        (schemas,),
    )
    tables = defaultdict(dict)
    for r in cur.fetchall():
        tables[r["table_schema"]][r["table_name"]] = {
            "type": r["table_type"],
            "n_live_tup": live.get((r["table_schema"], r["table_name"])),
            "row_count": exact.get((r["table_schema"], r["table_name"])),
            "columns": cols[r["table_schema"]].get(r["table_name"], []),
        }

    # Funções/views podem importar para o mapa (p.ex. schema_migrations inexistente)
    cur.execute("SELECT current_database() AS db, version() AS version")
    meta = cur.fetchone()

    out = {
        "label": args.label,
        "database": meta["db"],
        "pg_version": meta["version"].split(" on ")[0],
        "schemas": schemas,
        "tables_by_schema": {s: dict(sorted(t.items())) for s, t in sorted(tables.items())},
        "counts": {s: len(t) for s, t in sorted(tables.items())},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"db={meta['db']} schemas={len(schemas)} tables={sum(out['counts'].values())} -> {args.out}")
    for s, n in out["counts"].items():
        print(f"  {s}: {n} tabelas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
