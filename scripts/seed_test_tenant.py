"""
Seed do tenant de TESTE isolado — task-055a / PR A2.

ATENÇÃO: NÃO é migration. Roda MANUALMENTE com gate de env para evitar
execução acidental em produção.

Cria:
  - tenant      : id=00000000-0000-0000-0000-0000000000AA  slug=test-epi-ci
  - tenant_module: epi enabled para o tenant de teste
  - user admin  : test-admin@epi-ci.internal  role=admin (idempotente)

Uso:
  SEED_ALLOWED=1 DATABASE_URL=postgresql://... python3 scripts/seed_test_tenant.py

  # Para deletar o tenant de teste (cuidado — irreversível):
  SEED_ALLOWED=1 DATABASE_URL=... SEED_DESTROY=1 python3 scripts/seed_test_tenant.py
"""
import hashlib
import os
import sys
import uuid

TEST_TENANT_ID = "00000000-0000-0000-0000-0000000000AA"
TEST_TENANT_SLUG = "test-epi-ci"
TEST_TENANT_NAME = "Tenant de Teste CI (task-055a)"
TEST_USER_EMAIL = "test-admin@epi-ci.internal"
TEST_USER_NAME = "CI Test Admin"
TEST_USER_ROLE = "admin"


def _gate() -> None:
    if os.environ.get("SEED_ALLOWED") != "1":
        print(
            "ERRO: defina SEED_ALLOWED=1 para executar este script.\n"
            "Nunca rode em produção sem intenção explícita."
        )
        sys.exit(1)
    db = os.environ.get("DATABASE_URL", "")
    if not db:
        print("ERRO: DATABASE_URL não definida.")
        sys.exit(1)


def _make_password_hash(password: str) -> str:
    """Bcrypt hash via bcrypt lib ou fallback sha256 (apenas para CI)."""
    try:
        import bcrypt  # noqa: PLC0415
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode()
    except ImportError:
        sha = hashlib.sha256(password.encode()).hexdigest()
        print(
            "AVISO: bcrypt não instalado — usando SHA256 (aceitável apenas em CI/teste)."
        )
        return f"sha256:{sha}"


def _get_conn():
    import psycopg2  # noqa: PLC0415
    from psycopg2.extras import RealDictCursor  # noqa: PLC0415
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def seed(conn) -> None:
    with conn.cursor() as cur:
        # 1. Tenant de teste
        cur.execute(
            """
            INSERT INTO tenants (id, name, slug, is_active)
            VALUES (%s, %s, %s, TRUE)
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, slug = EXCLUDED.slug
            RETURNING id, slug
            """,
            (TEST_TENANT_ID, TEST_TENANT_NAME, TEST_TENANT_SLUG),
        )
        row = cur.fetchone()
        print(f"  tenant upserted: id={row['id']} slug={row['slug']}")

        # 2. Módulo EPI ativado para o tenant de teste
        cur.execute(
            """
            INSERT INTO tenant_modules (tenant_id, module_code, enabled)
            VALUES (%s, 'epi', TRUE)
            ON CONFLICT (tenant_id, module_code) DO UPDATE SET enabled = TRUE
            """,
            (TEST_TENANT_ID,),
        )
        print("  tenant_module epi: upserted")

        # 3. Usuário admin de teste (idempotente por email+tenant)
        test_password = os.environ.get("TEST_ADMIN_PASSWORD", "ci-test-password-2026")
        pwd_hash = _make_password_hash(test_password)

        cur.execute(
            """
            INSERT INTO users (id, email, password_hash, name, role, tenant_id, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (email) DO UPDATE
                SET name = EXCLUDED.name,
                    role = EXCLUDED.role,
                    tenant_id = EXCLUDED.tenant_id,
                    is_active = TRUE
            RETURNING id, email, role
            """,
            (
                str(uuid.uuid4()),
                TEST_USER_EMAIL,
                pwd_hash,
                TEST_USER_NAME,
                TEST_USER_ROLE,
                TEST_TENANT_ID,
            ),
        )
        row = cur.fetchone()
        print(f"  user upserted: id={row['id']} email={row['email']} role={row['role']}")

    conn.commit()
    print("\nSeed concluído com sucesso.")
    print(f"  TENANT_ID  = {TEST_TENANT_ID}")
    print(f"  USER_EMAIL = {TEST_USER_EMAIL}")
    print("  USER_PASS  = (env TEST_ADMIN_PASSWORD ou 'ci-test-password-2026')")


def destroy(conn) -> None:
    """Remove o tenant de teste e todos os dados em cascata."""
    print(f"DESTRUINDO tenant {TEST_TENANT_ID} e dados em cascata...")
    with conn.cursor() as cur:
        cur.execute("DELETE FROM tenants WHERE id = %s", (TEST_TENANT_ID,))
        deleted = cur.rowcount
    conn.commit()
    print(f"  {deleted} tenant(s) deletado(s).")


def main() -> None:
    _gate()

    print("Conectando ao banco...")
    conn = _get_conn()

    try:
        if os.environ.get("SEED_DESTROY") == "1":
            destroy(conn)
        else:
            seed(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
