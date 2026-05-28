#!/usr/bin/env python3
"""
scripts/migrate_public_to_rvb.py — Migração de dados public → rvb.

Move câmeras, alertas e jobs de treinamento do schema `public`
para o schema `rvb`, filtrando pelo tenant_id do tenant rvb.

Estratégia:
  INSERT INTO rvb.{table} SELECT * FROM public.{table}
  WHERE tenant_id = :rvb_uuid ON CONFLICT DO NOTHING

Segurança:
  - Idempotente (ON CONFLICT DO NOTHING)
  - Nunca deleta dados da origem
  - Dry-run por padrão (--execute para aplicar)

Uso:
  python3 scripts/migrate_public_to_rvb.py --dry-run     # inspecionar
  python3 scripts/migrate_public_to_rvb.py --execute     # migrar de verdade
  python3 scripts/migrate_public_to_rvb.py --execute --tenant-slug acme  # outro tenant
"""
import argparse
import os
import sys

import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_conn():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL não definida")
        sys.exit(1)
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)


# Tabelas a migrar e suas colunas de filtro por tenant_id
TABLES = [
    "cameras",
    "alerts",
    "training_jobs",
    "trained_models",
    "quality_inspections",
    "crossings",
]


def get_tenant_info(conn, slug: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, slug, schema_name FROM tenants WHERE slug = %s", (slug,)
        )
        row = cur.fetchone()
        if not row:
            print(f"ERROR: Tenant com slug '{slug}' não encontrado")
            sys.exit(1)
        return dict(row)


def table_exists(conn, schema: str, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
            """,
            (schema, table),
        )
        return cur.fetchone() is not None


def has_tenant_id_column(conn, schema: str, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s AND column_name = 'tenant_id'
            """,
            (schema, table),
        )
        return cur.fetchone() is not None


def count_rows(conn, schema: str, table: str, tenant_id: str) -> int:
    with conn.cursor() as cur:
        try:
            cur.execute(
                f'SELECT COUNT(*) AS n FROM "{schema}"."{table}" WHERE tenant_id = %s',  # noqa: S608
                (tenant_id,),
            )
            row = cur.fetchone()
            return row["n"] if row else 0
        except Exception:
            return -1


def migrate_table(
    conn, src_schema: str, dst_schema: str, table: str, tenant_id: str, dry_run: bool
) -> int:
    """Migra uma tabela. Retorna quantidade de linhas inseridas (0 em dry-run)."""
    src = f'"{src_schema}"."{table}"'
    dst = f'"{dst_schema}"."{table}"'

    # Obter colunas
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (src_schema, table),
        )
        cols = [r["column_name"] for r in cur.fetchall()]

    if not cols:
        print(f"  SKIP {table}: sem colunas (tabela vazia ou inexistente em {src_schema})")
        return 0

    cols_sql = ", ".join(f'"{c}"' for c in cols)
    # schema/table names validated by table_exists() — not from user input
    sql = (
        f'INSERT INTO {dst} ({cols_sql}) '  # noqa: S608
        f'SELECT {cols_sql} FROM {src} '  # noqa: S608
        f'WHERE tenant_id = %s ON CONFLICT DO NOTHING'  # noqa: S608
    )

    if dry_run:
        n = count_rows(conn, src_schema, table, tenant_id)
        print(f"  DRY-RUN {table}: {n} linhas seriam migradas de {src_schema} → {dst_schema}")
        return 0

    with conn.cursor() as cur:
        cur.execute(sql, (tenant_id,))
        inserted = cur.rowcount
        print(f"  MIGRATED {table}: {inserted} linhas inseridas em {dst_schema}")
        return inserted


def main():
    parser = argparse.ArgumentParser(description="Migrar dados public → schema do tenant")
    parser.add_argument("--execute", action="store_true", help="Aplicar migração (padrão: dry-run)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Apenas inspecionar")
    parser.add_argument("--tenant-slug", default="rvb", help="Slug do tenant destino (padrão: rvb)")
    parser.add_argument("--src-schema", default="public", help="Schema de origem (padrão: public)")
    args = parser.parse_args()

    dry_run = not args.execute

    conn = get_db_conn()
    try:
        tenant = get_tenant_info(conn, args.tenant_slug)
        tenant_id = str(tenant["id"])
        dst_schema = tenant["schema_name"]
        src_schema = args.src_schema

        print(f"\n{'DRY-RUN' if dry_run else 'EXECUTE'}: {src_schema} → {dst_schema}")
        print(f"Tenant: {tenant['slug']} (id={tenant_id})")
        print("-" * 60)

        if not dry_run:
            conn.autocommit = False

        total_migrated = 0
        for table in TABLES:
            if not table_exists(conn, src_schema, table):
                print(f"  SKIP {table}: não existe em {src_schema}")
                continue
            if not table_exists(conn, dst_schema, table):
                print(f"  SKIP {table}: não existe em {dst_schema} (criar migration antes)")
                continue
            if not has_tenant_id_column(conn, src_schema, table):
                print(f"  SKIP {table}: sem coluna tenant_id")
                continue
            n = migrate_table(conn, src_schema, dst_schema, table, tenant_id, dry_run)
            total_migrated += n

        if not dry_run:
            conn.commit()
            print(f"\nCOMMITTED: {total_migrated} linhas migradas no total")
        else:
            print("\nDRY-RUN concluído. Execute com --execute para aplicar.")

    except Exception as exc:
        if not dry_run:
            conn.rollback()
        print(f"\nERROR: {exc}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
