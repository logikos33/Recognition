"""
Integration tests: probe endpoint (task-046).

Cobertura:
  POST /api/cameras/probe — gate SSRF + probe de conectividade

Gate SSRF: loopback e link-local devem ser rejeitados com 422.
RFC1918 (192.168.x.x) é PERMITIDO — câmeras vivem na LAN.
ffprobe é mockado em todos os testes (sem dependência de rede/binário).
"""
from unittest.mock import patch
from uuid import uuid4

import pytest

TENANT_ID = str(uuid4())


@pytest.fixture
def admin_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT_ID,
                "role": "admin",
                "tenant_schema": "test_schema",
            },
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_headers(app):
    with app.app_context():
        from flask_jwt_extended import create_access_token
        token = create_access_token(
            identity=str(uuid4()),
            additional_claims={
                "tenant_id": TENANT_ID,
                "role": "operator",
                "tenant_schema": "test_schema",
            },
        )
    return {"Authorization": f"Bearer {token}"}


def _probe_body(**kwargs):
    base = {
        "manufacturer": "intelbras",
        "ip_or_host": "192.168.1.100",
        "port": 554,
        "username": "admin",
        "password": "pass",
        "channel": 1,
    }
    return {**base, **kwargs}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class TestProbeAuth:

    def test_requires_jwt(self, client) -> None:
        res = client.post("/api/cameras/probe", json=_probe_body())
        assert res.status_code in (401, 422)

    def test_operator_allowed(self, client, operator_headers) -> None:
        """Operadores também podem fazer probe (instalar câmera)."""
        with patch("app.api.v1.cameras.probe_handler._resolve_and_pin", return_value="192.168.1.100"), \
             patch("app.api.v1.cameras.probe_handler._ffprobe_stream",
                   return_value={"ok": True, "codec": "h264", "resolution": "1920x1080", "fps": 15.0}):
            res = client.post("/api/cameras/probe", json=_probe_body(), headers=operator_headers)
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# SSRF gate — loopback
# ---------------------------------------------------------------------------
class TestSSRFLoopback:

    def test_loopback_ipv4_rejected(self, client, admin_headers) -> None:
        res = client.post(
            "/api/cameras/probe",
            json=_probe_body(ip_or_host="127.0.0.1"),
            headers=admin_headers,
        )
        assert res.status_code == 422
        assert "loopback" in res.get_json().get("error", "").lower()

    def test_loopback_localhost_rejected(self, client, admin_headers) -> None:
        """localhost resolve para 127.0.0.1 — deve ser rejeitado."""
        with patch("app.api.v1.cameras.probe_handler.socket") as mock_socket:
            mock_socket.getaddrinfo.return_value = [
                (2, 1, 6, "", ("127.0.0.1", 0))
            ]
            mock_socket.AF_UNSPEC = 0
            mock_socket.SOCK_STREAM = 1
            mock_socket.AI_ADDRCONFIG = 32
            res = client.post(
                "/api/cameras/probe",
                json=_probe_body(ip_or_host="localhost"),
                headers=admin_headers,
            )
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# SSRF gate — link-local (cloud metadata)
# ---------------------------------------------------------------------------
class TestSSRFLinkLocal:

    def test_link_local_aws_metadata_rejected(self, client, admin_headers) -> None:
        res = client.post(
            "/api/cameras/probe",
            json=_probe_body(ip_or_host="169.254.169.254"),
            headers=admin_headers,
        )
        assert res.status_code == 422
        assert "link-local" in res.get_json().get("error", "").lower()

    def test_link_local_fe80_rejected(self, client, admin_headers) -> None:
        res = client.post(
            "/api/cameras/probe",
            json=_probe_body(ip_or_host="fe80::1"),
            headers=admin_headers,
        )
        assert res.status_code == 422

    def test_hostname_resolving_to_link_local_rejected(self, client, admin_headers) -> None:
        """DNS rebinding: hostname que resolve para 169.254.x.x é bloqueado."""
        with patch("app.api.v1.cameras.probe_handler.socket") as mock_socket:
            mock_socket.getaddrinfo.return_value = [
                (2, 1, 6, "", ("169.254.169.254", 0))
            ]
            mock_socket.AF_UNSPEC = 0
            mock_socket.SOCK_STREAM = 1
            mock_socket.AI_ADDRCONFIG = 32
            res = client.post(
                "/api/cameras/probe",
                json=_probe_body(ip_or_host="metadata.internal"),
                headers=admin_headers,
            )
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# RFC1918 permitido (câmeras LAN)
# ---------------------------------------------------------------------------
class TestPrivateIPAllowed:

    @pytest.mark.parametrize("host", ["192.168.1.100", "10.0.0.50", "172.16.5.10"])
    def test_private_ip_allowed(self, client, admin_headers, host) -> None:
        with patch("app.api.v1.cameras.probe_handler._resolve_and_pin", return_value=host), \
             patch("app.api.v1.cameras.probe_handler._ffprobe_stream",
                   return_value={"ok": True, "codec": "h264", "resolution": "1280x720", "fps": 15.0}):
            res = client.post(
                "/api/cameras/probe",
                json=_probe_body(ip_or_host=host),
                headers=admin_headers,
            )
        assert res.status_code == 200
        assert res.get_json()["success"] is True


