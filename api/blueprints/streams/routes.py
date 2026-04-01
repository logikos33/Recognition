"""Status de streams e workers. Sem JWT — health check interno."""
from flask import jsonify
from . import streams_bp
from api.utils.worker_proxy import get_workers_health


@streams_bp.route('/status', methods=['GET'])
def streams_status():
    workers = get_workers_health()
    return jsonify({
        'success': True,
        'workers': workers,
        'total_workers': len(workers),
        'mode': 'distributed' if workers else 'local'
    })
