"""
Helpers de setup direto no banco — cria tenants, usuários, sites, enrollment tokens.

Sem HTTP: psycopg2 direto (C-03). Cada chamada é autocontida e idempotente-friendly
(usa UUIDs gerados localmente para evitar conflito entre testes paralelos).
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt


def create_tenant(conn, name: str) -> dict:
    """Insere tenant em public.tenants com slug único. Retorna registro."""
    tid = str(uuid.uuid4())
    slug = f"harness-{secrets.token_hex(6)}"
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.tenants (id, name, slug, is_active)
            VALUES (%s, %s, %s, TRUE)
            RETURNING id, name, slug
            """,
            (tid, name, slug),
        )
        row = cur.fetchone()
    return dict(row)


def create_admin_user(conn, tenant_id: str, email: str, password: str) -> dict:
    """Insere usuário com role 'admin' no tenant. Retorna registro."""
    uid = str(uuid.uuid4())
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.users (id, tenant_id, email, password_hash, name, role, is_active)
            VALUES (%s, %s, %s, %s, %s, 'admin', TRUE)
            RETURNING id, tenant_id, email, name, role
            """,
            (uid, tenant_id, email, pw_hash, f"Harness Admin {tenant_id[:8]}"),
        )
        row = cur.fetchone()
    return dict(row)


def create_edge_site(conn, tenant_id: str, name: str, deployment_mode: str = "edge") -> dict:
    """Insere edge site em public.edge_sites. Retorna registro."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.edge_sites (tenant_id, name, deployment_mode, status)
            VALUES (%s, %s, %s, 'active')
            RETURNING id, tenant_id, name, deployment_mode, status
            """,
            (tenant_id, name, deployment_mode),
        )
        row = cur.fetchone()
    return dict(row)


def create_enrollment_token(conn, site_id: str, tenant_id: str) -> str:
    """Insere enrollment token one-time. Retorna plaintext (banco armazena só o hash SHA-256)."""
    plaintext = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.enrollment_tokens (tenant_id, site_id, token_hash, expires_at)
            VALUES (%s, %s, %s, %s)
            """,
            (tenant_id, site_id, token_hash, expires_at),
        )
    return plaintext
