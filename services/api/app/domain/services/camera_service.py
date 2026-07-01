"""
DOMAIN camera_service.py — Camera CRUD, RTSP/HTTP URL construction, and stream control.

Layer: domain
Pattern: Service (framework-agnostic)

Key exports:
  - CameraService.create_camera: validates required fields, Fernet-encrypts password, persists via CameraRepository
  - CameraService.list_cameras: admin sees all cameras, operators see only their own
  - CameraService.get_camera: fetches by UUID, strips password_encrypted from response
  - CameraService.build_rtsp_url: constructs manufacturer-specific RTSP URL (Hikvision/Intelbras/Dahua/generic),
    runs RTSPUrlValidator before returning
  - CameraService.build_stream_url: selects HTTP/ISAPI for Hikvision on non-554 ports, falls back to build_rtsp_url
  - CameraService.update_camera / delete_camera: enforce user ownership or admin bypass
  - CameraService.record_test_result: best-effort persistence of connectivity test outcome

Constraints:
  - CAMERA_SECRET_KEY env var must be set; Fernet key must be 32 url-safe base64 bytes
  - Passwords are never returned in any response — pop password_encrypted before returning dicts
  - All URL construction passes through RTSPUrlValidator.validate before being used

Related: app/core/validators.py, app/infrastructure/database/repositories/camera_repository.py
"""
import logging
from uuid import UUID

from cryptography.fernet import Fernet

from app.core.exceptions import (
    AuthorizationError,
    NotFoundError,
    ValidationError,
)
from app.core.validators import RTSPUrlValidator
from app.infrastructure.database.repositories.camera_repository import CameraRepository

logger = logging.getLogger(__name__)


