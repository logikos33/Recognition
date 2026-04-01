from flask import Blueprint
streams_bp = Blueprint('streams', __name__, url_prefix='/api/streams')
from . import routes  # noqa
