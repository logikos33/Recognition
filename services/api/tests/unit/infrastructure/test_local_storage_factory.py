"""Tests: local_storage.get_storage — factory tenant-aware (fix R2/integrações).

Cobertura (falha-antes/passa-depois do gap "dispatch/registry lê R2 sem
tenant_id, direto do env"):
  test_get_storage_no_tenant_uses_platform_env   — sem tenant_id, env decide
  test_get_storage_tenant_byo_wins                — BYO do tenant > env
  test_get_storage_incomplete_falls_back_local    — sem nada, LocalStorage
"""
from unittest.mock import patch

from app.infrastructure.storage.local_storage import LocalStorage, get_storage
from app.infrastructure.storage.r2_storage import R2Storage


class TestGetStorageFactory:
    def test_get_storage_no_tenant_uses_platform_env(self) -> None:
        with patch.dict("os.environ", {
            "R2_ENDPOINT": "https://platform.r2.cloudflarestorage.com",
            "R2_BUCKET": "platform-bucket",
            "R2_KEY": "platform-key",
            "R2_SECRET": "platform-secret",
        }):
            storage = get_storage()

        assert isinstance(storage, R2Storage)

    def test_get_storage_tenant_byo_wins(self) -> None:
        """Dispatch/registry da pipeline de treino: tenant com R2 próprio
        configurado deve usar o R2Storage dele, não o env de plataforma."""
        fake_creds = {
            "endpoint": "https://tenant.r2.cloudflarestorage.com",
            "bucket": "tenant-bucket",
            "access_key": "tenant-key",
            "secret_key": "tenant-secret",
        }
        with patch(
            "app.domain.services.integration_service.resolve_r2_credentials",
            return_value=fake_creds,
        ):
            with patch.dict("os.environ", {
                "R2_ENDPOINT": "https://platform.r2.cloudflarestorage.com",
                "R2_BUCKET": "platform-bucket",
                "R2_KEY": "platform-key",
                "R2_SECRET": "platform-secret",
            }):
                storage = get_storage(tenant_id="11111111-1111-1111-1111-111111111111")

        assert isinstance(storage, R2Storage)
        assert storage._bucket == "tenant-bucket"

    def test_get_storage_incomplete_falls_back_local(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            storage = get_storage(tenant_id="11111111-1111-1111-1111-111111111111")

        assert isinstance(storage, LocalStorage)
