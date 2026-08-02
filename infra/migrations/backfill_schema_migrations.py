#!/usr/bin/env python3
"""
Backfill do ledger de migrations (public.migrations_ledger) para um banco JÁ migrado
pelo loop LEGADO (produção atual, sem MIGRATIONS_LEDGER_CUTOVER).

Nome do arquivo mantido como pedido no mutirão (`backfill_schema_migrations.py`), mas o
ALVO real é public.migrations_ledger — NÃO public.schema_migrations (tabela legada e
imutável criada por 001_initial_schema.sql, incompatível com o formato do ledger; ver
docstring de 107_migrations_ledger.sql para o porquê).

Este é o script que materializa o passo "cutover real" do mutirão (item 3.5, gate
humano): rodar isto ANTES de ligar MIGRATIONS_LEDGER_CUTOVER=1 num banco que já tem
histórico. Sem backfill, o runner novo veria o ledger vazio e tentaria reaplicar TODAS
as migrations do zero contra um banco que já as tem.

O QUE FAZ:
  1. Garante que public.migrations_ledger existe (mesma DDL de runner_core._ensure_ledger_table).
  2. Para cada infra/migrations/*.sql, calcula o checksum sha256 atual e insere uma linha
     (tenant_schema='_global', version, filename, checksum, success=True) — assumindo que,
     num banco já totalmente migrado, TODA migration do diretório já foi aplicada com
     sucesso (inclusive as 4 toleradas como "legado conhecido": num banco já maduro, elas
     viram no-op bem-sucedido — ver README do harness).
  3. ON CONFLICT DO NOTHING — nunca sobrescreve uma linha que já exista no ledger (backfill
     é seguro rodar mais de uma vez; não usa o UPSERT que o runner usa em operação normal).
  4. Imprime um resumo: quantas linhas foram inseridas vs. já presentes.

NUNCA embute um DSN default — sempre --dsn explícito ou HARNESS_DATABASE_URL/DATABASE_URL
via variável de ambiente escolhida por quem roda.

Uso:
    python3 infra/migrations/backfill_schema_migrations.py --dsn postgresql://...
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runner_core  # infra/migrations/runner_core.py

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BACKFILL] %(message)s",
)
log = logging.getLogger("migrations.backfill")


def backfill(dsn: str, migrations_dir: str = runner_core.DEFAULT_MIGRATIONS_DIR) -> tuple[int, int]:
    """Retorna (inseridas, já_presentes)."""
    import psycopg2

    files = runner_core.sql_files(migrations_dir)
    if not files:
        log.error("Nenhum arquivo .sql encontrado em %s", migrations_dir)
        return (0, 0)

    conn = psycopg2.connect(dsn)
    try:
        runner_core._ensure_ledger_table(conn, log)  # noqa: SLF001 — reuso intencional

        inserted = 0
        already_present = 0
        cur = conn.cursor()
        for path in files:
            basename = os.path.basename(path)
            version = runner_core.version_of(basename)
            checksum = runner_core.sha256_of_file(path)

            cur.execute(
                """
                INSERT INTO public.migrations_ledger
                    (tenant_schema, version, filename, checksum, installed_rank, installed_on, success)
                VALUES (
                    %(tenant_schema)s, %(version)s, %(filename)s, %(checksum)s,
                    (SELECT COALESCE(MAX(installed_rank), 0) + 1 FROM public.migrations_ledger
                     WHERE tenant_schema = %(tenant_schema)s),
                    NOW(), TRUE
                )
                ON CONFLICT (tenant_schema, version, filename) DO NOTHING
                """,
                {
                    "tenant_schema": runner_core.TENANT_SCHEMA_GLOBAL,
                    "version": version,
                    "filename": basename,
                    "checksum": checksum,
                },
            )
            conn.commit()
            if cur.rowcount == 1:
                inserted += 1
                log.info("  %s -> inserida (checksum=%s)", basename, checksum[:12])
            else:
                already_present += 1
                log.info("  %s -> já presente no ledger (mantida como estava)", basename)

        return (inserted, already_present)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill de public.migrations_ledger")
    parser.add_argument(
        "--dsn",
        default=os.environ.get("HARNESS_DATABASE_URL") or os.environ.get("DATABASE_URL", ""),
        help="DSN PostgreSQL. NUNCA embutir URL no código — passe aqui ou via env.",
    )
    args = parser.parse_args()

    if not args.dsn:
        log.error("DSN não informado. Use --dsn ou defina HARNESS_DATABASE_URL/DATABASE_URL.")
        sys.exit(1)

    inserted, already_present = backfill(args.dsn)
    total = inserted + already_present
    log.info(
        "=== Resumo: %d migration(ões) no diretório | %d inserida(s) | %d já presente(s) ===",
        total, inserted, already_present,
    )


if __name__ == "__main__":
    main()
