#!/usr/bin/env python3
"""
seed_rvb.py — Env-gated seed script for RVB Isolantes (anchor client).

NEVER run automatically. NEVER import from railway_start.py.
Only executes when RVB_SEED_ENABLED=true is explicitly set.

Usage:
    RVB_SEED_ENABLED=true DATABASE_URL=postgresql://... \
    RVB_ADMIN_PASSWORD=<senha> python3 scripts/seed_rvb.py

Environment variables:
    RVB_SEED_ENABLED     Must be exactly "true" — hard gate
    DATABASE_URL         PostgreSQL connection string
    RVB_ADMIN_EMAIL      Admin email (default: admin@rvb.com.br)
    RVB_ADMIN_PASSWORD   Admin password (required)
    RVB_CAMERA_USERNAME  Camera username (default: admin)
    RVB_CAMERA_PASSWORD  Camera password (default: placeholder — update via UI)
    RVB_CAMERA_HOST_BASE Camera IP base, e.g. 192.168.1 (default: 10.0.0)
"""
import os
import sys
import uuid

# ── Hard gate ──────────────────────────────────────────────────────────────────
if os.environ.get("RVB_SEED_ENABLED") != "true":
    print("ERROR: RVB_SEED_ENABLED != 'true'. Aborting to prevent accidental seed.")
    print("  Set RVB_SEED_ENABLED=true to run this script intentionally.")
    sys.exit(1)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set.")
    sys.exit(1)

RVB_ADMIN_EMAIL = os.environ.get("RVB_ADMIN_EMAIL", "admin@rvb.com.br")
RVB_ADMIN_PASSWORD = os.environ.get("RVB_ADMIN_PASSWORD")
if not RVB_ADMIN_PASSWORD:
    print("ERROR: RVB_ADMIN_PASSWORD not set.")
    sys.exit(1)

RVB_CAMERA_USERNAME = os.environ.get("RVB_CAMERA_USERNAME", "admin")
RVB_CAMERA_PASSWORD = os.environ.get("RVB_CAMERA_PASSWORD", "PLACEHOLDER_UPDATE_VIA_UI")
RVB_CAMERA_HOST_BASE = os.environ.get("RVB_CAMERA_HOST_BASE", "10.0.0")

try:
    import psycopg2
    import bcrypt
except ImportError as e:
    print(f"ERROR: Missing dependency: {e}")
    print("  Install with: pip install psycopg2-binary bcrypt")
    sys.exit(1)

# ── Fixed UUIDs for idempotency ────────────────────────────────────────────────
RVB_TENANT_ID = "11111111-0000-0000-0000-000000000001"
RVB_ADMIN_USER_ID = "11111111-0000-0000-0000-000000000002"

# 28 camera stubs — names/locations reflect typical RVB plant layout.
# Update host IPs and credentials via the UI after first login.
CAMERA_STUBS = [
    ("Portaria Principal", "Entrada/Saída"),
    ("Portaria Secundária", "Entrada/Saída"),
    ("Área de Abastecimento 1", "Pátio"),
    ("Área de Abastecimento 2", "Pátio"),
    ("Área de Abastecimento 3", "Pátio"),
    ("Área de Abastecimento 4", "Pátio"),
    ("Linha de Produção 1", "Linha A"),
    ("Linha de Produção 2", "Linha A"),
    ("Linha de Produção 3", "Linha B"),
    ("Linha de Produção 4", "Linha B"),
    ("Linha de Produção 5", "Linha C"),
    ("Linha de Produção 6", "Linha C"),
    ("Almoxarifado Entrada", "Almoxarifado"),
    ("Almoxarifado Saída", "Almoxarifado"),
    ("Pátio de Caminhões 1", "Pátio Externo"),
    ("Pátio de Caminhões 2", "Pátio Externo"),
    ("Pátio de Caminhões 3", "Pátio Externo"),
    ("Doca de Carga 1", "Expedição"),
    ("Doca de Carga 2", "Expedição"),
    ("Doca de Carga 3", "Expedição"),
    ("Vestiário Masculino", "Área Interna"),
    ("Vestiário Feminino", "Área Interna"),
    ("Refeitório", "Área Interna"),
    ("Corredor Principal", "Área Interna"),
    ("Sala de Máquinas", "Manutenção"),
    ("Depósito EPI", "Manutenção"),
    ("Área Externa Norte", "Perimetral"),
    ("Área Externa Sul", "Perimetral"),
]

