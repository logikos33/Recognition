"""Respostas padronizadas da API."""
from flask import jsonify
from typing import Any


def success(data: Any = None, message: str = None, status: int = 200):
    resp = {'success': True}
    if data is not None:
        resp['data'] = data
    if message:
        resp['message'] = message
    return jsonify(resp), status


def error(message: str, status: int = 400):
    return jsonify({'success': False, 'error': message}), status
