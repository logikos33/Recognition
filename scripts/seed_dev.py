#!/usr/bin/env python3
"""
seed_dev.py — Seed env-gated para o ambiente de desenvolvimento.

NUNCA roda automaticamente. NUNCA importado por railway_start.py.
Só executa quando APP_ENV=develop OU SEED_DEV=1 OU RAILWAY_ENVIRONMENT=Desenvolvimento.

Uso:
    SEED_DEV=1 DATABASE_URL=postgresql://... python3 scripts/seed_dev.py
    railway run --service API-V3 -- python3 scripts/seed_dev.py

O que cria (idempotente — ON CONFLICT DO UPDATE):
    1. Tenant dev  (slug='dev', schema_name='dev')
    2. Superadmin  admin@recognition.dev    role=superadmin
    3. Demo        demo@recognition.dev     role=operator

Variáveis de ambiente:
    DATABASE_URL           PostgreSQL connection string (obrigatório)
    SEED_ADMIN_PASSWORD    Senha do superadmin (default: RecognitionDev@2024!)
    SEED_ADMIN_EMAIL       Email do superadmin (default: admin@recognition.dev)
    SEED_DEMO_EMAIL        Email do usuário demo (default: demo@recognition.dev)
    APP_ENV                dev/develop/development habilita o script
    SEED_DEV               '1'/'true'/'yes' habilita o script
    RAILWAY_ENVIRONMENT    'Desenvolvimento'/'develop' habilita o script
"""
import os
import sys
import uuid

# ── GUARD DE AMBIENTE (porta de entrada) ──────────────────────────────────────
APP_ENV = os.environ.get("APP_ENV", "").lower()
SEED_DEV = os.environ.get("SEED_DEV", "").lower() in ("1", "true", "yes")
RAILWAY_ENV = os.environ.get("RAILWAY_ENVIRONMENT", "").lower()

ALLOWED = (
    APP_ENV in ("develop", "development", "dev")
    or SEED_DEV
    or "desenvolvimento" in RAILWAY_ENV
    or "develop" in RAILWAY_ENV
)

if not ALLOWED:
    print(
        f"[SEED] BLOQUEADO — ambiente não é develop.\n"
        f"       APP_ENV={os.environ.get('APP_ENV', '')!r}  "
        f"RAILWAY_ENVIRONMENT={os.environ.get('RAILWAY_ENVIRONMENT', '')!r}"
    )
    print("[SEED] Para forçar (APENAS em dev): SEED_DEV=1 python3 scripts/seed_dev.py")
    sys.exit(0)  # exit 0 — não quebra CI, apenas não executa

print(
    f"[SEED] Ambiente autorizado:"
    f" APP_ENV={os.environ.get('APP_ENV', 'n/a')!r}"
    f" RAILWAY_ENVIRONMENT={os.environ.get('RAILWAY_ENVIRONMENT', 'n/a')!r}"
    f" SEED_DEV={SEED_DEV}"
)

# ── DEPENDÊNCIAS ──────────────────────────────────────────────────────────────
try:
    import psycopg2
    import bcrypt
except ImportError as exc:
    print(f"[SEED] ERRO: dependência faltando: {exc}")
    print("  Instale: pip install psycopg2-binary bcrypt")
    sys.exit(1)

# ── CONFIG ────────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("[SEED] ERRO: DATABASE_URL não definida.")
    sys.exit(1)

# Guard duplo: rejeita conexão a hosts de produção conhecidos
_PROD_KEYWORDS = ("production", "prod", "staging", "homolog")
_db_lower = DATABASE_URL.lower()
for _kw in _PROD_KEYWORDS:
    if _kw in _db_lower and "desenvolvimento" not in RAILWAY_ENV and not SEED_DEV:
        print(f"[SEED] BLOQUEADO — DATABASE_URL contém '{_kw}' e não é ambiente de dev confirmado.")
        sys.exit(1)

SEED_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "RecognitionDev@2024!")
SEED_ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@recognition.dev")
SEED_DEMO_EMAIL = os.environ.get("SEED_DEMO_EMAIL", "demo@recognition.dev")

# ── UUIDs fixos para idempotência ─────────────────────────────────────────────
DEV_TENANT_ID = "22222222-dddd-0000-0000-000000000001"
DEV_ADMIN_USER_ID = "22222222-dddd-0000-0000-000000000002"
DEV_DEMO_USER_ID = "22222222-dddd-0000-0000-000000000003"