assert len(CAMERA_STUBS) == 28, f"Expected 28 cameras, got {len(CAMERA_STUBS)}"


def main() -> None:
    print(f"Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # 1. Tenant
        print(f"Upserting tenant 'rvb'...")
        cur.execute(
            """
            INSERT INTO tenants (id, name, slug, is_active)
            VALUES (%s, 'RVB Isolantes', 'rvb', TRUE)
            ON CONFLICT (id) DO NOTHING
            """,
            (RVB_TENANT_ID,),
        )
        cur.execute(
            """
            INSERT INTO tenants (id, name, slug, is_active)
            VALUES (%s, 'RVB Isolantes', 'rvb', TRUE)
            ON CONFLICT (slug) DO NOTHING
            """,
            (RVB_TENANT_ID,),
        )

        # 2. Admin user
        print(f"Upserting admin user '{RVB_ADMIN_EMAIL}'...")
        pw_hash = bcrypt.hashpw(RVB_ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()
        cur.execute(
            """
            INSERT INTO users (id, email, password_hash, name, role, is_active, tenant_id)
            VALUES (%s, %s, %s, 'Admin RVB', 'admin', TRUE, %s)
            ON CONFLICT (email) DO NOTHING
            """,
            (RVB_ADMIN_USER_ID, RVB_ADMIN_EMAIL, pw_hash, RVB_TENANT_ID),
        )

        # 3. Module: epi
        print("Enabling module 'epi' for RVB tenant...")
        cur.execute(
            """
            INSERT INTO tenant_modules (id, tenant_id, module_code, enabled)
            VALUES (%s, %s, 'epi', TRUE)
            ON CONFLICT (tenant_id, module_code) DO NOTHING
            """,
            (str(uuid.uuid4()), RVB_TENANT_ID),
        )

        # 4. Cameras
        print(f"Upserting {len(CAMERA_STUBS)} camera stubs...")
        inserted = 0
        for i, (name, location) in enumerate(CAMERA_STUBS, start=1):
            cam_id = str(uuid.uuid5(uuid.UUID(RVB_TENANT_ID), f"cam-{i:03d}"))
            host = f"{RVB_CAMERA_HOST_BASE}.{99 + i}"
            cur.execute(
                """
                INSERT INTO cameras (
                    id, tenant_id, user_id, name, location,
                    manufacturer, host, port, username, password_encrypted,
                    channel, subtype, is_active
                )
                VALUES (%s, %s, %s, %s, %s, 'intelbras', %s, 554, %s, %s, 1, 0, TRUE)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    cam_id,
                    RVB_TENANT_ID,
                    RVB_ADMIN_USER_ID,
                    name,
                    location,
                    host,
                    RVB_CAMERA_USERNAME,
                    RVB_CAMERA_PASSWORD,
                ),
            )
            if cur.rowcount:
                inserted += 1

        conn.commit()
        print(f"\nDone.")
        print(f"  Tenant:  RVB Isolantes (id={RVB_TENANT_ID})")
        print(f"  Admin:   {RVB_ADMIN_EMAIL}")
        print(f"  Module:  epi")
        print(f"  Cameras: {inserted} inserted (skipped existing)")
        if RVB_CAMERA_PASSWORD == "PLACEHOLDER_UPDATE_VIA_UI":
            print("\nWARNING: Cameras use placeholder password.")
            print("  Update credentials for each camera via the UI before going live.")

    except Exception as exc:
        conn.rollback()
        print(f"ERROR: {exc}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
