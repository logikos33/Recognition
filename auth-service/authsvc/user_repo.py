from typing import Optional
from psycopg2.extras import RealDictCursor
from .db import get_conn


def get_by_email(email: str) -> Optional[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, email, password_hash, name, role, is_active "
                "FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
    return dict(row) if row else None


def get_by_id(user_id: str) -> Optional[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, email, name, role, is_active "
                "FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def create_user(email: str, password_hash: str, name: str) -> dict:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO users (email, password_hash, name, role, is_active) "
                "VALUES (%s, %s, %s, 'operator', true) "
                "RETURNING id, email, name, role",
                (email, password_hash, name))
            row = cur.fetchone()
    return dict(row)
