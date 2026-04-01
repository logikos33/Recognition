"""
Cameras CRUD + stream control.
Senhas SEMPRE criptografadas — NUNCA retornadas na API.
"""
import os, traceback
from flask import request, current_app
from flask_jwt_extended import jwt_required
from cryptography.fernet import Fernet
from . import cameras_bp
from api.utils.auth import get_current_user
from api.utils.responses import success, error
from api.utils import worker_proxy
from services.shared.database import get_db_connection


def _fernet():
    key = os.environ.get('CAMERA_SECRET_KEY', '')
    if not key:
        raise ValueError("CAMERA_SECRET_KEY não configurada")
    return Fernet(key.encode() if isinstance(key, str) else key)


def _enc(pwd: str) -> str:
    return _fernet().encrypt(pwd.encode()).decode()


def _dec(enc: str) -> str:
    try:
        return _fernet().decrypt(enc.encode()).decode()
    except Exception:
        return ''


@cameras_bp.route('', methods=['GET'])
@jwt_required()
def list_cameras():
    try:
        user = get_current_user()
        with get_db_connection() as conn:
            cur = conn.cursor()
            if user['role'] == 'admin':
                cur.execute(
                    "SELECT id,name,location,manufacturer,host,port,channel,"
                    "is_active,last_seen,created_at FROM ip_cameras ORDER BY created_at DESC"
                )
            else:
                cur.execute(
                    "SELECT id,name,location,manufacturer,host,port,channel,"
                    "is_active,last_seen,created_at FROM ip_cameras "
                    "WHERE user_id=%s ORDER BY created_at DESC",
                    (str(user['id']),)
                )
            cameras = [dict(r) for r in cur.fetchall()]

        for cam in cameras:
            cam['id'] = str(cam['id'])
            status = worker_proxy.get_stream_status(cam['id'])
            cam['stream_status'] = status.get('status', 'stopped')

        return success(cameras)
    except Exception:
        current_app.logger.error(traceback.format_exc())
        return error('Erro interno', 500)


@cameras_bp.route('', methods=['POST'])
@jwt_required()
def create_camera():
    try:
        user = get_current_user()
        data = request.get_json() or {}
        if not data.get('name') or not data.get('host'):
            return error('name e host são obrigatórios')

        pwd_enc = _enc(data['password']) if data.get('password') else None

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO ip_cameras
                  (user_id,name,location,description,manufacturer,
                   host,port,username,password_encrypted,channel,subtype)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id,name,location,manufacturer,host,port,channel,is_active
            """, (
                str(user['id']), data['name'], data.get('location'),
                data.get('description'), data.get('manufacturer', 'generic'),
                data['host'], data.get('port', 554),
                data.get('username', 'admin'), pwd_enc,
                data.get('channel', 1), data.get('subtype', 0)
            ))
            cam = dict(cur.fetchone())
            cam['id'] = str(cam['id'])

        return success(cam, status=201)
    except Exception:
        current_app.logger.error(traceback.format_exc())
        return error('Erro interno', 500)


@cameras_bp.route('/<camera_id>/stream/start', methods=['POST'])
@jwt_required()
def start_stream(camera_id):
    try:
        user = get_current_user()
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM ip_cameras WHERE id=%s", (camera_id,))
            cam = cur.fetchone()
        if not cam:
            return error('Câmera não encontrada', 404)
        if str(cam['user_id']) != str(user['id']) and user['role'] != 'admin':
            return error('Sem permissão', 403)

        password = _dec(cam['password_encrypted'] or '')
        rtsp_url = (
            cam.get('rtsp_url_override') or
            f"rtsp://{cam['username']}:{password}@{cam['host']}:{cam['port']}"
            f"/cam/realmonitor?channel={cam['channel']}&subtype={cam['subtype']}"
        )

        result = worker_proxy.start_stream(camera_id, rtsp_url)
        return success(result) if result['success'] else error(result.get('error', 'Erro'))
    except Exception:
        current_app.logger.error(traceback.format_exc())
        return error('Erro interno', 500)


@cameras_bp.route('/<camera_id>/stream/stop', methods=['POST'])
@jwt_required()
def stop_stream(camera_id):
    result = worker_proxy.stop_stream(camera_id)
    return success({'stopped': True})


@cameras_bp.route('/<camera_id>/stream/status', methods=['GET'])
@jwt_required()
def stream_status(camera_id):
    return success(worker_proxy.get_stream_status(camera_id))
