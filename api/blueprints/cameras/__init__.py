from flask import Blueprint
cameras_bp = Blueprint('cameras', __name__, url_prefix='/api/cameras')
from . import routes  # noqa
