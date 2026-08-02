"""Tests: local_storage.get_storage — factory tenant-aware (fix R2/integrações).

Cobertura (falha-antes/passa-depois do gap "dispatch/registry lê R2 sem
tenant_id, direto do env"):
  test_get_storage_no_tenant_uses_platform_env   — sem tenant_id, env decide
  test_get_storage_tenant_byo_wins                — BYO do tenant > env
  test_get_storage_incomplete_falls_back_local    — sem nada + opt-in
                                                     explícito, LocalStorage
  test_get_storage_incomplete_without_opt_in_fails_loud — sem nada e sem
                                                     opt-in, erro (mutirão
                                                     2.1/D-03: default
                                                     invertido — LocalStorage
                                                     deixou de ser o que
                                                     "sobra" sem credencial)
"""
from unittest.mock import patch

import pytest

from app.core.exceptions import StorageError
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
        """Default invertido (mutirão 2.1, D-03): sem NENHUMA credencial R2,
        só cai em LocalStorage com ALLOW_EPHEMERAL_STORAGE=1 explícito."""
        with patch.dict(
            "os.environ", {"ALLOW_EPHEMERAL_STORAGE": "1"}, clear=True
        ):
            storage = get_storage(tenant_id="11111111-1111-1111-1111-111111111111")

        assert isinstance(storage, LocalStorage)

    def test_get_storage_incomplete_without_opt_in_fails_loud(self) -> None:
        """Sem credencial R2 e sem ALLOW_EPHEMERAL_STORAGE=1 -> erro, mesmo
        fora do Railway. Este é o comportamento que mudou: antes bastava
        limpar o ambiente pra cair silenciosamente em disco efêmero."""
        with patch.dict("os.environ", {}, clear=True), pytest.raises(StorageError):
            get_storage(tenant_id="11111111-1111-1111-1111-111111111111")
