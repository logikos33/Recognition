"""Auth: register, login, me. Máx 150 linhas."""
import traceback
from flask import request, current_app
from flask_jwt_extended import create_access_token, jwt_required
from . import auth_bp
from api.utils.auth import hash_password, check_password, get_current_user
from api.utils.responses import success, error
from services.shared.database import get_db_connection


@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json() or {}
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        name = (data.get('name') or '').strip()

        if not all([email, password, name]):
            return error('email, password e name são obrigatórios')
        if len(password) < 6:
            return error('Senha: mínimo 6 caracteres')

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE email=%s", (email,))
            if cur.fetchone():
                return error('Email já cadastrado', 409)
            cur.execute(
                "INSERT INTO users (email,password_hash,name) VALUES(%s,%s,%s) "
                "RETURNING id,email,name,role",
                (email, hash_password(password), name)
            )
            user = dict(cur.fetchone())

        token = create_access_token(identity=str(user['id']))
        return success({'token': token, 'user': user}, status=201)

    except Exception:
        current_app.logger.error(traceback.format_exc())
        return error('Erro interno', 500)


@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json() or {}
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''

        if not email or not password:
            return error('email e password obrigatórios')

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id,email,name,role,password_hash,is_active FROM users WHERE email=%s",
                (email,)
            )
            user = cur.fetchone()

        if not user or not user['is_active']:
            return error('Credenciais inválidas', 401)
        if not check_password(password, user['password_hash']):
            return error('Credenciais inválidas', 401)

        user_dict = {k: str(v) if k == 'id' else v
                     for k, v in dict(user).items()
                     if k != 'password_hash'}
        token = create_access_token(identity=str(user['id']))
        return success({'token': token, 'user': user_dict})

    except Exception:
        current_app.logger.error(traceback.format_exc())
        return error('Erro interno', 500)


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user = get_current_user()
    if not user:
        return error('Usuário não encontrado', 404)
    user['id'] = str(user['id'])
    return success(user)
