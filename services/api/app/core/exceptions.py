"""
CORE exceptions.py — Custom exception hierarchy for Recognition.

Layer: core
Pattern: Exception hierarchy

Key exports:
  - sanitize_client_message: troca a mensagem por texto de gente quando ela carrega
    tripa técnica (SQL, nome de schema, psycopg, traceback, string de conexão)
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
import re

# ── Guarda de vazamento de tripa (issues #799/#800) ─────────────────────────
# MEDIDO no DEV, numa janela de deploy: as telas do EPI imprimiam para o
# usuário o SQL cru da query que falhou e o nome interno do schema do tenant
# (`rvb_isolantes`), além de um `503 connection pool exhausted` em inglês.
# Isso é três problemas de uma vez: jargão na cara do cliente, vazamento de
# estrutura interna (que schema/tabela/coluna existem) e a pior primeira
# impressão possível.
#
# A regra é: o DETALHE vai para o log (o time precisa dele), a RESPOSTA leva
# uma frase de gente. Quando um destes padrões aparece, a mensagem inteira é
# trocada — nunca redigida por partes, que é como sobra metade do SELECT na
# tela.
_TECHNICAL_LEAK = re.compile(
    r"""
      \b(?:select|insert|update|delete|drop|truncate|alter|create|grant)\b
      [\s\S]{0,120}?
      \b(?:from|into|table|set|where|values|join|returning)\b
    | search_path
    | \bschemas?\b
    | \bpsycopg\w*
    | \bsqlalchemy\b
    | \btraceback\b
    | ^\s*File\s+"
    | \.py["']?[,:]?\s*line\s+\d+
    | \b[a-z][a-z0-9+.\-]*://[^\s/@]*:[^\s/@]*@          # senha em URL
    | \b(?:postgres|postgresql|mysql|mongodb|redis|amqp)://
    | \bconnection\s+pool\b
    | \bpool\s+(?:exhausted|timeout|esgotad\w*)
    | \bpool\s+de\s+conex\w*
    | \brelation\s+"
    | \bcolumn\s+"
    | \bduplicate\s+key\s+value\b
    | violates\s+\w+\s+constraint
    | ^\s*(?:DETAIL|HINT|CONTEXT|LINE\s+\d+)\s*:
    | \bcursor\b[\s\S]{0,20}\bexecute\b
    | \bconnection\s+(?:refused|already\s+closed|unexpectedly)
    | \bserver\s+closed\s+the\s+connection\b
    | \bcould\s+not\s+connect\s+to\s+server\b
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

# Sem número de HTTP: "503" não diz nada para quem opera a fábrica.
_GENERIC_CLIENT_ERROR = (
    "Não foi possível concluir esta ação. Confira os dados e tente de novo."
)
_GENERIC_SERVER_ERROR = (
    "O sistema não conseguiu responder agora. Tente de novo em instantes."
)


def leaks_internals(message: str) -> bool:
    """True quando a mensagem carrega tripa que não pode chegar ao cliente."""
    return bool(message) and bool(_TECHNICAL_LEAK.search(message))


def sanitize_client_message(message: str, status_code: int = 500) -> str:
    """Mensagem segura para o corpo da resposta.

    No-op quando a mensagem já é de gente — só troca quando detecta tripa.
    Nunca engole o erro: o usuário continua sabendo que falhou e o que fazer.
    """
    if not message:
        return _GENERIC_SERVER_ERROR if status_code >= 500 else _GENERIC_CLIENT_ERROR
    if not leaks_internals(message):
        return message
    return _GENERIC_SERVER_ERROR if status_code >= 500 else _GENERIC_CLIENT_ERROR


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
    """Erros de RunPod, YOLOv8 training — retorna 500."""

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
