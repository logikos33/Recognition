"""
EPI Monitor V2 — Flask extensions initialization.

Extensions criadas aqui, inicializadas no create_app().
SocketIO usa message_queue=REDIS_URL para escalar entre workers Railway.
"""
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO

jwt = JWTManager()
socketio = SocketIO()