class CameraService:
    """Use cases de câmeras IP."""

    def __init__(
        self,
        camera_repo: CameraRepository,
        fernet_key: str,
    ) -> None:
        self._camera_repo = camera_repo
        self._fernet = Fernet(fernet_key.encode()) if fernet_key else None

    def _encrypt_password(self, password: str) -> str:
        """Criptografa senha com Fernet."""
        if not self._fernet:
            raise ValidationError("CAMERA_SECRET_KEY não configurada")
        return self._fernet.encrypt(password.encode()).decode()

    _VALID_CODECS: frozenset[str] = frozenset({"h264", "h265"})

    def _validate_hardening_fields(self, data: dict) -> None:
        """Valida campos de hardening: detection_stream_url, video_codec, max_auth_failures."""
        video_codec = data.get("video_codec")
        if video_codec is not None and video_codec not in self._VALID_CODECS:
            raise ValidationError(
                f"video_codec '{video_codec}' inválido — aceitos: h264, h265 (ou null)"
            )

        max_auth_failures = data.get("max_auth_failures")
        if max_auth_failures is not None:
            if not isinstance(max_auth_failures, int) or max_auth_failures < 1:
                raise ValidationError(
                    "max_auth_failures deve ser inteiro >= 1"
                )

        detection_stream_url = data.get("detection_stream_url")
        if detection_stream_url:
            RTSPUrlValidator.validate(detection_stream_url)

    def _decrypt_password(self, encrypted: str) -> str:
        """Descriptografa senha com Fernet."""
        if not self._fernet or not encrypted:
            return ""
        try:
            return self._fernet.decrypt(encrypted.encode()).decode()
        except Exception:
            return ""

    def create_camera(self, user_id: UUID, data: dict) -> dict:
        """Cria câmera IP. Criptografa senha antes de salvar."""
        if not data.get("name") or not data.get("host"):
            raise ValidationError("name e host são obrigatórios")

        self._validate_hardening_fields(data)

        camera_data = {
            "tenant_id": user_id,
            "name": data["name"],
            "location": data.get("location"),
            "description": data.get("description"),
            "manufacturer": data.get("manufacturer", "generic"),
            "host": data["host"],
            "port": data.get("port", 554),
            "username": data.get("username", "admin"),
            "channel": data.get("channel", 1),
            "subtype": data.get("subtype", 0),
            "detection_stream_url": data.get("detection_stream_url"),
            "video_codec": data.get("video_codec"),
            "max_auth_failures": data.get("max_auth_failures", 5),
        }

        if data.get("password"):
            camera_data["password_encrypted"] = self._encrypt_password(
                data["password"]
            )

        camera = self._camera_repo.create(camera_data)
        camera["id"] = str(camera["id"])
        return camera

    def list_cameras(self, user_id: UUID, is_admin: bool = False) -> list[dict]:
        """Lista câmeras. Admin vê todas, operator vê as suas."""
        if is_admin:
            cameras = self._camera_repo.get_all()
        else:
            cameras = self._camera_repo.get_by_user(user_id)

        for cam in cameras:
            cam["id"] = str(cam["id"])
        return cameras

    def get_camera(self, camera_id: UUID) -> dict:
        """Busca câmera por ID (sem senha)."""
        camera = self._camera_repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundError("Câmera", str(camera_id))
        camera["id"] = str(camera["id"])
        camera.pop("password_encrypted", None)
        return camera

    def build_rtsp_url(self, camera_id: UUID, user_id: UUID, is_admin: bool = False) -> str:
        """Constrói URL RTSP da câmera. Valida permissão."""
        camera = self._camera_repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundError("Câmera", str(camera_id))

        if str(camera["tenant_id"]) != str(user_id) and not is_admin:
            raise AuthorizationError("Sem permissão para esta câmera")

        if camera.get("rtsp_url_override"):
            url = camera["rtsp_url_override"]
        else:
            from urllib.parse import quote as _quote  # noqa: PLC0415
            password = self._decrypt_password(camera.get("password_encrypted", ""))
            safe_user = _quote(str(camera.get("username", "")), safe="")
            safe_pass = _quote(password, safe="")
            base = f"rtsp://{safe_user}:{safe_pass}@{camera['host']}:{camera['port']}"

            manufacturer = (camera.get("manufacturer") or "generic").lower()
            channel = camera.get("channel", 1)
            subtype = camera.get("subtype", 0)

            if manufacturer == "hikvision":
                # Hikvision: /Streaming/Channels/{channel}0{subtype+1}
                stream_id = f"{channel}0{subtype + 1}"
                url = f"{base}/Streaming/Channels/{stream_id}"
            elif manufacturer in ("intelbras", "dahua"):
                url = f"{base}/cam/realmonitor?channel={channel}&subtype={subtype}"
            else:
                url = f"{base}/stream1"

        RTSPUrlValidator.validate(url)
        return url

    def build_stream_url(self, camera_id: UUID, user_id: UUID, is_admin: bool = False) -> str:
        """Build best available stream URL. RTSP for port 554, HTTP/ISAPI for Hikvision on other ports."""
        camera = self._camera_repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundError("Câmera", str(camera_id))

        if str(camera["tenant_id"]) != str(user_id) and not is_admin:
            raise AuthorizationError("Sem permissão para esta câmera")

        # Override takes priority (supports any validated scheme)
        if camera.get("rtsp_url_override"):
            url = camera["rtsp_url_override"]
            RTSPUrlValidator.validate(url)
            return url

        port = camera.get("port", 554)
        manufacturer = (camera.get("manufacturer") or "generic").lower()

        # Hikvision on non-554 port → HTTP/ISAPI
        if port != 554 and manufacturer == "hikvision":
            from urllib.parse import quote as _quote  # noqa: PLC0415
            password = self._decrypt_password(camera.get("password_encrypted", ""))
            safe_user = _quote(str(camera.get("username", "")), safe="")
            safe_pass = _quote(password, safe="")
            channel = camera.get("channel", 1)
            subtype = camera.get("subtype", 0)
            stream_id = f"{channel}0{subtype + 1}"
            url = (
                f"http://{safe_user}:{safe_pass}@{camera['host']}:{port}"
                f"/ISAPI/Streaming/channels/{stream_id}/httpPreview"
            )
            RTSPUrlValidator.validate(url)
            return url

        # Default: existing RTSP logic
        return self.build_rtsp_url(camera_id, user_id, is_admin)

    def update_camera(self, camera_id: UUID, user_id: UUID, data: dict, is_admin: bool = False) -> dict:
        """Atualiza câmera. Valida permissão e re-encripta senha se fornecida."""
        camera = self._camera_repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundError("Câmera", str(camera_id))

        if str(camera["tenant_id"]) != str(user_id) and not is_admin:
            raise AuthorizationError("Sem permissão para esta câmera")

        self._validate_hardening_fields(data)

        update_data: dict = {}
        for field in (
            "name", "location", "description", "manufacturer",
            "host", "port", "username", "channel", "subtype",
            "rtsp_url_override", "is_active",
            "detection_stream_url", "video_codec", "max_auth_failures",
        ):
            if field in data:
                update_data[field] = data[field]

        if data.get("password"):
            update_data["password_encrypted"] = self._encrypt_password(data["password"])

        if not update_data:
            raise ValidationError("Nenhum campo para atualizar")

        updated = self._camera_repo.update(camera_id, update_data)
        if updated:
            updated["id"] = str(updated["id"])
            updated.pop("password_encrypted", None)
        return updated  # type: ignore[return-value]

    def record_test_result(self, camera_id: UUID, error: str | None) -> None:
        """Persiste resultado do último teste de conectividade (best-effort)."""
        try:
            self._camera_repo.update_last_tested(camera_id, error)
        except Exception:
            pass  # Não bloquear resposta por falha no registro

    def delete_camera(self, camera_id: UUID, user_id: UUID, is_admin: bool = False) -> None:
        """Deleta câmera. Valida permissão."""
        camera = self._camera_repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundError("Câmera", str(camera_id))

        if str(camera["tenant_id"]) != str(user_id) and not is_admin:
            raise AuthorizationError("Sem permissão para esta câmera")

        self._camera_repo.delete(camera_id)
