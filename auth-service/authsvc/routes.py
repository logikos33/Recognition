import logging
from flask import Blueprint, jsonify, request
from . import jwt_handler, password, user_repo, session_store

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _safe(user: dict) -> dict:
    return {"id": str(user["id"]), "email": user["email"],
            "name": user.get("name", ""), "role": user.get("role", "operator")}


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    plain = data.get("password", "")
    if not email or not plain:
        return jsonify({"error": "email e password são obrigatórios"}), 400
    user = user_repo.get_by_email(email)
    if not user or not user.get("is_active") or not password.check_password(plain, user["password_hash"]):
        return jsonify({"error": "Credenciais inválidas"}), 401
    uid = str(user["id"])
    access = jwt_handler.create_access_token(uid, user["email"], user.get("role", "operator"))
    refresh = jwt_handler.create_refresh_token(uid)
    session_store.store_refresh(uid, refresh)
    logger.info("login_ok: email=%s", email)
    return jsonify({"success": True, "data": {
        "token": access, "refresh_token": refresh, "user": _safe(user),
    }})


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    plain = data.get("password", "")
    name = data.get("name") or data.get("full_name", "")
    if not email or not plain or not name:
        return jsonify({"error": "email, password e name são obrigatórios"}), 400
    if user_repo.get_by_email(email):
        return jsonify({"error": "Email já cadastrado"}), 400
    try:
        user = user_repo.create_user(email, password.hash_password(plain), name)
    except Exception as exc:
        logger.error("register_error: %s", exc)
        return jsonify({"error": "Erro ao criar usuário"}), 500
    return jsonify({"success": True, "data": {"user": user}}), 201


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    data = request.get_json() or {}
    token = data.get("refresh_token", "")
    payload = jwt_handler.decode_unsafe(token)
    if not payload or payload.get("type") != "refresh":
        return jsonify({"error": "Token inválido"}), 401
    uid = payload.get("sub", "")
    if session_store.get_refresh(uid) != token:
        return jsonify({"error": "Token revogado"}), 401
    user = user_repo.get_by_id(uid)
    if not user or not user.get("is_active"):
        return jsonify({"error": "Usuário inválido"}), 401
    new_access = jwt_handler.create_access_token(uid, user["email"], user.get("role", "operator"))
    new_refresh = jwt_handler.create_refresh_token(uid)
    session_store.store_refresh(uid, new_refresh)
    return jsonify({"success": True, "data": {"token": new_access, "refresh_token": new_refresh}})


@auth_bp.route("/logout", methods=["POST"])
def logout():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        payload = jwt_handler.verify_token(token)
        if payload:
            session_store.revoke_refresh(payload.get("sub", ""))
    return jsonify({"success": True})


@auth_bp.route("/validate", methods=["POST"])
def validate():
    data = request.get_json() or {}
    payload = jwt_handler.verify_token(data.get("token", ""))
    if not payload:
        return jsonify({"valid": False}), 401
    return jsonify({"valid": True, "payload": payload})


@auth_bp.route("/me", methods=["GET"])
def me():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    payload = jwt_handler.verify_token(token)
    if not payload:
        return jsonify({"error": "Não autenticado"}), 401
    user = user_repo.get_by_id(payload.get("sub", ""))
    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404
    return jsonify({"success": True, "data": {"user": _safe(user)}})
