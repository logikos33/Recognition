"""
Recognition — autenticação do handshake SocketIO + rooms por tenant.

Por que existe
--------------
python-socketio ≥ 5 só aceita conexão a um namespace que tenha handler
registrado (ou esteja em ``namespaces=``). Até este módulo, ``create_app()`` não
registrava handler nenhum: ``/monitor``, ``/training`` e ``/quality`` eram
RECUSADOS e todo o tempo real do front rodava no vazio (PR #523, A1). E o
bridge emitia em broadcast no namespace — quando as conexões passassem a
aceitar, um tenant veria detecções do outro (C-01, A2).

Contrato com o cliente
----------------------
* Namespaces aceitos: ``/monitor``, ``/training``, ``/quality``. ``/admin`` NÃO
  é registrado (ninguém emite nele; o hook do front está morto) — continua
  recusado de propósito.
* JWT obrigatório no handshake. Fontes, nesta ordem:
  1. ``auth: {token}`` do socket.io-client (recomendado — não vai para a URL);
  2. ``?token=`` na query (compatibilidade com os hooks atuais; desencorajado,
     o token vaza para logs de acesso).
  Mesmo token Bearer da REST (HS256, claims ``tenant_id``/``tenant_schema``/
  ``role``…). Validação = assinatura + expiração + **blocklist** (logout /
  sessão revogada), igual a ``@jwt_required``.
* Sem token, token inválido/expirado/revogado ou sem claim ``tenant_schema``
  (ADR-0017: sem fallback de tenant) → ``ConnectionRefusedError`` com motivo
  curto (``auth_required`` / ``invalid_token`` / ``tenant_required``); o cliente
  recebe ``connect_error``.
* Conexão aceita entra na room ``tenant:<tenant_schema>`` do namespace. O bridge
  (app/core/socket_bridge.py) só emite ``to=`` essa room — nunca broadcast.

Superadmin sem contexto de tenant assumido tem token SEM ``tenant_schema``
(conforme o login) → recusado aqui. É o comportamento seguro por padrão; uma
room "plataforma" para superadmin é decisão de produto futura, não deste PR.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

ROOM_NAMESPACES: tuple[str, ...] = ("/monitor", "/training", "/quality")


def tenant_room(tenant_schema: str) -> str:
    """Nome da room do tenant (mesmo nome em todos os namespaces)."""
    return f"tenant:{tenant_schema}"


def _extract_token(auth: Any, query_token: str | None) -> str | None:
    if isinstance(auth, dict):
        token = auth.get("token")
        if isinstance(token, str) and token:
            return token
    if isinstance(query_token, str) and query_token:
        return query_token
    return None


def authenticate_handshake(auth: Any, query_token: str | None) -> dict[str, Any]:
    """Valida o JWT do handshake e devolve as claims.

    Levanta ``ConnectionRefusedError(reason)`` em qualquer falha. Precisa de
    app context (usa a config do Flask-JWT-Extended) — o flask-socketio garante
    isso dentro dos handlers.
    """
    from flask_jwt_extended import decode_token  # noqa: PLC0415
    from flask_jwt_extended.exceptions import JWTExtendedException  # noqa: PLC0415
    from flask_jwt_extended.internal_utils import (  # noqa: PLC0415
        verify_token_not_blocklisted,
    )
    from flask_socketio import ConnectionRefusedError  # noqa: PLC0415
    from jwt import PyJWTError, get_unverified_header  # noqa: PLC0415

    token = _extract_token(auth, query_token)
    if not token:
        raise ConnectionRefusedError("auth_required")
    try:
        claims = decode_token(token)
        # decode_token NÃO consulta a blocklist (docstring do próprio
        # Flask-JWT-Extended); o loader registrado em app/__init__.py é o mesmo
        # que protege a REST — reaproveitado aqui (helper interno, mas estável
        # em 4.x; se mudar de lugar o teste de token revogado acusa).
        verify_token_not_blocklisted(get_unverified_header(token), claims)
    except (JWTExtendedException, PyJWTError, ValueError) as exc:
        logger.info("socket_handshake_rejected: reason=invalid_token err=%s", type(exc).__name__)
        raise ConnectionRefusedError("invalid_token") from exc
    tenant_schema = claims.get("tenant_schema")
    if not tenant_schema:
        logger.info("socket_handshake_rejected: reason=tenant_required sub=%s", claims.get("sub"))
        raise ConnectionRefusedError("tenant_required")
    return claims


def register_socket_namespaces(socketio) -> None:  # type: ignore[no-untyped-def]
    """Registra o handler ``connect`` (JWT + join_room) em cada namespace.

    Chamado em ``create_app()`` logo após ``socketio.init_app`` — inclusive em
    TESTING, para a suíte cobrir recusa/aceite/isolamento.
    """
    from flask import request  # noqa: PLC0415
    from flask_socketio import join_room  # noqa: PLC0415

    def _make_handler(namespace: str):
        def _on_connect(auth: Any = None) -> None:
            claims = authenticate_handshake(auth, request.args.get("token"))
            room = tenant_room(claims["tenant_schema"])
            join_room(room)
            logger.info(
                "socket_connected: ns=%s room=%s sub=%s role=%s",
                namespace, room, claims.get("sub"), claims.get("role"),
            )

        _on_connect.__name__ = f"on_connect_{namespace.strip('/')}"
        return _on_connect

    for ns in ROOM_NAMESPACES:
        socketio.on_event("connect", _make_handler(ns), namespace=ns)
    logger.info("socket_namespaces_registered: %s", ROOM_NAMESPACES)
