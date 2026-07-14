"""
Regression tests — THREAT_MODEL.md gap #2: 404-vs-403 inconsistente em câmeras.

SECURITY.md documenta o princípio: "acesso cross-tenant retorna 404 (nunca
403 — não vazamos existência)". alerts/routes.py já seguia esse padrão
(404), mas CameraService.build_rtsp_url/build_stream_url/update_camera/
patch_config/delete_camera levantavam AuthorizationError (403) para acesso
cross-tenant em vez de NotFoundError (404) — vazando a existência do
camera_id de outro tenant via diferença de status code.

FALHA antes do fix: as 5 chamadas acima lançavam AuthorizationError (403)
quando `camera["tenant_id"] != tenant_id/user_id do requisitante`.
PASSA após o fix: todas lançam NotFoundError (404), idêntico ao caso
"câmera inexistente" — sem diferenciar (evita enumeração).
"""
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import AuthorizationError, NotFoundError
from app.domain.services.camera_service import CameraService

TENANT_A = uuid4()
TENANT_B = uuid4()
CAMERA_ID = uuid4()


def _cam() -> dict:
    return {
        "id": CAMERA_ID,
        "tenant_id": TENANT_A,
        "name": "Cam Portaria",
        "host": "192.168.1.1",
        "port": 554,
        "username": "admin",
        "password_encrypted": "",
        "manufacturer": "generic",
        "channel": 1,
        "subtype": 0,
        "rtsp_url_override": "rtsp://admin:pass@192.168.1.1:554/stream",
        "is_active": True,
        "fps_target": 5,
        "quality_preset": "medium",
    }


@pytest.fixture()
def service():
    repo = MagicMock()
    repo.get_by_id.return_value = _cam()
    return CameraService(repo, fernet_key="")


class TestCrossTenantReturns404NotAuthorizationError:
    """Nenhum dos 5 pontos de checagem cross-tenant deve levantar AuthorizationError."""

    def test_build_rtsp_url_cross_tenant_is_404(self, service):
        with pytest.raises(NotFoundError):
            service.build_rtsp_url(CAMERA_ID, TENANT_B)

    def test_build_stream_url_cross_tenant_is_404(self, service):
        with pytest.raises(NotFoundError):
            service.build_stream_url(CAMERA_ID, TENANT_B)

    def test_update_camera_cross_tenant_is_404(self, service):
        with pytest.raises(NotFoundError):
            service.update_camera(CAMERA_ID, TENANT_B, {"name": "hijacked"})

    def test_patch_config_cross_tenant_is_404(self, service):
        with pytest.raises(NotFoundError):
            service.patch_config(CAMERA_ID, TENANT_B, fps_target=10)

    def test_delete_camera_cross_tenant_is_404(self, service):
        with pytest.raises(NotFoundError):
            service.delete_camera(CAMERA_ID, TENANT_B)

    def test_no_cross_tenant_check_ever_raises_authorization_error(self, service):
        """Contra-prova direta: nenhum dos 5 métodos deve levantar 403 para cross-tenant."""
        checks = [
            lambda: service.build_rtsp_url(CAMERA_ID, TENANT_B),
            lambda: service.build_stream_url(CAMERA_ID, TENANT_B),
            lambda: service.update_camera(CAMERA_ID, TENANT_B, {"name": "x"}),
            lambda: service.patch_config(CAMERA_ID, TENANT_B, fps_target=10),
            lambda: service.delete_camera(CAMERA_ID, TENANT_B),
        ]
        for check in checks:
            try:
                check()
            except AuthorizationError:
                pytest.fail(
                    "Acesso cross-tenant vazou via 403 (AuthorizationError) — "
                    "deve ser 404 (NotFoundError), ver SECURITY.md"
                )
            except NotFoundError:
                pass  # esperado


class TestSameTenantStillWorks:
    """Regressão: acesso do PRÓPRIO tenant não deve virar 404."""

    def test_build_rtsp_url_same_tenant_succeeds(self, service):
        url = service.build_rtsp_url(CAMERA_ID, TENANT_A)
        assert url.startswith("rtsp://")

    def test_delete_camera_same_tenant_succeeds(self, service, ):
        service.delete_camera(CAMERA_ID, TENANT_A)


class TestAdminOverrideStillWorks:
    """Regressão: admin/superadmin mantém o bypass cross-tenant (is_admin=True)."""

    def test_build_rtsp_url_admin_override(self, service):
        url = service.build_rtsp_url(CAMERA_ID, TENANT_B, is_admin=True)
        assert url.startswith("rtsp://")

    def test_delete_camera_admin_override(self, service):
        service.delete_camera(CAMERA_ID, TENANT_B, is_admin=True)
