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


class TestLocalStorageListKeysFilePrefix:
    """list_keys when prefix resolves to a file path (not a dir) — lines 81-85."""

    def setup_method(self) -> None:
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        self.storage = LocalStorage(self.tmp_dir)

    def teardown_method(self) -> None:
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_list_keys_by_file_prefix_in_parent(self) -> None:
        # Create files like "dir/file_a.txt" and "dir/file_b.txt"
        self.storage.upload_bytes("dir/file_a.txt", b"a", "text/plain")
        self.storage.upload_bytes("dir/file_b.txt", b"b", "text/plain")
        self.storage.upload_bytes("dir/other.txt", b"o", "text/plain")
        # list_keys("dir/file") — "dir/file" is NOT a dir; parent is "dir"
        keys = self.storage.list_keys("dir/file")
        # Should find file_a.txt and file_b.txt but not other.txt
        assert len(keys) == 2
        assert all("file" in k for k in keys)

    def test_list_keys_no_parent_returns_empty(self) -> None:
        # prefix has no existing parent dir at all
        keys = self.storage.list_keys("no_such_parent/subdir/prefix")
        assert keys == []


class TestLocalStorageCopyObject:
    """copy_object method — lines 100-106."""

    def setup_method(self) -> None:
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        self.storage = LocalStorage(self.tmp_dir)

    def teardown_method(self) -> None:
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_copy_creates_destination(self) -> None:
        self.storage.upload_bytes("src/file.txt", b"content", "text/plain")
        self.storage.copy_object("src/file.txt", "dest/file_copy.txt")
        assert self.storage.exists("dest/file_copy.txt")
        assert self.storage.download_bytes("dest/file_copy.txt") == b"content"

    def test_copy_source_not_found_raises(self) -> None:
        with pytest.raises(StorageError, match="source not found"):
            self.storage.copy_object("nonexistent/file.txt", "dest/file.txt")

    def test_copy_creates_nested_dest_dirs(self) -> None:
        self.storage.upload_bytes("src.bin", b"data", "application/octet-stream")
        self.storage.copy_object("src.bin", "deep/nested/dest.bin")
        assert self.storage.exists("deep/nested/dest.bin")


class TestGetStorage:
    """get_storage factory — R2 branch lines 116-118."""

    def test_returns_local_storage_when_no_r2_env(self, monkeypatch) -> None:
        from app.infrastructure.storage.local_storage import get_storage
        monkeypatch.delenv("R2_ENDPOINT", raising=False)
        monkeypatch.delenv("R2_KEY", raising=False)
        monkeypatch.delenv("R2_SECRET", raising=False)
        storage = get_storage()
        assert isinstance(storage, LocalStorage)

    def test_returns_r2_storage_when_r2_env_set(self, monkeypatch) -> None:
        from unittest.mock import MagicMock, patch
        from app.infrastructure.storage.local_storage import get_storage
        monkeypatch.setenv("R2_ENDPOINT", "https://account.r2.cloudflarestorage.com")
        monkeypatch.setenv("R2_KEY", "access-key-id")
        monkeypatch.setenv("R2_SECRET", "secret-key")
        mock_r2 = MagicMock()
        with patch("app.infrastructure.storage.r2_storage.R2Storage", return_value=mock_r2) as r2_cls:
            get_storage()
        r2_cls.assert_called_once()
