"""
Regressão — admin de TENANT não é superadmin: câmeras escopadas pelo JWT (C-01).

Achado (b) do mapa de migração, grupo CÂMERAS: `_is_admin`
(app/api/v1/cameras/helpers.py) devolvia True para role 'admin' (admin de
tenant) e era usado como override GLOBAL em list/get/update/delete/start/
test de câmeras — GET /api/cameras com admin de B listava as câmeras de
TODOS os tenants (CameraRepository.get_all) e get/update/delete/start
aceitavam camera_id de outro tenant.

FALHA antes do fix / PASSA depois:
  - admin de B → só câmeras de B; câmera de A → 404 (nunca 403/200);
  - superadmin mantém a visão global (e o contexto assumido continua
    funcionando — a identidade do token segue sendo o superadmin);
  - admin de A continua operando as PRÓPRIAS câmeras (start/test passam
    get_tenant_id() ao service, não o user_id — antes só funcionava via o
    override indevido).
"""
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

import app.api.v1.cameras.crud_handlers as crud_handlers
import app.api.v1.cameras.helpers as cam_helpers
import app.api.v1.cameras.stream_handlers as stream_handlers
import app.api.v1.cameras.test_handler as test_handler
from app.core.exceptions import NotFoundError
from app.domain.services.camera_service import CameraService

from ._helpers_tenant import make_user_jwt

TENANT_A = str(uuid4())
TENANT_B = str(uuid4())
CAM_A = str(uuid4())
CAM_B = str(uuid4())

ADMIN_A = str(uuid4())
ADMIN_B = str(uuid4())
SUPER = str(uuid4())
# users.role — o que _is_admin lê do banco (espelha a claim 'role' do JWT).
ROLES = {ADMIN_A: "admin", ADMIN_B: "admin", SUPER: "superadmin"}


def _cam(cam_id: str, tenant_id: str) -> dict:
    return {
        "id": cam_id,
        "tenant_id": tenant_id,
        "name": f"cam-{tenant_id[:4]}",
        "host": "10.0.0.5",
        "port": 554,
        "manufacturer": "generic",
        "rtsp_url_override": "rtsp://10.0.0.5:554/stream1",
        "site_id": None,
    }


CAMS = {CAM_A: _cam(CAM_A, TENANT_A), CAM_B: _cam(CAM_B, TENANT_B)}


def _hdr(app, user_id: str, tenant_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_user_jwt(app, tenant_id, ROLES[user_id], user_id)}"}


@pytest.fixture()
def camera_repo(monkeypatch):
    """CameraService REAL sobre repositório mockado; _is_admin REAL sobre users mockado."""
    repo = MagicMock()
    repo.get_by_id.side_effect = lambda cid: dict(CAMS.get(str(cid)) or {}) or None
    repo.get_all.return_value = [dict(c) for c in CAMS.values()]
    repo.get_by_user.side_effect = lambda tid: [
        dict(c) for c in CAMS.values() if c["tenant_id"] == str(tid)
    ]
    repo.update.side_effect = lambda cid, data: {**CAMS[str(cid)], **data}
    service = CameraService(repo, fernet_key="")
    for mod in (crud_handlers, stream_handlers, test_handler):
        monkeypatch.setattr(mod, "_get_camera_service", lambda: service)
    monkeypatch.setattr(crud_handlers, "_get_redis", lambda: MagicMock(get=lambda *_: None))

    users = MagicMock()
    users.get_by_id.side_effect = lambda uid: {"id": str(uid), "role": ROLES[str(uid)]}
    with patch.object(cam_helpers, "DatabasePool") as pool_cls, \
         patch.object(cam_helpers, "UserRepository", return_value=users):
        pool_cls.get_instance.return_value = MagicMock()
        yield repo


class TestListCamerasAdminScope:
    def test_tenant_admin_sees_only_own_tenant(self, app, client, camera_repo):
        resp = client.get("/api/cameras", headers=_hdr(app, ADMIN_B, TENANT_B))
        assert resp.status_code == 200
        ids = {c["id"] for c in resp.get_json()["data"]["cameras"]}
        assert ids == {CAM_B}, f"admin de tenant listou câmeras de outro tenant: {ids}"
        camera_repo.get_all.assert_not_called()

    def test_superadmin_keeps_global_view(self, app, client, camera_repo):
        resp = client.get("/api/cameras", headers=_hdr(app, SUPER, TENANT_A))
        assert resp.status_code == 200
        ids = {c["id"] for c in resp.get_json()["data"]["cameras"]}
        assert ids == {CAM_A, CAM_B}


