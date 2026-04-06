"""Tests: R2Storage (mocked boto3)."""
import pytest
from unittest.mock import MagicMock, patch

from app.core.exceptions import StorageError
from app.infrastructure.storage.base import StorageStrategy


class TestMockStorage:
    """Testes para MockStorageStrategy (valida interface)."""

    def setup_method(self) -> None:
        """Setup: importar conftest MockStorageStrategy."""
        from tests.conftest import MockStorageStrategy
        self.storage = MockStorageStrategy()

    def test_implements_strategy(self) -> None:
        assert isinstance(self.storage, StorageStrategy)

    def test_upload_and_download(self) -> None:
        self.storage.upload_bytes("test/file.jpg", b"image-data", "image/jpeg")
        data = self.storage.download_bytes("test/file.jpg")
        assert data == b"image-data"

    def test_download_nonexistent_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            self.storage.download_bytes("nonexistent/key")

    def test_exists(self) -> None:
        assert not self.storage.exists("test/key")
        self.storage.upload_bytes("test/key", b"data", "text/plain")
        assert self.storage.exists("test/key")

    def test_delete(self) -> None:
        self.storage.upload_bytes("test/delete-me", b"data", "text/plain")
        assert self.storage.exists("test/delete-me")
        self.storage.delete("test/delete-me")
        assert not self.storage.exists("test/delete-me")

    def test_list_keys(self) -> None:
        self.storage.upload_bytes("prefix/a.jpg", b"a", "image/jpeg")
        self.storage.upload_bytes("prefix/b.jpg", b"b", "image/jpeg")
        self.storage.upload_bytes("other/c.jpg", b"c", "image/jpeg")
        keys = self.storage.list_keys("prefix/")
        assert len(keys) == 2
        assert "prefix/a.jpg" in keys

    def test_presigned_upload_url(self) -> None:
        url = self.storage.generate_presigned_upload_url("key/test.mp4")
        assert "mock-r2.test" in url
        assert "upload" in url

    def test_presigned_download_url(self) -> None:
        url = self.storage.generate_presigned_download_url("key/test.mp4")
        assert "mock-r2.test" in url
        assert "download" in url

    def test_upload_file(self) -> None:
        self.storage.upload_file("key/file.pt", "/tmp/fake.pt")
        assert self.storage.exists("key/file.pt")


class TestR2StorageInit:
    """Testes para R2Storage initialization (mocked boto3)."""

    PATCH_TARGET = "boto3.client"

    @patch("boto3.client")
    def test_init_creates_client(self, mock_client: MagicMock) -> None:
        from app.infrastructure.storage.r2_storage import R2Storage

        storage = R2Storage(
            endpoint="https://test.r2.cloudflarestorage.com",
            bucket="test-bucket",
            access_key="test-key",
            secret_key="test-secret",
        )
        mock_client.assert_called_once_with(
            "s3",
            endpoint_url="https://test.r2.cloudflarestorage.com",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region_name="auto",
        )

    @patch("boto3.client")
    def test_exists_returns_true(self, mock_client: MagicMock) -> None:
        from app.infrastructure.storage.r2_storage import R2Storage

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage._client.head_object.return_value = {}
        assert storage.exists("some/key") is True

    @patch("boto3.client")
    def test_exists_returns_false(self, mock_client: MagicMock) -> None:
        from botocore.exceptions import ClientError
        from app.infrastructure.storage.r2_storage import R2Storage

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage._client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadObject"
        )
        assert storage.exists("nonexistent/key") is False

    @patch("boto3.client")
    def test_upload_bytes_calls_put_object(self, mock_client: MagicMock) -> None:
        from app.infrastructure.storage.r2_storage import R2Storage

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage.upload_bytes("test/key", b"data", "text/plain")
        storage._client.put_object.assert_called_once_with(
            Bucket="bucket",
            Key="test/key",
            Body=b"data",
            ContentType="text/plain",
        )
