"""
EPI Monitor V2 — Local Filesystem Storage (fallback when R2 not configured).

Implements StorageStrategy using local filesystem.
Files stored under storage/ directory.
"""
import logging
import os
import shutil

from app.core.exceptions import StorageError
from app.infrastructure.storage.base import StorageStrategy

logger = logging.getLogger(__name__)


class LocalStorage(StorageStrategy):
    """Filesystem-based storage for development and R2 fallback."""

    def __init__(self, base_dir: str = "storage") -> None:
        self._base_dir = os.path.realpath(os.path.abspath(base_dir))
        os.makedirs(self._base_dir, exist_ok=True)
        logger.info("local_storage_initialized: base_dir=%s", self._base_dir)

    def _full_path(self, key: str) -> str:
        """Resolve key to full filesystem path. Prevents traversal."""
        full = os.path.realpath(os.path.join(self._base_dir, key))
        if not full.startswith(self._base_dir + os.sep) and full != self._base_dir:
            raise StorageError("Path traversal detected")
        return full

    def generate_presigned_upload_url(
        self, key: str, content_type: str = "application/octet-stream", ttl: int = 900
    ) -> str:
        """Local storage: returns the API upload endpoint path."""
        return f"/api/storage/upload/{key}"

    def generate_presigned_download_url(
        self, key: str, ttl: int = 3600, response_content_type: str | None = None
    ) -> str:
        """Local storage: returns the API download endpoint path."""
        return f"/api/storage/download/{key}"

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        """Write bytes to local file."""
        path = self._full_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        logger.debug("local_upload: key=%s, size=%d", key, len(data))

    def download_bytes(self, key: str) -> bytes:
        """Read bytes from local file."""
        path = self._full_path(key)
        if not os.path.exists(path):
            raise StorageError(f"File not found: {key}")
        with open(path, "rb") as f:
            return f.read()

    def upload_file(self, key: str, local_path: str) -> None:
        """Copy local file to storage."""
        dest = self._full_path(key)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(local_path, dest)
        logger.debug("local_upload_file: key=%s", key)

    def delete(self, key: str) -> None:
        """Delete file from storage."""
        path = self._full_path(key)
        if os.path.exists(path):
            os.remove(path)

    def exists(self, key: str) -> bool:
        """Check if file exists."""
        return os.path.exists(self._full_path(key))

    def list_keys(self, prefix: str) -> list[str]:
        """List files with prefix."""
        base = self._full_path(prefix)
        if not os.path.isdir(base):
            parent = os.path.dirname(base)
            if not os.path.isdir(parent):
                return []
            base_prefix = os.path.basename(base)
            return [
                os.path.join(prefix, f)
                for f in os.listdir(parent)
                if f.startswith(base_prefix)
            ]
        result = []
        for root, dirs, files in os.walk(base):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, self._base_dir)
                result.append(rel)
        return result


def get_storage() -> StorageStrategy:
    """Factory: returns R2Storage if configured, else LocalStorage."""
    r2_endpoint = os.environ.get("R2_ENDPOINT", "")
    r2_key = os.environ.get("R2_KEY", "")
    r2_secret = os.environ.get("R2_SECRET", "")

    if r2_endpoint and r2_key and r2_secret:
        from app.infrastructure.storage.r2_storage import R2Storage

        return R2Storage(
            endpoint=r2_endpoint,
            bucket=os.environ.get("R2_BUCKET", "epi-monitor"),
            access_key=r2_key,
            secret_key=r2_secret,
        )

    # Determine storage base dir
    base = os.environ.get("STORAGE_DIR", "storage")
    return LocalStorage(base)
