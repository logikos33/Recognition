"""Helpers de autenticação JWT."""
import os
import bcrypt
from flask_jwt_extended import get_jwt_identity
from services.shared.database import get_db_connection


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def get_current_user() -> dict:
    user_id = get_jwt_identity()
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, name, role FROM users WHERE id=%s AND is_active=TRUE",
            (user_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None


def require_admin():
    user = get_current_user()
    if not user or user['role'] != 'admin':
        from flask import jsonify
        return jsonify({'success': False, 'error': 'Acesso restrito a administradores'}), 403
    return None