# ---------------------------------------------------------------------------
# Validações de input
# ---------------------------------------------------------------------------
class TestProbeValidation:

    def test_missing_host_returns_422(self, client, admin_headers) -> None:
        body = _probe_body()
        del body["ip_or_host"]
        res = client.post("/api/cameras/probe", json=body, headers=admin_headers)
        assert res.status_code == 422

    def test_unknown_manufacturer_returns_422(self, client, admin_headers) -> None:
        res = client.post(
            "/api/cameras/probe",
            json=_probe_body(manufacturer="unknown_brand"),
            headers=admin_headers,
        )
        assert res.status_code == 422

    def test_all_manufacturers_accepted(self, client, admin_headers) -> None:
        for mfr in ("intelbras", "hikvision", "dahua", "generic"):
            with patch("app.api.v1.cameras.probe_handler._resolve_and_pin",
                       return_value="192.168.1.1"), \
                 patch("app.api.v1.cameras.probe_handler._ffprobe_stream",
                       return_value={"ok": True, "codec": "h264", "resolution": "1280x720", "fps": 15.0}):
                res = client.post(
                    "/api/cameras/probe",
                    json=_probe_body(manufacturer=mfr),
                    headers=admin_headers,
                )
            assert res.status_code == 200, f"manufacturer={mfr} failed"


# ---------------------------------------------------------------------------
# Probe bem-sucedido
# ---------------------------------------------------------------------------
class TestProbeSuccess:

    def test_returns_codec_resolution_fps(self, client, admin_headers) -> None:
        with patch("app.api.v1.cameras.probe_handler._resolve_and_pin",
                   return_value="192.168.1.100"), \
             patch("app.api.v1.cameras.probe_handler._ffprobe_stream",
                   return_value={"ok": True, "codec": "h265", "resolution": "1920x1080", "fps": 25.0}):
            res = client.post("/api/cameras/probe", json=_probe_body(), headers=admin_headers)
        data = res.get_json()
        assert res.status_code == 200
        assert data["success"] is True
        assert data["data"]["ok"] is True
        assert data["data"]["codec"] == "h265"
        assert data["data"]["resolution"] == "1920x1080"
        assert data["data"]["fps"] == 25.0
        assert data["data"]["substream_url_sugerida"] is not None

    def test_substream_url_uses_original_host(self, client, admin_headers) -> None:
        """URL sugerida deve conter o host original, não o IP pinado."""
        with patch("app.api.v1.cameras.probe_handler._resolve_and_pin",
                   return_value="192.168.1.100"), \
             patch("app.api.v1.cameras.probe_handler._ffprobe_stream",
                   return_value={"ok": True, "codec": "h264", "resolution": "640x480", "fps": 10.0}):
            res = client.post(
                "/api/cameras/probe",
                json=_probe_body(ip_or_host="minha-camera.local"),
                headers=admin_headers,
            )
        url = res.get_json()["data"]["substream_url_sugerida"]
        assert "minha-camera.local" in url

    def test_probe_failure_returns_ok_false(self, client, admin_headers) -> None:
        with patch("app.api.v1.cameras.probe_handler._resolve_and_pin",
                   return_value="192.168.1.100"), \
             patch("app.api.v1.cameras.probe_handler._ffprobe_stream",
                   return_value={"ok": False, "error": "Autenticação falhou — verifique usuário e senha"}):
            res = client.post("/api/cameras/probe", json=_probe_body(), headers=admin_headers)
        data = res.get_json()
        assert res.status_code == 200
        assert data["data"]["ok"] is False
        assert data["data"]["substream_url_sugerida"] is None


# ---------------------------------------------------------------------------
# Caminho NAT
# ---------------------------------------------------------------------------
class TestProbeNAT:

    def test_nat_path_returns_ok_none(self, client, admin_headers) -> None:
        with patch("app.api.v1.cameras.probe_handler._check_gateway_available",
                   return_value=False):
            res = client.post(
                "/api/cameras/probe",
                json=_probe_body(is_behind_nat=True),
                headers=admin_headers,
            )
        data = res.get_json()
        assert res.status_code == 200
        assert data["data"]["ok"] is None
        assert data["data"]["method"] == "nat"