def _hash_password(plaintext: str) -> str:
    """Gera bcrypt hash da senha (mesma lib usada pelo app)."""
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def main() -> None:
    print(f"[SEED] Conectando ao banco...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # ── 1. Tenant dev ─────────────────────────────────────────────────────
        print("[SEED] Upserting tenant 'dev'...")
        cur.execute(
            """
            INSERT INTO tenants (id, name, slug, schema_name, plan, modules_enabled, is_active)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, TRUE)
            ON CONFLICT (id) DO UPDATE SET
                name            = EXCLUDED.name,
                slug            = EXCLUDED.slug,
                schema_name     = EXCLUDED.schema_name,
                plan            = EXCLUDED.plan,
                modules_enabled = EXCLUDED.modules_enabled,
                is_active       = TRUE
            """,
            (
                DEV_TENANT_ID,
                "Desenvolvimento — Recognition Dev",
                "dev",
                "dev",
                "internal",
                '["epi","counting","quality","basic","analytics","admin"]',
            ),
        )

        # Fallback: se slug 'dev' já existe com outro id, apenas atualiza
        cur.execute(
            """
            UPDATE tenants
            SET name            = %s,
                schema_name     = COALESCE(schema_name, %s),
                plan            = %s,
                modules_enabled = %s::jsonb,
                is_active       = TRUE
            WHERE slug = %s AND id != %s
            """,
            (
                "Desenvolvimento — Recognition Dev",
                "dev",
                "internal",
                '["epi","counting","quality","basic","analytics","admin"]',
                "dev",
                DEV_TENANT_ID,
            ),
        )

        # Recupera o tenant_id real (pode ser o fixo ou o pré-existente)
        cur.execute("SELECT id FROM tenants WHERE slug = %s", ("dev",))
        row = cur.fetchone()
        dev_tenant_id = str(row[0]) if row else DEV_TENANT_ID
        print(f"[SEED] Tenant dev id={dev_tenant_id}")

        # ── 2. tenant_modules para o tenant dev ───────────────────────────────
        for module_code in ("epi", "counting", "quality", "basic", "analytics"):
            cur.execute(
                """
                INSERT INTO tenant_modules (id, tenant_id, module_code, enabled)
                VALUES (%s, %s, %s, TRUE)
                ON CONFLICT (tenant_id, module_code) DO UPDATE SET enabled = TRUE
                """,
                (str(uuid.uuid4()), dev_tenant_id, module_code),
            )

        # ── 3. Superadmin dev ─────────────────────────────────────────────────
        print(f"[SEED] Upserting superadmin '{SEED_ADMIN_EMAIL}'...")
        admin_hash = _hash_password(SEED_ADMIN_PASSWORD)
        cur.execute(
            """
            INSERT INTO users (id, email, password_hash, name, role, is_active, tenant_id)
            VALUES (%s, %s, %s, %s, 'superadmin', TRUE, %s)
            ON CONFLICT (email) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                name          = EXCLUDED.name,
                role          = 'superadmin',
                is_active     = TRUE,
                tenant_id     = EXCLUDED.tenant_id,
                updated_at    = NOW()
            """,
            (
                DEV_ADMIN_USER_ID,
                SEED_ADMIN_EMAIL,
                admin_hash,
                "Admin Dev",
                dev_tenant_id,
            ),
        )

        # ── 4. Usuário demo (operator) ─────────────────────────────────────────
        print(f"[SEED] Upserting demo user '{SEED_DEMO_EMAIL}'...")
        demo_hash = _hash_password(SEED_ADMIN_PASSWORD)
        cur.execute(
            """
            INSERT INTO users (id, email, password_hash, name, role, is_active, tenant_id)
            VALUES (%s, %s, %s, %s, 'operator', TRUE, %s)
            ON CONFLICT (email) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                name          = EXCLUDED.name,
                role          = 'operator',
                is_active     = TRUE,
                tenant_id     = EXCLUDED.tenant_id,
                updated_at    = NOW()
            """,
            (
                DEV_DEMO_USER_ID,
                SEED_DEMO_EMAIL,
                demo_hash,
                "Demo Operator",
                dev_tenant_id,
            ),
        )

        conn.commit()

        # ── Resultado ──────────────────────────────────────────────────────────
        print("\n[SEED] ══════════════════════════════════════════")
        print("[SEED] Seed concluído com sucesso!")
        print(f"[SEED] Tenant:      Desenvolvimento — Recognition Dev (slug=dev)")
        print(f"[SEED] Tenant ID:   {dev_tenant_id}")
        print(f"[SEED]")
        print(f"[SEED] SUPERADMIN")
        print(f"[SEED]   email:    {SEED_ADMIN_EMAIL}")
        print(f"[SEED]   senha:    {SEED_ADMIN_PASSWORD}")
        print(f"[SEED]   role:     superadmin")
        print(f"[SEED]")
        print(f"[SEED] DEMO OPERATOR")
        print(f"[SEED]   email:    {SEED_DEMO_EMAIL}")
        print(f"[SEED]   senha:    {SEED_ADMIN_PASSWORD}")
        print(f"[SEED]   role:     operator")
        print("[SEED] ══════════════════════════════════════════")
        print("[SEED] AVISO: credenciais acima são apenas para dev — nunca usar em prod.")

    except Exception as exc:
        conn.rollback()
        print(f"[SEED] ERRO — rollback executado: {exc}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
