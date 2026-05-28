"""
Recognition — Tests: Demo Video Isolation (superadmin vs client).

Cobre os cenários críticos de segurança:
1. Superadmin consegue fazer upload (200/201)
2. Cliente comum não consegue upload (403)
3. Stream info oculta vídeo demo para roles != superadmin
4. Stream info expõe vídeo demo apenas para superadmin
"""
from io import BytesIO
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Fixtures: tokens com roles distintos
# ---------------------------------------------------------------------------

@pytest.fixture
def superadmin_headers(app):
    """JWT com role=superadmin."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={"role": "superadmin"},
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_headers(app):
    """JWT com role=operator (cliente comum)."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={"role": "operator"},
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(app):
    """JWT com role=admin (admin de tenant — não é superadmin)."""
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={"role": "admin"},
        )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Helper: dado de upload mínimo
# ---------------------------------------------------------------------------

def _mp4_upload(module: str = "fueling"):
    """Retorna dados multipart para um upload de vídeo demo."""
    return {
        "video": (BytesIO(b"fake-mp4-data"), "demo.mp4", "video/mp4"),
        "module": module,
    }


# ---------------------------------------------------------------------------
# Testes: upload de vídeo demo
# ---------------------------------------------------------------------------

class TestDemoVideoUpload:

    def test_superadmin_can_upload(self, client, superadmin_headers):
        """Superadmin deve conseguir fazer upload e receber 200/201."""
        mock_record = {"id": 1, "module": "fueling", "r2_url": "https://r2.test/v.mp4"}

        with patch(
            "app.domain.services.demo_video_service.upload",
            return_value=mock_record,
        ):
            res = client.post(
                "/api/admin/demo-videos/upload",
                headers=superadmin_headers,
                data=_mp4_upload(),
                content_type="multipart/form-data",
            )

        assert res.status_code in (200, 201), f"Esperado 200/201, obtido {res.status_code}"
        data = res.get_json()
        assert data.get("success") is True

    def test_operator_cannot_upload(self, client, operator_headers):
        """Operator (cliente comum) deve receber 403 ao tentar upload."""
        res = client.post(
            "/api/admin/demo-videos/upload",
            headers=operator_headers,
            data=_mp4_upload(),
            content_type="multipart/form-data",
        )
        assert res.status_code == 403, f"Esperado 403, obtido {res.status_code}"

    def test_admin_tenant_cannot_upload(self, client, admin_headers):
        """Admin de tenant (não superadmin) também deve receber 403."""
        res = client.post(
            "/api/admin/demo-videos/upload",
            headers=admin_headers,
            data=_mp4_upload(),
            content_type="multipart/form-data",
        )
        assert res.status_code == 403, f"Esperado 403, obtido {res.status_code}"

    def test_unauthenticated_cannot_upload(self, client):
        """Sem token JWT deve receber 401 ou 422."""
        res = client.post(
            "/api/admin/demo-videos/upload",
            data=_mp4_upload(),
            content_type="multipart/form-data",
        )
        assert res.status_code in (401, 422), f"Esperado 401/422, obtido {res.status_code}"


# ---------------------------------------------------------------------------
# Testes: GET /api/admin/demo-videos (listagem)
# ---------------------------------------------------------------------------

class TestDemoVideoList:

    def test_superadmin_can_list(self, client, superadmin_headers):
        """Superadmin deve conseguir listar vídeos demo."""
        with patch(
            "app.domain.services.demo_video_service.list_videos",
            return_value=[{"id": 1, "module": "fueling"}],
        ):
            res = client.get("/api/admin/demo-videos", headers=superadmin_headers)
        assert res.status_code == 200

    def test_operator_cannot_list(self, client, operator_headers):
        """Operator não deve acessar listagem."""
        res = client.get("/api/admin/demo-videos", headers=operator_headers)
        assert res.status_code == 403


# ---------------------------------------------------------------------------
# Testes: stream/info — isolamento crítico de vídeos demo
# ---------------------------------------------------------------------------

