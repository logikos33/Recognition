"""
Tests: rotas e handlers de classes do tenant (WS-A1).

- GET/POST /api/classes (já wired em training/routes.py) → Flask test client.
- PUT/DELETE /api/classes/<id> → handler-level (test_request_context) SEMPRE;
  client-level roda quando o orquestrador colar o wiring (skip automático
  enquanto a rota não existe no url_map).

Contrato AnnotationInterface.jsx preservado: GET → {success, classes: [...]}
com id, name, color por item.
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token

from app.core.exceptions import ConflictError, NotFoundError, ValidationError

_HANDLERS = "app.api.v1.training.annotation_handlers"


def _make_token(app, role="operator", tenant_id=None, user_id=None):
    uid = user_id or uuid4()
    tid = tenant_id or str(uuid4())
    with app.app_context():
        token = create_access_token(
            identity=str(uid),
            additional_claims={
                "role": role,
                "tenant_id": tid,
                "tenant_schema": "public",
            },
        )
    return token, uid, tid


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _route_registered(app, rule: str, method: str) -> bool:
    return any(
        r.rule == rule and method in (r.methods or set())
        for r in app.url_map.iter_rules()
    )


def _skip_unless_wired(app, method: str):
    if not _route_registered(app, "/api/classes/<int:class_id>", method):
        pytest.skip(
            f"{method} /api/classes/<id> aguardando wiring do orquestrador"
        )


# ---------------------------------------------------------------------------
# GET /api/classes
# ---------------------------------------------------------------------------

class TestGetClasses:
    def test_returns_annotation_interface_contract(self, client, app):
        token, _uid, _tid = _make_token(app)
        mock_svc = MagicMock()
        mock_svc.list_classes.return_value = [
            {"id": 1, "name": "Capacete", "color": "#22c55e",
             "module_code": "epi"},
        ]
        with patch(f"{_HANDLERS}.get_tenant_class_service", return_value=mock_svc):
            res = client.get("/api/classes", headers=_headers(token))

        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        cls = data["classes"][0]
        assert cls["id"] == 1
        assert cls["name"] == "Capacete"
        assert cls["color"] == "#22c55e"

    def test_passes_tenant_module_and_counts(self, client, app):
        token, uid, tid = _make_token(app)
        mock_svc = MagicMock()
        mock_svc.list_classes.return_value = []
        with patch(f"{_HANDLERS}.get_tenant_class_service", return_value=mock_svc):
            res = client.get(
                "/api/classes?module=fueling&include_counts=true",
                headers=_headers(token),
            )

        assert res.status_code == 200
        kwargs = mock_svc.list_classes.call_args.kwargs
        args = mock_svc.list_classes.call_args.args
        assert args[0] == tid
        assert str(kwargs["user_id"]) == str(uid)
        assert kwargs["module_code"] == "fueling"
        assert kwargs["include_counts"] is True

    def test_include_counts_defaults_false(self, client, app):
        token, _uid, _tid = _make_token(app)
        mock_svc = MagicMock()
        mock_svc.list_classes.return_value = []
        with patch(f"{_HANDLERS}.get_tenant_class_service", return_value=mock_svc):
            client.get("/api/classes", headers=_headers(token))
        kwargs = mock_svc.list_classes.call_args.kwargs
        assert kwargs["include_counts"] is False
        assert kwargs["module_code"] == "epi"

    def test_no_jwt_returns_401(self, client):
        res = client.get("/api/classes")
        assert res.status_code in (401, 422)

    def test_service_error_returns_500(self, client, app):
        token, _uid, _tid = _make_token(app)
        mock_svc = MagicMock()
        mock_svc.list_classes.side_effect = RuntimeError("DB down")
        with patch(f"{_HANDLERS}.get_tenant_class_service", return_value=mock_svc):
            res = client.get("/api/classes", headers=_headers(token))
        assert res.status_code == 500


# ---------------------------------------------------------------------------
# POST /api/classes
# ---------------------------------------------------------------------------

class TestCreateClass:
    def test_create_ok_201(self, client, app):
        # admin: passa também quando o wiring adicionar require_training_role
        token, uid, tid = _make_token(app, role="admin")
        mock_svc = MagicMock()
        mock_svc.create_class.return_value = {
            "id": 3, "name": "Luva", "color": "#3b82f6", "module_code": "epi",
        }
        with patch(f"{_HANDLERS}.get_tenant_class_service", return_value=mock_svc):
            res = client.post(
                "/api/classes",
                json={"name": "Luva", "color": "#3b82f6", "module": "epi"},
                headers=_headers(token),
            )

        assert res.status_code == 201
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["name"] == "Luva"
        kwargs = mock_svc.create_class.call_args.kwargs
        assert kwargs["tenant_id"] == tid
        assert str(kwargs["user_id"]) == str(uid)
        assert kwargs["module_code"] == "epi"

    def test_create_validation_error_400(self, client, app):
        token, _uid, _tid = _make_token(app, role="admin")
        mock_svc = MagicMock()
        mock_svc.create_class.side_effect = ValidationError(
            "Nome da classe é obrigatório"
        )
        with patch(f"{_HANDLERS}.get_tenant_class_service", return_value=mock_svc):
            res = client.post(
                "/api/classes", json={"name": ""}, headers=_headers(token)
            )
        assert res.status_code == 400
        assert res.get_json()["success"] is False

    def test_create_duplicate_409(self, client, app):
        token, _uid, _tid = _make_token(app, role="admin")
        mock_svc = MagicMock()
        mock_svc.create_class.side_effect = ConflictError("Classe já existe")
        with patch(f"{_HANDLERS}.get_tenant_class_service", return_value=mock_svc):
            res = client.post(
                "/api/classes", json={"name": "Capacete"}, headers=_headers(token)
            )
        assert res.status_code == 409


# ---------------------------------------------------------------------------
# PUT/DELETE /api/classes/<id> — handler-level (independe do wiring)
# ---------------------------------------------------------------------------

class TestUpdateClassHandler:
    def test_update_ok(self, app):
        from app.api.v1.training.annotation_handlers import update_class_handler

        uid = uuid4()
        tid = str(uuid4())
        mock_svc = MagicMock()
        mock_svc.update_class.return_value = {
            "id": 5, "name": "Colete", "color": "#f59e0b",
        }
        with app.test_request_context(
            "/api/classes/5", method="PUT", json={"name": "Colete"}
        ), patch(f"{_HANDLERS}.get_current_user_id", return_value=uid), \
             patch(f"{_HANDLERS}.get_tenant_id", return_value=tid), \
             patch(f"{_HANDLERS}.get_tenant_class_service", return_value=mock_svc):
            response, status = update_class_handler(5)

        assert status == 200
        body = response.get_json()
        assert body["success"] is True
        assert body["data"]["name"] == "Colete"
        mock_svc.update_class.assert_called_once_with(
            5, tid, user_id=uid, name="Colete", color=None
        )

    def test_update_not_found_propagates_404(self, app):
        from app.api.v1.training.annotation_handlers import update_class_handler

        mock_svc = MagicMock()
        mock_svc.update_class.side_effect = NotFoundError("Classe", "99")
        with app.test_request_context(
            "/api/classes/99", method="PUT", json={"name": "X"}
        ), patch(f"{_HANDLERS}.get_current_user_id", return_value=uuid4()), \
             patch(f"{_HANDLERS}.get_tenant_id", return_value=str(uuid4())), \
             patch(f"{_HANDLERS}.get_tenant_class_service", return_value=mock_svc):
            with pytest.raises(NotFoundError) as exc_info:
                update_class_handler(99)
        # middleware.register_error_handlers converte em 404 JSON
        assert exc_info.value.status_code == 404


class TestDeleteClassHandler:
    def test_delete_ok(self, app):
        from app.api.v1.training.annotation_handlers import delete_class_handler

        uid = uuid4()
        tid = str(uuid4())
        mock_svc = MagicMock()
        mock_svc.delete_class.return_value = {"id": 5, "name": "Colete"}
        with app.test_request_context("/api/classes/5", method="DELETE"), \
             patch(f"{_HANDLERS}.get_current_user_id", return_value=uid), \
             patch(f"{_HANDLERS}.get_tenant_id", return_value=tid), \
             patch(f"{_HANDLERS}.get_tenant_class_service", return_value=mock_svc):
            response, status = delete_class_handler(5)

        assert status == 200
        body = response.get_json()
        assert body["success"] is True
        assert body["data"]["deleted"] is True
        assert body["data"]["id"] == 5
        mock_svc.delete_class.assert_called_once_with(5, tid, user_id=uid)

    def test_delete_referenced_propagates_409(self, app):
        from app.api.v1.training.annotation_handlers import delete_class_handler

        mock_svc = MagicMock()
        mock_svc.delete_class.side_effect = ConflictError(
            "Classe possui 3 anotações vinculadas"
        )
        with app.test_request_context("/api/classes/5", method="DELETE"), \
             patch(f"{_HANDLERS}.get_current_user_id", return_value=uuid4()), \
             patch(f"{_HANDLERS}.get_tenant_id", return_value=str(uuid4())), \
             patch(f"{_HANDLERS}.get_tenant_class_service", return_value=mock_svc):
            with pytest.raises(ConflictError) as exc_info:
                delete_class_handler(5)
        assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# PUT/DELETE /api/classes/<id> — client-level (roda após wiring; skip antes)
# ---------------------------------------------------------------------------

class TestUpdateDeleteRoutesWired:
    def test_put_update_ok(self, client, app):
        _skip_unless_wired(app, "PUT")
        token, _uid, _tid = _make_token(app, role="admin")
        mock_svc = MagicMock()
        mock_svc.update_class.return_value = {"id": 5, "name": "Novo"}
        with patch(f"{_HANDLERS}.get_tenant_class_service", return_value=mock_svc):
            res = client.put(
                "/api/classes/5", json={"name": "Novo"}, headers=_headers(token)
            )
        assert res.status_code == 200
        assert res.get_json()["data"]["name"] == "Novo"

    def test_put_other_tenant_404(self, client, app):
        _skip_unless_wired(app, "PUT")
        token, _uid, _tid = _make_token(app, role="admin")
        mock_svc = MagicMock()
        mock_svc.update_class.side_effect = NotFoundError("Classe", "99")
        with patch(f"{_HANDLERS}.get_tenant_class_service", return_value=mock_svc):
            res = client.put(
                "/api/classes/99", json={"name": "X"}, headers=_headers(token)
            )
        assert res.status_code == 404

    def test_delete_referenced_409(self, client, app):
        _skip_unless_wired(app, "DELETE")
        token, _uid, _tid = _make_token(app, role="admin")
        mock_svc = MagicMock()
        mock_svc.delete_class.side_effect = ConflictError(
            "Classe possui 3 anotações vinculadas"
        )
        with patch(f"{_HANDLERS}.get_tenant_class_service", return_value=mock_svc):
            res = client.delete("/api/classes/5", headers=_headers(token))
        assert res.status_code == 409

    def test_mutation_denied_for_operator_without_override(self, client, app):
        """require_training_role('write'): operator sem override → 403."""
        _skip_unless_wired(app, "DELETE")
        token, _uid, _tid = _make_token(app, role="operator")
        mock_svc = MagicMock()
        with patch(f"{_HANDLERS}.get_tenant_class_service", return_value=mock_svc):
            res = client.delete("/api/classes/5", headers=_headers(token))
        assert res.status_code == 403
        mock_svc.delete_class.assert_not_called()
