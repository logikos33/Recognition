"""
Tests: app/core/socket_auth.py — handshake SocketIO com JWT + room por tenant.

Guarda de regressão do achado A1/A2 do mapa de migração (PR #523): sem handler
de connect o python-socketio recusa os namespaces; com handler sem JWT/room o
broadcast vaza entre tenants (C-01). Usa o test client do flask-socketio (modo
threading em TESTING) — sem Redis.
"""
from unittest.mock import patch

import pytest
from flask_jwt_extended import create_access_token

from app.core.socket_auth import ROOM_NAMESPACES, tenant_room
from app.extensions import socketio


def _token(app, tenant_schema="rvb", role="admin", **extra):
    with app.app_context():
        claims = {"role": role, **extra}
        if tenant_schema:
            claims["tenant_schema"] = tenant_schema
            claims["tenant_id"] = f"tid-{tenant_schema}"
        return create_access_token(identity=f"user-{tenant_schema}", additional_claims=claims)


@pytest.fixture
def connect(app):
    clients = []

    def _connect(namespace, **kwargs):
        c = socketio.test_client(app, namespace=namespace, **kwargs)
        clients.append(c)
        return c

    yield _connect
    for c in clients:
        try:
            c.disconnect()
        except Exception:  # noqa: BLE001
            pass


class TestRecusa:

    @pytest.mark.parametrize("ns", ROOM_NAMESPACES)
    def test_sem_token_e_recusado(self, connect, ns):
        assert connect(ns).is_connected(ns) is False

    def test_token_invalido_e_recusado(self, connect):
        assert connect("/monitor", auth={"token": "nao.e.jwt"}).is_connected("/monitor") is False

    def test_token_sem_tenant_schema_e_recusado(self, app, connect):
        """ADR-0017: sem claim de tenant não há fallback — superadmin sem contexto inclusive."""
        tok = _token(app, tenant_schema=None, role="superadmin")
        assert connect("/monitor", auth={"token": tok}).is_connected("/monitor") is False

    def test_token_revogado_e_recusado(self, app, connect):
        """decode_token não consulta a blocklist; o handshake tem de consultar (logout/sessão revogada)."""
        tok = _token(app)
        with patch("app.domain.services.session_service.is_jti_revoked", return_value=True):
            assert connect("/monitor", auth={"token": tok}).is_connected("/monitor") is False

    def test_namespace_admin_continua_recusado_mesmo_com_jwt(self, app, connect):
        """/admin não é registrado de propósito (ninguém emite nele)."""
        tok = _token(app, role="superadmin")
        assert connect("/admin", auth={"token": tok}).is_connected("/admin") is False


class TestAceite:

    @pytest.mark.parametrize("ns", ROOM_NAMESPACES)
    def test_auth_token_conecta(self, app, connect, ns):
        tok = _token(app)
        assert connect(ns, auth={"token": tok}).is_connected(ns) is True

    def test_query_token_conecta_compatibilidade(self, app, connect):
        """Os hooks atuais do front mandam ?token= — aceito por compatibilidade."""
        tok = _token(app)
        assert connect("/monitor", query_string=f"token={tok}").is_connected("/monitor") is True

    def test_auth_tem_precedencia_sobre_query(self, app, connect):
        tok = _token(app)
        c = connect("/monitor", auth={"token": tok}, query_string="token=lixo")
        assert c.is_connected("/monitor") is True

    def test_conexao_entra_na_room_do_tenant(self, app, connect):
        tok = _token(app, tenant_schema="rvb")
        c = connect("/monitor", auth={"token": tok})
        socketio.emit("detection", {"camera_id": "c1"}, namespace="/monitor", to=tenant_room("rvb"))
        assert [m["name"] for m in c.get_received("/monitor")] == ["detection"]


class TestIsolamentoEntreTenants:
    """Evento emitido para a room do tenant A não chega ao socket do tenant B."""

    @pytest.mark.parametrize("ns,event", [("/monitor", "detection"), ("/quality", "quality_inspection"), ("/training", "training_progress")])
    def test_evento_do_tenant_a_nao_chega_no_b(self, app, connect, ns, event):
        a = connect(ns, auth={"token": _token(app, tenant_schema="rvb")})
        b = connect(ns, auth={"token": _token(app, tenant_schema="acme")})
        assert a.is_connected(ns) and b.is_connected(ns)

        socketio.emit(event, {"x": 1}, namespace=ns, to=tenant_room("rvb"))

        assert [m["name"] for m in a.get_received(ns)] == [event]
        assert b.get_received(ns) == []

    def test_broadcast_sem_room_chegaria_nos_dois(self, app, connect):
        """Documenta POR QUE o bridge nunca pode emitir sem `to=`: o namespace é compartilhado."""
        a = connect("/monitor", auth={"token": _token(app, tenant_schema="rvb")})
        b = connect("/monitor", auth={"token": _token(app, tenant_schema="acme")})
        socketio.emit("detection", {"x": 1}, namespace="/monitor")  # ← o que o bridge NÃO faz mais
        assert a.get_received("/monitor") and b.get_received("/monitor")

    def test_rooms_sao_por_namespace(self, app, connect):
        """Room `tenant:rvb` em /monitor não entrega em /quality e vice-versa."""
        mon = connect("/monitor", auth={"token": _token(app, tenant_schema="rvb")})
        qual = connect("/quality", auth={"token": _token(app, tenant_schema="rvb")})
        socketio.emit("quality_inspection", {"x": 1}, namespace="/quality", to=tenant_room("rvb"))
        assert qual.get_received("/quality") and mon.get_received("/monitor") == []