class TestStreamInfoIsolation:

    def test_operator_gets_hls_even_when_demo_exists(self, client, operator_headers):
        """
        Mesmo que exista um vídeo demo no banco para a câmera,
        um operator deve receber type='hls' (nunca 'demo_video').

        Verifica que demo_video_service.get_for_camera retorna None para roles != superadmin.
        """
        with patch(
            "app.domain.services.demo_video_service.get_for_camera",
            return_value=None,  # serviço JÁ retorna None para não-superadmin
        ):
            res = client.get("/api/cameras/42/stream/info", headers=operator_headers)

        assert res.status_code == 200
        data = res.get_json()
        assert data["data"]["type"] == "hls", (
            "Operator não deve ver type='demo_video'"
        )

    def test_superadmin_gets_demo_video_when_exists(self, client, superadmin_headers):
        """Superadmin deve receber type='demo_video' quando existe vídeo demo."""
        mock_demo = {"id": 1, "r2_url": "https://r2.test/demo.mp4", "label": "Baia 01"}

        with patch(
            "app.domain.services.demo_video_service.get_for_camera",
            return_value=mock_demo,
        ):
            res = client.get("/api/cameras/42/stream/info", headers=superadmin_headers)

        assert res.status_code == 200
        data = res.get_json()
        assert data["data"]["type"] == "demo_video", (
            "Superadmin deve receber type='demo_video'"
        )
        assert data["data"]["url"] == "https://r2.test/demo.mp4"

    def test_superadmin_gets_hls_when_no_demo(self, client, superadmin_headers):
        """Superadmin deve receber type='hls' quando não há vídeo demo configurado."""
        with patch(
            "app.domain.services.demo_video_service.get_for_camera",
            return_value=None,
        ):
            res = client.get("/api/cameras/99/stream/info", headers=superadmin_headers)

        assert res.status_code == 200
        data = res.get_json()
        assert data["data"]["type"] == "hls"


# ---------------------------------------------------------------------------
# Testes: demo_video_service — isolamento a nível de serviço (unit)
# ---------------------------------------------------------------------------

class TestDemoVideoServiceIsolation:

    def test_get_for_camera_returns_none_for_non_superadmin(self):
        """
        Teste de unidade do serviço: get_for_camera deve retornar None
        para qualquer role diferente de 'superadmin', mesmo que o banco tenha registro.
        """
        from app.domain.services import demo_video_service

        mock_repo = MagicMock()
        mock_repo.get_for_camera.return_value = {"id": 1, "r2_url": "https://r2.test/v.mp4"}

        with patch(
            "app.domain.services.demo_video_service._get_repo",
            return_value=mock_repo,
        ):
            # operator não deve ver o vídeo
            result_operator = demo_video_service.get_for_camera(42, "operator")
            result_admin = demo_video_service.get_for_camera(42, "admin")
            result_viewer = demo_video_service.get_for_camera(42, "viewer")

        assert result_operator is None, "operator não deve receber vídeo demo"
        assert result_admin is None, "admin não deve receber vídeo demo"
        assert result_viewer is None, "viewer não deve receber vídeo demo"
        # Confirma que o banco nem foi consultado para esses roles
        mock_repo.get_for_camera.assert_not_called()

    def test_get_for_camera_returns_video_for_superadmin(self):
        """Superadmin deve receber o vídeo demo quando existe no banco."""
        from app.domain.services import demo_video_service

        mock_video = {"id": 5, "r2_url": "https://r2.test/v.mp4", "label": "Demo"}
        mock_repo = MagicMock()
        mock_repo.get_for_camera.return_value = mock_video

        with patch(
            "app.domain.services.demo_video_service._get_repo",
            return_value=mock_repo,
        ):
            result = demo_video_service.get_for_camera(42, "superadmin")

        assert result == mock_video
        mock_repo.get_for_camera.assert_called_once_with(42)

    def test_upload_raises_for_non_superadmin(self):
        """upload() deve lançar AuthorizationError para roles não-superadmin."""
        from app.core.exceptions import AuthorizationError
        from app.domain.services import demo_video_service

        with pytest.raises(AuthorizationError):
            demo_video_service.upload(
                file_data=b"data",
                content_type="video/mp4",
                module="fueling",
                user_role="operator",
            )
