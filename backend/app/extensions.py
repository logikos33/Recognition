"""
EPI Monitor V2 — Flask extensions initialization.

Extensions criadas aqui, inicializadas no create_app().
SocketIO usa message_queue=REDIS_URL para escalar entre workers Railway.
Limiter usa Redis storage em prod, memory:// em dev/test.
"""
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_socketio import SocketIO

jwt = JWTManager()
socketio = SocketIO()
limiter = Limiter(key_func=get_remote_address, default_limits=[])
