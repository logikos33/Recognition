"""
Recognition — Recorder Service (NVR/DVR, WS-B1, ADR-0034).

CRUD de gravadores + teste de conectividade. Mesmo padrão de
camera_service.py:
  - senha cifrada com Fernet(CAMERA_SECRET_KEY) — nunca retornada em texto
  - password_encrypted nunca aparece em respostas (pop antes de retornar)
  - qualquer URL de conexão passa por RTSPUrlValidator.validate antes de
    ser usada (feito pelos clients em infrastructure/nvr/, não aqui —
    mesma divisão de responsabilidade de camera_service.build_rtsp_url)
"""
import logging
import os
from typing import Any, Optional
from uuid import UUID

from cryptography.fernet import Fernet

from app.core.exceptions import NotFoundError, ValidationError
from app.infrastructure.database.repositories.recorder_repository import (
    RecorderRepository,
)

logger = logging.getLogger(__name__)

_VALID_PROTOCOLS = frozenset({"onvif", "hikvision", "dahua", "intelbras", "rtsp"})


class RecorderService:
    """Use cases de gravadores NVR/DVR (WS-B1)."""

    def __init__(self, recorder_repo: RecorderRepository) -> None:
        self._repo = recorder_repo
        key = os.environ.get("CAMERA_SECRET_KEY", "")
        self._fernet = Fernet(key.encode()) if key else None

    def _encrypt_password(self, password: str) -> str:
        if not self._fernet:
            raise ValidationError("CAMERA_SECRET_KEY não configurada")
        return self._fernet.encrypt(password.encode()).decode()

    def decrypt_password(self, encrypted: "str | None") -> str:
        """Descriptografa senha — USO INTERNO (clients de conexão), nunca
        expor via API."""
        if not self._fernet or not encrypted:
            return ""
        try:
            return self._fernet.decrypt(encrypted.encode()).decode()
        except Exception:
            return ""

    @staticmethod
    def _mask(row: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in row.items() if k != "password_encrypted"}

    def create_recorder(
        self, tenant_id: str, created_by: UUID, data: dict[str, Any]
    ) -> dict[str, Any]:
        if not data.get("name") or not data.get("host"):
            raise ValidationError("name e host são obrigatórios")

        protocol = data.get("protocol") or "onvif"
        if protocol not in _VALID_PROTOCOLS:
            raise ValidationError(
                f"protocol inválido: {protocol!r} (esperado: {sorted(_VALID_PROTOCOLS)})"
            )

        port = data.get("port", 80)
        if not isinstance(port, int) or not (1 <= port <= 65535):
            raise ValidationError("port deve ser um inteiro entre 1 e 65535")

        recorder_data: dict[str, Any] = {
            "tenant_id": tenant_id,
            "name": data["name"],
            "host": data["host"],
            "port": port,
            "username": data.get("username"),
            "protocol": protocol,
            "manufacturer": data.get("manufacturer"),
            "channels": data.get("channels", 0),
            "retention_days": data.get("retention_days"),
            "created_by": created_by,
        }
        if data.get("password"):
            recorder_data["password_encrypted"] = self._encrypt_password(data["password"])

        row = self._repo.create(recorder_data)
        return self._mask(row)

    def list_recorders(self, tenant_id: str) -> list[dict[str, Any]]:
        return [self._mask(r) for r in self._repo.list_by_tenant(tenant_id)]

    def get_recorder(self, recorder_id: UUID, tenant_id: str) -> Optional[dict[str, Any]]:
        row = self._repo.get_by_id(recorder_id, tenant_id)
        return self._mask(row) if row else None

    def get_recorder_or_raise(self, recorder_id: UUID, tenant_id: str) -> dict[str, Any]:
        row = self._repo.get_by_id(recorder_id, tenant_id)
        if not row:
            raise NotFoundError("Recorder", str(recorder_id))
        return row

    def update_recorder(
        self, recorder_id: UUID, tenant_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        update_data = dict(data)
        if "protocol" in update_data and update_data["protocol"] not in _VALID_PROTOCOLS:
            raise ValidationError(
                f"protocol inválido: {update_data['protocol']!r} "
                f"(esperado: {sorted(_VALID_PROTOCOLS)})"
            )
        password = update_data.pop("password", None)
        if password:
            update_data["password_encrypted"] = self._encrypt_password(password)

        row = self._repo.update(recorder_id, tenant_id, update_data)
        if not row:
            raise NotFoundError("Recorder", str(recorder_id))
        return self._mask(row)

    def delete_recorder(self, recorder_id: UUID, tenant_id: str) -> bool:
        deleted = self._repo.delete(recorder_id, tenant_id)
        if not deleted:
            raise NotFoundError("Recorder", str(recorder_id))
        return True

    def test_connection(self, recorder_id: UUID, tenant_id: str) -> dict[str, Any]:
        """Testa conectividade (cascata ONVIF/ISAPI/RTSP — ver infrastructure/nvr).

        Best-effort: qualquer exceção vira status='error' + last_error,
        nunca propaga pro caller (mesmo padrão de camera_service de teste
        de conectividade).
        """
        row = self.get_recorder_or_raise(recorder_id, tenant_id)

        from app.infrastructure.nvr.factory import get_nvr_client  # noqa: PLC0415

        try:
            client = get_nvr_client(row, self.decrypt_password(row.get("password_encrypted")))
            ok = client.test_connection()
            status = "online" if ok else "offline"
            error_msg = None if ok else "Sem resposta do gravador"
        except Exception as exc:
            status = "error"
            error_msg = str(exc)[:500]
            logger.warning("recorder_test_connection_failed: id=%s err=%s", recorder_id, exc)

        updated = self._repo.update_status(recorder_id, tenant_id, status, error_msg)
        return self._mask(updated) if updated else {"status": status, "last_error": error_msg}
