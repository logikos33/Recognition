"""
Harness migration runner — espelha railway_start.py:run_migrations() (linhas 55–90).

Diferenças intencionais (cirúrgicas):
  1. DSN via --dsn arg ou HARNESS_DATABASE_URL (nunca DATABASE_URL, evita acidente em prod).
  2. Glob fixo em infra/migrations/*.sql (sem fallback migrations/*.sql legado).
  3. --pass N apenas para identificar a passada nos logs.
  4. Exit code 1 se qualquer erro não-idempotente e não-legado ocorrer.

NÃO usa schema_migrations — fiel à produção que re-roda tudo a cada deploy.
NÃO chamar infra/migrations/run_migrations.py (tem tracker, não reflete prod).
"""

import argparse
import glob
import logging
import os
import sys

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [HARNESS] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("harness.migrations")

# Erros legados conhecidos: a migration 038_operations.sql referencia ip_cameras,
# renomeada para cameras na 013 e recriada corretamente pela 047_operations_repair.sql.
# O estado final do banco está correto; a 038 é forward-only (C-02) — não editar.
KNOWN_LEGACY_ERRORS = (
    "ip_cameras",  # 038_operations.sql — FK para tabela renomeada, corrigida pela 047
)


def _is_known_legacy(error_text: str) -> bool:
    lowered = error_text.lower()
    return any(marker in lowered for marker in KNOWN_LEGACY_ERRORS)


def _is_idempotent_error(error_text: str) -> bool:
    lowered = error_text.lower()
    return "already exists" in lowered or "duplicate" in lowered


def run(dsn: str, pass_n: int) -> bool:
    """Aplica infra/migrations/*.sql em ordem, imitando railway_start.run_migrations().

    Retorna True se nenhum erro fatal (não-idempotente e não-legado) ocorreu.
    """
    log.info("=== Migrations (passada %d) ===", pass_n)

    sql_files = sorted(glob.glob("infra/migrations/*.sql"))
    if not sql_files:
        log.error("Nenhum arquivo SQL encontrado em infra/migrations/ — verifique o CWD.")
        return False

    log.info("  %d arquivos encontrados em infra/migrations/", len(sql_files))

    try:
        conn = psycopg2.connect(dsn)
    except Exception as e:
        log.error("Falha ao conectar ao banco: %s", e)
        return False

    cur = conn.cursor()
    fatal_errors: list[tuple[str, str]] = []

    for f in sql_files:
        basename = os.path.basename(f)
        log.info("  [pass %d] %s ...", pass_n, basename)
        try:
            cur.execute(open(f).read())  # noqa: WPS515 — intencional: 1 execute por arquivo
            conn.commit()
            log.info("  [pass %d] %s ✅", pass_n, basename)
        except Exception as e:
            conn.rollback()
            err_text = str(e)
            if _is_idempotent_error(err_text):
                log.info("  [pass %d] %s ⚠️  já existe (OK — redeploy normal)", pass_n, basename)
            elif _is_known_legacy(err_text):
                log.warning(
                    "  [pass %d] %s ⚠️  LEGADO CONHECIDO: %s", pass_n, basename, err_text.strip()
                )
            else:
                log.error("  [pass %d] %s ❌ %s", pass_n, basename, err_text.strip())
                fatal_errors.append((basename, err_text))

    conn.close()

    if fatal_errors:
        log.error("=== %d erro(s) fatal(is) na passada %d ===", len(fatal_errors), pass_n)
        for name, err in fatal_errors:
            log.error("  ❌ %s: %s", name, err.strip())
        return False

    log.info("=== Passada %d OK ===", pass_n)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Harness migration runner")
    parser.add_argument(
        "--dsn",
        default=os.environ.get("HARNESS_DATABASE_URL", ""),
        help="DSN PostgreSQL (ou HARNESS_DATABASE_URL)",
    )
    parser.add_argument("--pass", dest="pass_n", type=int, default=1, help="Número da passada (log)")
    args = parser.parse_args()

    if not args.dsn:
        log.error("DSN não informado. Use --dsn ou HARNESS_DATABASE_URL.")
        sys.exit(1)

    success = run(args.dsn, args.pass_n)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
