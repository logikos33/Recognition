"""
EPI Monitor V2 — Camera Service.

Lógica de negócio para câmeras IP. NÃO conhece Flask.
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

        camera_data = {
            "user_id": user_id,
            "name": data["name"],
            "location": data.get("location"),
            "description": data.get("description"),
            "manufacturer": data.get("manufacturer", "generic"),
            "host": data["host"],
            "port": data.get("port", 554),
            "username": data.get("username", "admin"),
            "channel": data.get("channel", 1),
            "subtype": data.get("subtype", 0),
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

        if str(camera["user_id"]) != str(user_id) and not is_admin:
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

    def update_camera(self, camera_id: UUID, user_id: UUID, data: dict, is_admin: bool = False) -> dict:
        """Atualiza câmera. Valida permissão e re-encripta senha se fornecida."""
        camera = self._camera_repo.get_by_id(camera_id)
        if not camera:
            raise NotFoundError("Câmera", str(camera_id))

        if str(camera["user_id"]) != str(user_id) and not is_admin:
            raise AuthorizationError("Sem permissão para esta câmera")

        update_data: dict = {}
        for field in (
            "name", "location", "description", "manufacturer",
            "host", "port", "username", "channel", "subtype",
            "rtsp_url_override", "is_active",
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

        if str(camera["user_id"]) != str(user_id) and not is_admin:
            raise AuthorizationError("Sem permissão para esta câmera")

        self._camera_repo.delete(camera_id)
