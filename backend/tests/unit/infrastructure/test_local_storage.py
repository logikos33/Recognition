"""Tests: LocalStorage."""
import os
import pytest
import tempfile
import shutil

from app.infrastructure.storage.local_storage import LocalStorage
from app.infrastructure.storage.base import StorageStrategy
from app.core.exceptions import StorageError


class TestLocalStorage:
    """Testes para LocalStorage."""

    def setup_method(self) -> None:
        self.tmp_dir = tempfile.mkdtemp()
        self.storage = LocalStorage(self.tmp_dir)

    def teardown_method(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_implements_strategy(self) -> None:
        assert isinstance(self.storage, StorageStrategy)

    def test_upload_and_download_bytes(self) -> None:
        self.storage.upload_bytes("test/file.txt", b"hello world", "text/plain")
        data = self.storage.download_bytes("test/file.txt")
        assert data == b"hello world"

    def test_download_nonexistent_raises(self) -> None:
        with pytest.raises(StorageError, match="File not found"):
            self.storage.download_bytes("nonexistent/key")

    def test_exists(self) -> None:
        assert not self.storage.exists("test/key")
        self.storage.upload_bytes("test/key", b"data", "text/plain")
        assert self.storage.exists("test/key")

    def test_delete(self) -> None:
        self.storage.upload_bytes("test/del", b"data", "text/plain")
        assert self.storage.exists("test/del")
        self.storage.delete("test/del")
        assert not self.storage.exists("test/del")

    def test_delete_nonexistent_no_error(self) -> None:
        self.storage.delete("nonexistent/key")  # Should not raise

    def test_list_keys(self) -> None:
        self.storage.upload_bytes("prefix/a.txt", b"a", "text/plain")
        self.storage.upload_bytes("prefix/b.txt", b"b", "text/plain")
        self.storage.upload_bytes("other/c.txt", b"c", "text/plain")
        keys = self.storage.list_keys("prefix")
        assert len(keys) == 2

    def test_upload_file(self) -> None:
        src = os.path.join(self.tmp_dir, "source.txt")
        with open(src, "w") as f:
            f.write("file content")
        self.storage.upload_file("uploaded/file.txt", src)
        assert self.storage.exists("uploaded/file.txt")

    def test_presigned_upload_url(self) -> None:
        url = self.storage.generate_presigned_upload_url("key/test")
        assert "upload" in url

    def test_presigned_download_url(self) -> None:
        url = self.storage.generate_presigned_download_url("key/test")
        assert "download" in url

    def test_path_traversal_blocked(self) -> None:
        with pytest.raises(StorageError, match="traversal"):
            self.storage.upload_bytes("../../etc/passwd", b"evil", "text/plain")

    def test_nested_directories_created(self) -> None:
        self.storage.upload_bytes("a/b/c/d/file.txt", b"deep", "text/plain")
        assert self.storage.exists("a/b/c/d/file.txt")
