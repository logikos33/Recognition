"""
CORE exceptions.py — Custom exception hierarchy for Recognition.

Layer: core
Pattern: Exception hierarchy

Key exports:
  - EpiMonitorError: base class carrying message + status_code for unified error handling
  - ValidationError(400), AuthenticationError(401), AuthorizationError(403)
  - NotFoundError(404), ConflictError(409), StorageError(502)
  - DatabaseError(503), TrainingError(500), InferenceError(500), StreamError(500)

Constraints:
  - All domain exceptions must subclass EpiMonitorError so middleware.register_error_handlers catches them
  - Never expose stack traces or internal details in exception messages — middleware handles logging
  - NotFoundError accepts resource + resource_id for consistent "X not found (id)" messages

Related: app/core/middleware.py (handler), app/core/responses.py (error format)
"""


class EpiMonitorError(Exception):
    """Base exception para todo o sistema Recognition."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ValidationError(EpiMonitorError):
    """Inputs inválidos — retorna 400."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class AuthenticationError(EpiMonitorError):
    """JWT inválido, credenciais erradas — retorna 401."""

    def __init__(self, message: str = "Credenciais inválidas") -> None:
        super().__init__(message, status_code=401)


class AuthorizationError(EpiMonitorError):
    """Sem permissão para o recurso — retorna 403."""

    def __init__(self, message: str = "Sem permissão") -> None:
        super().__init__(message, status_code=403)


class NotFoundError(EpiMonitorError):
    """Recurso não encontrado — retorna 404."""

    def __init__(self, resource: str, resource_id: str = "") -> None:
        detail = f" ({resource_id})" if resource_id else ""
        super().__init__(f"{resource} não encontrado{detail}", status_code=404)


class ConflictError(EpiMonitorError):
    """Recurso já existe — retorna 409."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)


class StorageError(EpiMonitorError):
    """Erros de R2/S3, operações de arquivo — retorna 502."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=502)


class DatabaseError(EpiMonitorError):
    """Wrapper para erros psycopg2 — retorna 503."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class TrainingError(EpiMonitorError):
    """Erros de Vast.ai, YOLOv8 training — retorna 500."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class InferenceError(EpiMonitorError):
    """Erros de runtime de detecção YOLO — retorna 500."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class StreamError(EpiMonitorError):
    """Erros de FFmpeg/HLS stream — retorna 500."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)
