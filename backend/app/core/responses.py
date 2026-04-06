"""
EPI Monitor V2 — Standardized JSON responses.

Toda response da API usa estas funções — nunca jsonify() direto nas routes.
"""
from typing import Any

from flask import jsonify


def success(
    data: Any = None,
    message: str = "OK",
    status: int = 200,
) -> tuple:
    """Response padronizada de sucesso."""
    body: dict[str, Any] = {"success": True, "message": message}
    if data is not None:
        body["data"] = data
    return jsonify(body), status


def error(
    message: str = "Erro interno",
    status: int = 400,
    error_code: str | None = None,
) -> tuple:
    """Response padronizada de erro."""
    body: dict[str, Any] = {"success": False, "error": message}
    if error_code:
        body["error_code"] = error_code
    return jsonify(body), status
