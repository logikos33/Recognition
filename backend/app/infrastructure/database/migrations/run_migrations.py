"""
EPI Monitor V2 — Migration Runner.

Script idempotente: verifica schema_migrations antes de aplicar.
Roda na ordem numérica dos arquivos .sql.
"""
import glob
import logging
import os
import sys

import psycopg2

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MIGRATE] %(message)s")
logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """Retorna DATABASE_URL corrigida."""
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def run_migrations() -> bool:
    """Executa migrations pendentes. Retorna True se sucesso."""
    db_url = get_database_url()
    if not db_url:
        logger.error("DATABASE_URL não definida")
        return False

    migrations_dir = os.path.dirname(os.path.abspath(__file__))
    sql_files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))

    if not sql_files:
        logger.warning("Nenhum arquivo .sql encontrado em %s", migrations_dir)
        return True

    try:
        conn = psycopg2.connect(db_url, connect_timeout=15)
        conn.autocommit = False
        cur = conn.cursor()

        # Garantir que schema_migrations existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(10) PRIMARY KEY,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        conn.commit()

        # Buscar migrations já aplicadas
        cur.execute("SELECT version FROM schema_migrations")
        applied = {row[0] for row in cur.fetchall()}

        for sql_file in sql_files:
            filename = os.path.basename(sql_file)
            version = filename.split("_")[0]

            if version in applied:
                logger.info("  [SKIP] %s (já aplicada)", filename)
                continue

            logger.info("  [APPLY] %s ...", filename)
            try:
                with open(sql_file) as f:
                    sql = f.read()
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (version,),
                )
                conn.commit()
                logger.info("  [OK] %s", filename)
            except psycopg2.Error as exc:
                conn.rollback()
                err = str(exc).lower()
                if "already exists" in err or "duplicate" in err:
                    logger.info("  [SKIP] %s (objetos já existem)", filename)
                    # Registrar como aplicada mesmo assim
                    try:
                        cur.execute(
                            "INSERT INTO schema_migrations (version) VALUES (%s) "
                            "ON CONFLICT DO NOTHING",
                            (version,),
                        )
                        conn.commit()
                    except Exception:
                        conn.rollback()
                else:
                    logger.error("  [FAIL] %s: %s", filename, exc)
                    return False

        conn.close()
        logger.info("Migrations completas: %d arquivos processados", len(sql_files))
        return True

    except Exception as exc:
        logger.error("Migration runner failed: %s", exc)
        return False


if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)