class TestCameraMutationsAdminScope:
    def test_get_other_tenant_camera_is_404(self, app, client, camera_repo):
        resp = client.get(f"/api/cameras/{CAM_A}", headers=_hdr(app, ADMIN_B, TENANT_B))
        assert resp.status_code == 404, f"got {resp.status_code}: {resp.get_json()}"

    def test_get_own_camera_is_200(self, app, client, camera_repo):
        resp = client.get(f"/api/cameras/{CAM_A}", headers=_hdr(app, ADMIN_A, TENANT_A))
        assert resp.status_code == 200

    def test_superadmin_assumed_context_keeps_get_override(self, app, client, camera_repo):
        """Contexto assumido: identity = superadmin, claim tenant = B → câmera de A ainda 200."""
        resp = client.get(f"/api/cameras/{CAM_A}", headers=_hdr(app, SUPER, TENANT_B))
        assert resp.status_code == 200, f"got {resp.status_code}: {resp.get_json()}"
        assert resp.get_json()["data"]["id"] == CAM_A

    def test_update_other_tenant_camera_is_404(self, app, client, camera_repo):
        resp = client.put(
            f"/api/cameras/{CAM_A}", json={"name": "pwned"},
            headers=_hdr(app, ADMIN_B, TENANT_B),
        )
        assert resp.status_code == 404, f"got {resp.status_code}: {resp.get_json()}"
        camera_repo.update.assert_not_called()

    def test_delete_other_tenant_camera_is_404(self, app, client, camera_repo):
        resp = client.delete(f"/api/cameras/{CAM_A}", headers=_hdr(app, ADMIN_B, TENANT_B))
        assert resp.status_code == 404, f"got {resp.status_code}: {resp.get_json()}"
        camera_repo.delete.assert_not_called()


class TestStreamAndTestAdminScope:
    @pytest.fixture(autouse=True)
    def _stream_env(self, monkeypatch):
        monkeypatch.setattr(stream_handlers, "_get_redis", lambda: MagicMock())
        monkeypatch.setattr(stream_handlers, "get_segments_redis", lambda: MagicMock())
        monkeypatch.setattr(stream_handlers, "_is_gateway_online", lambda _r: True)

    def test_start_stream_other_tenant_camera_is_404(self, app, client, camera_repo):
        resp = client.post(
            f"/api/cameras/{CAM_A}/stream/start", headers=_hdr(app, ADMIN_B, TENANT_B)
        )
        assert resp.status_code == 404, f"got {resp.status_code}: {resp.get_json()}"

    def test_start_stream_own_camera_still_works_for_tenant_admin(self, app, client, camera_repo):
        """Admin de A segue operando a própria câmera — sem depender do override."""
        resp = client.post(
            f"/api/cameras/{CAM_A}/stream/start", headers=_hdr(app, ADMIN_A, TENANT_A)
        )
        assert resp.status_code == 200, f"got {resp.status_code}: {resp.get_json()}"

    def test_superadmin_assumed_context_keeps_start_stream_override(self, app, client, camera_repo):
        """Superadmin com claim tenant = B ainda inicia stream de câmera de A (override global)."""
        resp = client.post(
            f"/api/cameras/{CAM_A}/stream/start", headers=_hdr(app, SUPER, TENANT_B)
        )
        assert resp.status_code == 200, f"got {resp.status_code}: {resp.get_json()}"

    def test_test_camera_passes_jwt_tenant_not_user_id(self, app, client, monkeypatch, camera_repo):
        """/test resolve posse por get_tenant_id(); admin de tenant não tem override."""
        service = MagicMock()
        service.build_stream_url.side_effect = NotFoundError("Câmera", CAM_A)
        monkeypatch.setattr(test_handler, "_get_camera_service", lambda: service)

        resp = client.post(f"/api/cameras/{CAM_A}/test", headers=_hdr(app, ADMIN_B, TENANT_B))
        assert resp.status_code == 200  # diagnóstico estruturado, url_format=error
        assert resp.get_json()["data"]["checks"]["url_format"]["status"] == "error"
        args = service.build_stream_url.call_args[0]
        assert args[0] == UUID(CAM_A)
        assert str(args[1]) == TENANT_B, f"esperava tenant do JWT, recebeu {args[1]!r}"
        assert args[2] is False, "admin de tenant não pode ter override global"
