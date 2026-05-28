"""
CORE responses.py — Standardized JSON response helpers for all API routes.

Layer: core
Pattern: Factory functions

Key exports:
  - success(data, message, status): returns {"success": True, "message": ..., "data": ...} tuple
  - error(message, status, error_code): returns {"success": False, "error": ..., "error_code"?: ...} tuple

Constraints:
  - All route handlers must use success() or error() — never call jsonify() directly in routes
  - "data" key is omitted when data=None to keep responses minimal
  - "error_code" key is omitted when not provided; use it for machine-readable error identifiers

Related: app/core/exceptions.py, app/core/middleware.py (error handler also uses jsonify directly)
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
