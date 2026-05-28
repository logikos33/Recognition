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

    @patch("boto3.client")
    def test_upload_bytes_raises_storage_error(self, mock_client: MagicMock) -> None:
        from botocore.exceptions import ClientError
        from app.infrastructure.storage.r2_storage import R2Storage
        from app.core.exceptions import StorageError

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage._client.put_object.side_effect = ClientError(
            {"Error": {"Code": "500"}}, "PutObject"
        )
        with pytest.raises(StorageError):
            storage.upload_bytes("test/key", b"data", "text/plain")

    @patch("boto3.client")
    def test_download_bytes_success(self, mock_client: MagicMock) -> None:
        from app.infrastructure.storage.r2_storage import R2Storage

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        mock_body = MagicMock()
        mock_body.read.return_value = b"image-data"
        storage._client.get_object.return_value = {"Body": mock_body}

        result = storage.download_bytes("frames/test.jpg")
        assert result == b"image-data"
        storage._client.get_object.assert_called_once_with(
            Bucket="bucket", Key="frames/test.jpg"
        )

    @patch("boto3.client")
    def test_download_bytes_raises_storage_error(self, mock_client: MagicMock) -> None:
        from botocore.exceptions import ClientError
        from app.infrastructure.storage.r2_storage import R2Storage
        from app.core.exceptions import StorageError

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage._client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "GetObject"
        )
        with pytest.raises(StorageError):
            storage.download_bytes("missing/key.jpg")

    @patch("boto3.client")
    def test_delete_calls_delete_object(self, mock_client: MagicMock) -> None:
        from app.infrastructure.storage.r2_storage import R2Storage

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage.delete("test/del.jpg")
        storage._client.delete_object.assert_called_once_with(
            Bucket="bucket", Key="test/del.jpg"
        )

    @patch("boto3.client")
    def test_delete_raises_storage_error(self, mock_client: MagicMock) -> None:
        from botocore.exceptions import ClientError
        from app.infrastructure.storage.r2_storage import R2Storage
        from app.core.exceptions import StorageError

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage._client.delete_object.side_effect = ClientError(
            {"Error": {"Code": "500"}}, "DeleteObject"
        )
        with pytest.raises(StorageError):
            storage.delete("test/key")

    @patch("boto3.client")
    def test_list_keys_returns_keys(self, mock_client: MagicMock) -> None:
        from app.infrastructure.storage.r2_storage import R2Storage

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage._client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "frames/a.jpg"},
                {"Key": "frames/b.jpg"},
            ]
        }
        keys = storage.list_keys("frames/")
        assert keys == ["frames/a.jpg", "frames/b.jpg"]

    @patch("boto3.client")
    def test_list_keys_empty_bucket(self, mock_client: MagicMock) -> None:
        from app.infrastructure.storage.r2_storage import R2Storage

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage._client.list_objects_v2.return_value = {}
        keys = storage.list_keys("empty/")
        assert keys == []

    @patch("boto3.client")
    def test_list_keys_raises_storage_error(self, mock_client: MagicMock) -> None:
        from botocore.exceptions import ClientError
        from app.infrastructure.storage.r2_storage import R2Storage
        from app.core.exceptions import StorageError

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage._client.list_objects_v2.side_effect = ClientError(
            {"Error": {"Code": "500"}}, "ListObjectsV2"
        )
        with pytest.raises(StorageError):
            storage.list_keys("prefix/")

    @patch("boto3.client")
    def test_generate_presigned_upload_url(self, mock_client: MagicMock) -> None:
        from app.infrastructure.storage.r2_storage import R2Storage

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage._client.generate_presigned_url.return_value = "https://r2.test/presigned"
        url = storage.generate_presigned_upload_url("raw-videos/video.mp4", "video/mp4")
        assert url == "https://r2.test/presigned"
        storage._client.generate_presigned_url.assert_called_once_with(
            "put_object",
            Params={"Bucket": "bucket", "Key": "raw-videos/video.mp4", "ContentType": "video/mp4"},
            ExpiresIn=900,
        )

    @patch("boto3.client")
    def test_generate_presigned_upload_url_raises(self, mock_client: MagicMock) -> None:
        from botocore.exceptions import ClientError
        from app.infrastructure.storage.r2_storage import R2Storage
        from app.core.exceptions import StorageError

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage._client.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "500"}}, "GeneratePresignedUrl"
        )
        with pytest.raises(StorageError):
            storage.generate_presigned_upload_url("key.mp4")

    @patch("boto3.client")
    def test_generate_presigned_download_url(self, mock_client: MagicMock) -> None:
        from app.infrastructure.storage.r2_storage import R2Storage

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage._client.generate_presigned_url.return_value = "https://r2.test/dl"
        url = storage.generate_presigned_download_url("frames/img.jpg", ttl=1800)
        assert url == "https://r2.test/dl"
        storage._client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "bucket", "Key": "frames/img.jpg"},
            ExpiresIn=1800,
        )

    @patch("boto3.client")
    def test_generate_presigned_download_url_raises(self, mock_client: MagicMock) -> None:
        from botocore.exceptions import ClientError
        from app.infrastructure.storage.r2_storage import R2Storage
        from app.core.exceptions import StorageError

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage._client.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "500"}}, "GeneratePresignedUrl"
        )
        with pytest.raises(StorageError):
            storage.generate_presigned_download_url("key.jpg")

    @patch("boto3.client")
    def test_upload_file_calls_upload_file(self, mock_client: MagicMock) -> None:
        from app.infrastructure.storage.r2_storage import R2Storage

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage.upload_file("frames/img.jpg", "/tmp/frame.jpg")
        storage._client.upload_file.assert_called_once_with(
            "/tmp/frame.jpg", "bucket", "frames/img.jpg"
        )

    @patch("boto3.client")
    def test_upload_file_raises_storage_error(self, mock_client: MagicMock) -> None:
        from botocore.exceptions import ClientError
        from app.infrastructure.storage.r2_storage import R2Storage
        from app.core.exceptions import StorageError

        storage = R2Storage("https://test.r2", "bucket", "key", "secret")
        storage._client.upload_file.side_effect = ClientError(
            {"Error": {"Code": "500"}}, "UploadFile"
        )
        with pytest.raises(StorageError):
            storage.upload_file("key.jpg", "/tmp/f.jpg")
